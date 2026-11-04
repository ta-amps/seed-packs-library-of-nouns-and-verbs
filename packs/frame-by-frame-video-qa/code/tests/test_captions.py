"""WebVTT cues, their line position and the box a player would draw them in."""

from __future__ import annotations

import unittest

from frame_qa.captions import CaptionError, active_cue, caption_box, parse_time, parse_vtt

VTT = """WEBVTT

NOTE a made-up sidecar

c01
00:00:00.167 --> 00:00:04.333 line:82% position:50% align:center
If your plan has tokens left
over at the end of the month

c02
00:00:04.633 --> 00:00:07.400
A single <b>line</b>
"""


class Captions(unittest.TestCase):
    def test_cues_times_text_and_settings(self) -> None:
        cues = parse_vtt(VTT)
        self.assertEqual([c.ident for c in cues], ["c01", "c02"])
        self.assertEqual((cues[0].start_s, cues[0].end_s), (0.167, 4.333))
        self.assertEqual(cues[0].lines, ("If your plan has tokens left", "over at the end of the month"))
        self.assertEqual(cues[0].settings["line"], "82%")
        self.assertEqual(cues[0].line_percent(), 82.0)
        self.assertEqual(cues[1].text, "A single line")
        self.assertEqual(cues[1].line_percent(default=85.0), 85.0)

    def test_active_cue_is_half_open(self) -> None:
        cues = parse_vtt(VTT)
        self.assertIsNone(active_cue(cues, 0.1))
        self.assertEqual(active_cue(cues, 0.167).ident, "c01")
        self.assertIsNone(active_cue(cues, 4.333))
        self.assertEqual(active_cue(cues, 5.0).ident, "c02")

    def test_caption_box_is_centred_below_the_line_position(self) -> None:
        cue = parse_vtt(VTT)[0]
        x0, y0, x1, y1 = caption_box(cue, 1920, 1080, 0.045, 0.52, 1.25)
        font = 0.045 * 1080
        self.assertEqual(y0, round(0.82 * 1080))
        self.assertEqual(x0 + x1, 1920)
        self.assertEqual(y1, y0 + round(2 * 1.25 * font + 0.3 * font))
        self.assertEqual(x1 - x0, round(len("over at the end of the month") * 0.52 * font + font))

    def test_bad_sidecars_fail_loudly(self) -> None:
        with self.assertRaises(CaptionError):
            parse_vtt("1\n00:00:01,000 --> 00:00:02,000\nSRT, not WebVTT\n")
        with self.assertRaises(CaptionError):
            parse_vtt("WEBVTT\n\n00:00:02.000 --> 00:00:01.000\nends first\n")
        with self.assertRaises(CaptionError):
            parse_time("1:2:3")
        self.assertEqual(parse_time("01:02:03.004"), 3723.004)


if __name__ == "__main__":
    unittest.main()
