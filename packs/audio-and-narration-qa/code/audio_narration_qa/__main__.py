"""CLI entry point for audio_narration_qa."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .dynamics import detect_edit_point_clicks, detect_pause_pumping
from .loudness import evaluate_loudness, read_wav_pcm
from .pacing_and_asr import evaluate_asr_cer_gate, evaluate_wpm_and_caption_alignment, parse_webvtt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m audio_narration_qa")
    sub = parser.add_subparsers(dest="command", required=True)

    ld = sub.add_parser("loudness", help="measure BS.1770 loudness, LRA and true peak on a PCM WAV file")
    ld.add_argument("--wav", required=True, type=Path)
    ld.add_argument("--target-lufs", type=float, default=-16.0)

    cer_p = sub.add_parser("cer", help="evaluate ASR Character Error Rate against a reference script")
    cer_p.add_argument("--reference", required=True, type=Path)
    cer_p.add_argument("--hypothesis", required=True, type=Path)
    cer_p.add_argument("--pass-max-cer", type=float, default=0.02)
    cer_p.add_argument("--minor-max-cer", type=float, default=0.05)

    pc = sub.add_parser("pacing", help="check WebVTT WPM pacing and caption-pause alignment")
    pc.add_argument("--vtt", required=True, type=Path)
    pc.add_argument("--phrases-json", required=True, type=Path)
    pc.add_argument("--duration-s", required=True, type=float)

    dy = sub.add_parser("dynamics", help="check pause pumping and edit-point clicks on WAV stems")
    dy.add_argument("--mix-wav", required=True, type=Path)
    dy.add_argument("--music-wav", type=Path)
    dy.add_argument("--phrases-json", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "loudness":
        channels, rate, sha = read_wav_pcm(args.wav)
        res = evaluate_loudness(channels, sample_rate=rate, target_lufs=args.target_lufs)
        res.pop("kp_10ms", None)
        res["sha256"] = sha
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.command == "cer":
        res = evaluate_asr_cer_gate(
            args.reference.read_text(encoding="utf-8"),
            args.hypothesis.read_text(encoding="utf-8"),
            pass_max_cer=args.pass_max_cer,
            minor_max_cer=args.minor_max_cer,
        )
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.command == "pacing":
        cues = parse_webvtt(args.vtt.read_text(encoding="utf-8"))
        phrases = [tuple(p) for p in json.loads(args.phrases_json.read_text(encoding="utf-8"))]
        res = evaluate_wpm_and_caption_alignment(cues, phrases, args.duration_s)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.command == "dynamics":
        mix_ch, rate, sha = read_wav_pcm(args.mix_wav)
        phrases = [tuple(p) for p in json.loads(args.phrases_json.read_text(encoding="utf-8"))]
        mono = [(mix_ch[0][i] + mix_ch[-1][i]) * 0.5 for i in range(len(mix_ch[0]))]
        clicks = detect_edit_point_clicks(mono, sample_rate=rate, speech_phrases=phrases)
        pumping = None
        if args.music_wav:
            mus_ch, mrate, _ = read_wav_pcm(args.music_wav)
            mus_kp = evaluate_loudness(mus_ch, sample_rate=mrate)["kp_10ms"]
            pumping = detect_pause_pumping(mus_kp, phrases)
        print(json.dumps({"sha256": sha, "clicks": clicks, "pumping": pumping}, indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
