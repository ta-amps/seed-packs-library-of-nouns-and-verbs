"""Contrast ratios against published reference values, compositing, sizes and thresholds."""

from __future__ import annotations

import unittest

from a11y_checks.contrast import (LARGE_BOLD_PX, check_pair, composite, format_ratio, is_large_text, parse_color,
                                  ratio_of)


class Ratios(unittest.TestCase):
    def test_published_reference_values(self) -> None:
        for fg, bg, expected in (("#ffffff", "#000000", 21.0), ("#767676", "#ffffff", 4.54), ("#777777", "#ffffff", 4.48),
                                 ("#0000ff", "#ffffff", 8.59), ("#ffff00", "#ffffff", 1.07), ("#123456", "#123456", 1.0)):
            self.assertEqual(check_pair(fg, bg)["ratio"], expected, (fg, bg))

    def test_order_does_not_matter(self) -> None:
        self.assertEqual(ratio_of(parse_color("#336699"), parse_color("#f0f0f0")),
                         ratio_of(parse_color("#f0f0f0"), parse_color("#336699")))

    def test_pass_uses_the_unrounded_ratio(self) -> None:
        near = check_pair("#777777", "#ffffff", size_px=16)
        self.assertFalse(near["passes"])
        self.assertEqual(near["required"], 4.5)
        self.assertTrue(check_pair("#767676", "#ffffff", size_px=16)["passes"])

    def test_large_text_threshold(self) -> None:
        self.assertTrue(is_large_text(24))
        self.assertFalse(is_large_text(23.9))
        self.assertTrue(is_large_text(18.67, 700))
        self.assertFalse(is_large_text(18.66, 700))
        self.assertFalse(is_large_text(20, 600))
        self.assertAlmostEqual(LARGE_BOLD_PX, 18.6667, places=3)
        large = check_pair("#949494", "#ffffff", size_px=24)
        self.assertTrue(large["large_text"])
        self.assertEqual(large["required"], 3.0)
        self.assertTrue(large["passes"])
        self.assertFalse(check_pair("#949494", "#ffffff", size_px=16)["passes"])

    def test_unknown_size_is_judged_as_normal_text(self) -> None:
        result = check_pair("#949494", "#ffffff")
        self.assertFalse(result["size_known"])
        self.assertFalse(result["large_text"])
        self.assertEqual(result["required"], 4.5)

    def test_enhanced_level_is_reported_separately(self) -> None:
        result = check_pair("#767676", "#ffffff", size_px=16)
        self.assertTrue(result["passes"])
        self.assertEqual(result["enhanced"], {"sc": "1.4.6", "level": "AAA", "required": 7.0, "passes": False})
        self.assertTrue(check_pair("#595959", "#ffffff", size_px=16)["enhanced"]["passes"])

    def test_non_text_contrast(self) -> None:
        result = check_pair("#949494", "#ffffff", kind="non_text")
        self.assertEqual((result["sc"], result["required"]), ("1.4.11", 3.0))
        self.assertTrue(result["passes"])
        self.assertFalse(check_pair("#cccccc", "#ffffff", kind="non_text")["passes"])

    def test_format(self) -> None:
        self.assertEqual(format_ratio(4.5421), "4.54:1")


class Colors(unittest.TestCase):
    def test_syntaxes_agree(self) -> None:
        for text in ("#336699", "#369", "rgb(51, 102, 153)", "rgb(51 102 153)", "rgba(51,102,153,1)", "#336699ff", "#369f",
                     "rgb(20% 40% 60%)"):
            self.assertEqual(parse_color(text)[:3], (51, 102, 153), text)
            self.assertEqual(parse_color(text)[3], 1.0, text)
        self.assertEqual(parse_color("white"), (255, 255, 255, 1.0))
        self.assertEqual(parse_color("transparent")[3], 0.0)

    def test_alpha_is_composited_over_the_background(self) -> None:
        half = composite(parse_color("rgba(0, 0, 0, 0.5)"), parse_color("#ffffff"))
        self.assertEqual(half, (127.5, 127.5, 127.5, 1.0))
        result = check_pair("rgba(0, 0, 0, 0.5)", "#ffffff")
        self.assertEqual(result["foreground"], "#808080")
        self.assertEqual(result["ratio"], round(ratio_of(half, parse_color("#ffffff")), 2))
        self.assertEqual(check_pair("rgb(0 0 0 / 0.5)", "#ffffff")["ratio"], result["ratio"])

    def test_transparent_background_falls_back_to_the_canvas(self) -> None:
        self.assertEqual(check_pair("#000000", "transparent")["ratio"], 21.0)
        self.assertEqual(check_pair("#ffffff", "transparent", canvas="#000000")["ratio"], 21.0)

    def test_bad_colors_fail_loudly(self) -> None:
        for text in ("", "#12", "#gggggg", "rgb(300, 0, 0)", "rgb(1, 2)", "blue", "hsl(0 0% 0%)"):
            with self.assertRaises(ValueError, msg=text):
                parse_color(text)
        with self.assertRaises(ValueError):
            check_pair("#000", "#fff", kind="logo")


if __name__ == "__main__":
    unittest.main()
