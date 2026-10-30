"""WebVTT and SRT parsing, every lint rule, sidecar parity and timing against speech."""

from __future__ import annotations

import unittest

from video_qa_checks.captions import lint, parity, parse_srt, parse_webvtt, speech_sync, stats, to_ms

VTT = """﻿WEBVTT

NOTE sequence=example aspect=landscape_16x9

c01
00:00:00.500 --> 00:00:03.600 line:82% position:50% align:center
Every evening, volunteers
check the <b>shared fridge</b>.

00:03.800 --> 00:06.200
<v Narrator>They log what is running low.</v>
"""

SRT = "1\r\n00:00:00,500 --> 00:00:03,600\r\nEvery evening, volunteers\r\ncheck the shared fridge.\r\n\r\n" \
      "2\r\n00:00:03,800 --> 00:00:06,200\r\nThey log what is running low.\r\n"


def cue(cue_id: str, start: int, end: int, *lines: str, settings: str = "") -> dict:
    return {"cue_id": cue_id, "start_ms": start, "end_ms": end, "settings": settings, "lines": list(lines)}


class Parsing(unittest.TestCase):
    def test_timestamps(self) -> None:
        self.assertEqual(to_ms("00:01:02.345"), 62_345)
        self.assertEqual(to_ms("01:02.345"), 62_345)
        self.assertEqual(to_ms("1:00:00,001"), 3_600_001)
        with self.assertRaises(ValueError):
            to_ms("00:61:00.000")

    def test_webvtt_ids_settings_notes_and_markup(self) -> None:
        cues = parse_webvtt(VTT)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["cue_id"], "c01")
        self.assertEqual(cues[0]["settings"], "line:82% position:50% align:center")
        self.assertEqual(cues[0]["lines"], ["Every evening, volunteers", "check the shared fridge."])
        self.assertEqual(cues[1]["cue_id"], "cue2")
        self.assertEqual((cues[1]["start_ms"], cues[1]["end_ms"]), (3800, 6200))
        self.assertEqual(cues[1]["lines"], ["They log what is running low."])

    def test_webvtt_needs_its_header(self) -> None:
        with self.assertRaises(ValueError):
            parse_webvtt("00:00:00.000 --> 00:00:01.000\nhello\n")

    def test_srt_with_crlf_and_the_same_cues(self) -> None:
        srt = parse_srt(SRT)
        self.assertEqual([c["cue_id"] for c in srt], ["1", "2"])
        self.assertEqual(parity(parse_webvtt(VTT), srt), [])


class Lint(unittest.TestCase):
    def rules(self, cues: list[dict], **limits: object) -> list[str]:
        return [p["rule"] for p in lint(cues, dict(limits) or None)]

    def test_a_clean_track_has_no_problem(self) -> None:
        self.assertEqual(lint(parse_webvtt(VTT)), [])

    def test_each_rule_fires_on_its_own(self) -> None:
        self.assertEqual(self.rules([cue("a", 0, 2000)]), ["empty_cue"])
        self.assertEqual(self.rules([cue("a", 0, 3000, "one", "two", "three")]), ["too_many_lines"])
        self.assertEqual(self.rules([cue("a", 0, 4000, "x" * 43)]), ["line_too_long"])
        self.assertEqual(self.rules([cue("a", 0, 900, "Hi.")]), ["too_short"])
        self.assertEqual(self.rules([cue("a", 0, 7100, "A slow line.")]), ["too_long"])
        self.assertEqual(self.rules([cue("a", 0, 1000, "eighteen chars, ok")]), ["reading_speed"])
        self.assertEqual(self.rules([cue("a", 0, 2000, "Up high.", settings="line:95%")]), ["line_position"])
        self.assertEqual(self.rules([cue("a", 1000, 1000, "Zero.")]), ["ends_before_start"])

    def test_order_overlap_and_blink_gaps(self) -> None:
        a = cue("a", 0, 2000, "First line here.")
        self.assertEqual(self.rules([a, cue("b", 1900, 4000, "Second line.")]), ["overlap"])
        self.assertEqual(self.rules([a, cue("b", 2066, 4000, "Second line.")]), ["blink_gap"])
        self.assertEqual(self.rules([a, cue("b", 2100, 4000, "Second line.")]), [])
        self.assertEqual(self.rules([cue("b", 3000, 5000, "Later."), cue("a", 1000, 2500, "Earlier.")]), ["out_of_order"])

    def test_limits_are_adjustable_and_media_length_is_checked(self) -> None:
        fast = [cue("a", 0, 1000, "eighteen chars, ok")]
        self.assertEqual(lint(fast, {"max_cps": 20}), [])
        problems = lint([cue("a", 0, 2000, "Ends late.")], duration_ms=1500)
        self.assertEqual([p["rule"] for p in problems], ["ends_after_media"])

    def test_stats(self) -> None:
        result = stats(parse_webvtt(VTT))
        self.assertEqual(result["cues"], 2)
        self.assertEqual(result["longest_line"], 29)
        self.assertEqual(result["longest_gap_ms"], 200)
        self.assertEqual(result["max_cps_cue"], "c01")


class Sync(unittest.TestCase):
    def test_coverage_offsets_and_cues_without_speech(self) -> None:
        cues = [cue("a", 400, 3000, "Every evening, volunteers check."), cue("b", 3100, 5800, "They log it."),
                cue("c", 6000, 7500, "Silence here."), cue("d", 8000, 9500, "Early words."),
                cue("e", 10_400, 12_000, "Late words.")]
        speech = [[480, 2900], [3150, 5700], [8700, 9400], [10_050, 11_950]]
        result = speech_sync(cues, speech)
        self.assertEqual(result["cues_without_speech"], ["c"])
        self.assertEqual(result["early"], [{"cue": "d", "offset_ms": -700}])
        self.assertEqual(result["late"], [{"cue": "e", "offset_ms": 350}])
        self.assertEqual(result["speech_ms"], 2420 + 2550 + 700 + 1900)
        self.assertEqual(result["coverage"], round(7220 / 7570, 4))
        self.assertEqual(len(result["problems"]), 3)

    def test_a_cue_after_a_split_inside_one_utterance_is_unmeasured(self) -> None:
        cues = [cue("a", 0, 2500, "A long sentence that"), cue("b", 2500, 5000, "continues here.")]
        result = speech_sync(cues, [[0, 4900]])
        self.assertEqual(result["unmeasured"], ["b"])
        self.assertEqual(result["late"], [])
        self.assertEqual(result["coverage"], 1.0)

    def test_low_coverage_is_a_problem(self) -> None:
        result = speech_sync([cue("a", 0, 1000, "Short.")], [[0, 4000]])
        self.assertEqual(result["coverage"], 0.25)
        self.assertIn("captions cover 0.25 of speech, under 0.95", result["problems"])


if __name__ == "__main__":
    unittest.main()
