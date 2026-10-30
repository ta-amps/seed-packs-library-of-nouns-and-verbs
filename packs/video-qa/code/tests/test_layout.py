"""The legibility proxy, WCAG contrast, reading time and safe areas, on numbers worked out by hand."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from video_qa_checks.layout import (check_boxes, check_reading, contrast_ok, contrast_ratio, font_px, legibility,
                                    reading_time_s)

FRAME = {"width": 1920, "height": 1080}
DISPLAYS = [{"name": "phone held sideways", "width_px": 844}, {"name": "laptop", "width_px": 1280}]


class Legibility(unittest.TestCase):
    def test_sizes_from_px_source_scale_and_cap_height(self) -> None:
        self.assertEqual(font_px({"id": "a", "px": 20}), 20.0)
        self.assertAlmostEqual(font_px({"id": "b", "source_px": 16, "scale": 1.9}), 30.4)
        self.assertAlmostEqual(font_px({"id": "c", "px": 14, "measure": "cap_px"}), 20.0)
        with self.assertRaises(ValueError):
            font_px({"id": "d"})

    def test_a_20_px_label_is_too_small_on_a_phone_held_sideways(self) -> None:
        result = legibility([{"id": "label", "role": "label", "px": 20}, {"id": "caption", "role": "caption", "px": 32}],
                            FRAME, DISPLAYS)
        label, caption = result["items"]
        self.assertEqual(result["smallest_display"], "phone held sideways")
        self.assertEqual(label["css_px"], {"phone held sideways": 8.79, "laptop": 13.33})
        self.assertEqual(label["needs_px_for_smallest_display"], 27.3)
        self.assertEqual(label["problems"], ["too_small_on_smallest_display"])
        self.assertEqual(caption["problems"], [])
        self.assertEqual(result["problems"], ["label: too_small_on_smallest_display"])

    def test_role_floors_are_shares_of_frame_height(self) -> None:
        result = legibility([{"id": "tiny", "role": "caption", "px": 27}], FRAME, [{"name": "desk", "width_px": 1920}])
        self.assertEqual(result["items"][0]["frame_share"], 0.025)
        self.assertEqual(result["items"][0]["problems"], ["below_role_floor"])


class Contrast(unittest.TestCase):
    def test_published_ratios(self) -> None:
        self.assertEqual(contrast_ratio("#000000", "#FFFFFF"), 21.0)
        self.assertEqual(contrast_ratio("#777777", "#ffffff"), 4.48)
        self.assertEqual(contrast_ratio("#ffffff", "#777777"), 4.48)

    def test_the_threshold_is_never_rounded(self) -> None:
        self.assertEqual(contrast_ratio("#627c77", "#ffffff"), 4.5)
        self.assertFalse(contrast_ok("#627c77", "#ffffff", px=20))

    def test_large_text_needs_three_to_one(self) -> None:
        self.assertFalse(contrast_ok("#777777", "#FFFFFF", px=20))
        self.assertTrue(contrast_ok("#777777", "#FFFFFF", px=24))
        self.assertTrue(contrast_ok("#777777", "#FFFFFF", px=19, bold=True))
        with self.assertRaises(ValueError):
            contrast_ratio("#fff", "#000000")


class AgreesWithTheAccessibilityAudit(unittest.TestCase):
    def test_contrast_matches_the_accessibility_audit_packs_recorded_ratios(self) -> None:
        packs = Path(__file__).resolve().parents[3]
        source = json.loads((packs / "accessibility-audit" / "source.json").read_text(encoding="utf-8"))
        value = next(n["value"] for n in source["nouns"] if n["slug"] == "example.contrast")
        for pair in value["pairs"]:
            expected = value["expected"][pair["id"]]
            self.assertEqual(contrast_ratio(pair["foreground"], pair["background"]), expected["ratio"], pair["id"])
            self.assertEqual(contrast_ok(pair["foreground"], pair["background"], px=16), expected["normal_text"], pair["id"])
            self.assertEqual(contrast_ok(pair["foreground"], pair["background"], px=24), expected["large_text"], pair["id"])


class Reading(unittest.TestCase):
    def test_half_a_second_plus_three_words_per_second(self) -> None:
        self.assertEqual(reading_time_s("Every claim is cited."), 1.833)
        self.assertEqual(reading_time_s("- -"), 0.5)

    def test_items_that_leave_too_soon(self) -> None:
        items = [{"id": "a", "text": "Every claim is cited.", "start_s": 2.0, "end_s": 3.5},
                 {"id": "b", "text": "Every claim is cited.", "start_s": 2.0, "end_s": 4.0},
                 {"id": "c", "text": "Background texture words", "start_s": 0.0, "end_s": 0.2, "must_read": False}]
        self.assertEqual(check_reading(items), ["a: on screen 1.5 s, needs 1.833 s to read"])


class Boxes(unittest.TestCase):
    def test_inner_ninety_percent_and_keep_outs(self) -> None:
        boxes = [{"id": "inside", "box": [200, 100, 600, 80]}, {"id": "edge", "box": [40, 500, 400, 60]},
                 {"id": "buttons", "box": [1500, 900, 300, 80]}]
        keep = [{"x": 1700, "y": 880, "width": 220, "height": 200, "label": "player controls"}]
        self.assertEqual(check_boxes(boxes, FRAME, keep_outs=keep),
                         ["edge: outside the safe area", "buttons: overlaps player controls"])


if __name__ == "__main__":
    unittest.main()
