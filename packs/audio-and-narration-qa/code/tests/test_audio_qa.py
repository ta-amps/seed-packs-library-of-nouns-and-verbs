"""Unit tests and worked-example recomputation for audio_narration_qa."""

from __future__ import annotations

import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from audio_narration_qa.dynamics import (
    build_hold_duck_envelope,
    detect_edit_point_clicks,
    detect_pause_pumping,
)
from audio_narration_qa.loudness import (
    SR_DEFAULT,
    evaluate_loudness,
    read_wav_pcm,
    sample_peak_dbfs,
    true_peak_dbtp,
)
from audio_narration_qa.pacing_and_asr import (
    evaluate_asr_cer_gate,
    evaluate_wpm_and_caption_alignment,
    parse_webvtt,
)

PACK_SOURCE = Path(__file__).resolve().parents[2] / "source.json"


def _sine_stereo(freq_hz: float, amplitude: float, duration_s: float, sr: int = SR_DEFAULT) -> list[list[float]]:
    n = int(round(duration_s * sr))
    w = 2.0 * math.pi * freq_hz / sr
    ch = [amplitude * math.sin(w * i) for i in range(n)]
    return [ch, list(ch)]


class AudioNarrationQATest(unittest.TestCase):
    def test_bs1770_sine_loudness_and_intersample_true_peak(self) -> None:
        # Per ITU-R BS.1770-4 calibration, the -0.691 offset cancels K-filter gain (+0.691 dB at 997 Hz)
        # so a -18.0 dBFS peak 997 Hz stereo sine wave measures -18.00 LUFS.
        amp = 10.0 ** (-18.0 / 20.0)
        stereo = _sine_stereo(997.0, amp, 4.0)
        res = evaluate_loudness(stereo, target_lufs=-18.0, tolerance_lu=0.2)
        self.assertIsNotNone(res["integrated_lufs"])
        self.assertAlmostEqual(res["integrated_lufs"], -18.0, delta=0.1)
        self.assertEqual(res["findings"], [])

        # Inter-sample peak test: fs/4 cosine shifted by pi/4 hits +/- 0.7071 on samples, 1.0 between samples (+3.01 dBTP)
        sr = 48000
        phase = math.pi / 4.0
        inter = [[0.85 * math.cos(0.5 * math.pi * n + phase) for n in range(4800)]]
        sp = sample_peak_dbfs(inter)
        tp = true_peak_dbtp(inter)
        self.assertGreater(tp - sp, 2.5)
        self.assertGreater(tp, -1.5)

    def test_wav_pcm_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "tone.wav"
            samples = [int(12000 * math.sin(2.0 * math.pi * 440.0 * i / 48000)) for i in range(4800)]
            with wave.open(str(p), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
            ch, rate, sha = read_wav_pcm(p)
            self.assertEqual(rate, 48000)
            self.assertEqual(len(ch), 1)
            self.assertEqual(len(ch[0]), 4800)
            self.assertEqual(len(sha), 64)

    def test_sidechain_pause_pumping_and_hold_envelope(self) -> None:
        # 6 seconds = 600 x 10ms frames; music ducked to 1e-4 during speech, swelling 6 dB (4x power) inside two 0.5s pauses
        kp = [1e-4] * 600
        phrases = [(0.5, 1.8), (2.3, 3.6), (4.1, 5.4)]
        for f in range(180, 230):
            kp[f] = 6.0e-4  # +7.78 dB rise inside first 0.5s pause
        for f in range(360, 410):
            kp[f] = 5.0e-4  # +6.99 dB rise inside second 0.5s pause
        res = detect_pause_pumping(kp, phrases, rise_threshold_db=3.0, min_pumping_pauses=2)
        self.assertEqual(res["pauses_checked"], 2)
        self.assertEqual(res["pauses_rising_over_threshold"], 2)
        self.assertIsNotNone(res["finding"])
        self.assertEqual(res["finding"]["severity"], "major")

        # Hold envelope bridges both 0.5s pauses (< 1.2s hold) into a single continuous duck block
        env = build_hold_duck_envelope(phrases, 6.0, hold_s=1.2, depth_db=11.0)
        ducked = [pt for pt in env if pt[1] == -11.0]
        self.assertEqual(len(ducked), 2)
        self.assertAlmostEqual(ducked[0][0], 0.35, places=2)
        self.assertAlmostEqual(ducked[1][0], 5.55, places=2)

    def test_edit_point_click_detection(self) -> None:
        sr = 48000
        n = sr * 2
        # Quiet smooth low-frequency room tone with an abrupt step splice click at t = 1.000 s
        mono = [0.002 * math.sin(2.0 * math.pi * 120.0 * i / sr) for i in range(n)]
        splice = sr * 1
        mono[splice] += 0.25  # sharp impulse discontinuity at cut boundary
        res = detect_edit_point_clicks(
            mono,
            sample_rate=sr,
            speech_phrases=[(0.1, 0.7), (1.3, 1.8)],
            edit_times_s=[1.0],
        )
        self.assertEqual(len(res["clicks"]), 1)
        self.assertTrue(res["clicks"][0]["near_edit_boundary"])
        self.assertEqual(res["finding"]["severity"], "major")

    def test_wpm_pacing_caption_alignment_and_asr_cer(self) -> None:
        vtt = (
            "WEBVTT\n\n"
            "c1\n00:00:00.500 --> 00:00:03.200\n"
            "Every frame and audio stem is checked before review.\n\n"
            "c2\n00:00:03.800 --> 00:00:06.900\n"
            "Short pauses hold the music duck steady without pumping.\n"
        )
        cues = parse_webvtt(vtt)
        # c1 ends at 3.20s, but speech stops at 2.40s -> 0.80s bleed into pause (> 0.50s limit)
        phrases = [(0.52, 2.40), (3.82, 6.80)]
        pacing = evaluate_wpm_and_caption_alignment(cues, phrases, 7.5)
        ids = {f["id"] for f in pacing["findings"]}
        self.assertIn("caption-end-bleed-into-pause-c1", ids)
        self.assertAlmostEqual(pacing["voice_coverage"], 1.0, places=2)

        cer_pass = evaluate_asr_cer_gate(
            "Every frame and audio stem is checked before review.",
            "every frame and audio stem is checked before review",
        )
        self.assertEqual(cer_pass["cer"], 0.0)
        self.assertEqual(cer_pass["verdict"], "pass")

        cer_fail = evaluate_asr_cer_gate(
            "Every frame and audio stem is checked before review.",
            "Every flame and rodeo step is wrecked before preview.",
        )
        self.assertGreater(cer_fail["cer"], 0.05)
        self.assertEqual(cer_fail["verdict"], "fail")

    def test_pack_worked_example_recomputes_exactly(self) -> None:
        source = json.loads(PACK_SOURCE.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in source["nouns"]}
        inp = nouns["example.narration-cut"]
        expected = nouns["example.qa-report"]["instance"]

        cues = parse_webvtt(inp["webvtt"])
        phrases = [tuple(p) for p in inp["speech_phrases_s"]]
        pumping = detect_pause_pumping(inp["music_kp_10ms"], phrases)
        pacing = evaluate_wpm_and_caption_alignment(cues, phrases, inp["duration_s"])
        cer = evaluate_asr_cer_gate(inp["reference_script"], inp["asr_transcript"])

        self.assertEqual(pumping["pauses_rising_over_threshold"], expected["pumping_pauses"])
        self.assertEqual(pumping["max_rise_db"], expected["max_pause_rise_db"])
        self.assertEqual(pacing["speaking_wpm"], expected["speaking_wpm"])
        self.assertEqual(pacing["voice_coverage"], expected["voice_coverage"])
        self.assertEqual(cer["cer"], expected["asr_cer"])
        self.assertEqual(cer["verdict"], expected["asr_verdict"])


if __name__ == "__main__":
    unittest.main()
