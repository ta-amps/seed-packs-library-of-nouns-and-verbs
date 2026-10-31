"""Glyph measurement on drawn text: letter heights, polarity, colours and WCAG contrast."""

from __future__ import annotations

import unittest

import cv2
import numpy as np

from frame_qa.features import phase_shift
from frame_qa.text import CAP_EM, contrast_ratio, measure_line, srgb_luminance

from helpers import pack_nouns


def draw(text: str, scale: float, fg=(30, 30, 30), bg=(232, 240, 244), size=(900, 200), at=(40, 120), thickness=2):
    img = np.full((size[1], size[0], 3), bg, np.uint8)
    cv2.putText(img, text, at, cv2.FONT_HERSHEY_SIMPLEX, scale, fg, thickness, cv2.LINE_AA)
    return img


def det_box(img: np.ndarray, bg, pad: int):
    ys, xs = np.nonzero(np.abs(img.astype(int) - np.array(bg)).max(axis=2) > 0)
    return (int(xs.min()) - pad, int(ys.min()) - pad, int(xs.max()) + pad + 1, int(ys.max()) + pad + 1)


class Measure(unittest.TestCase):
    def test_cap_height_follows_the_drawn_size(self) -> None:
        for scale in (0.6, 1.0, 1.6, 2.4):
            img = draw("Hello World 2026", scale)
            letter = draw("H", scale)
            rows = np.nonzero((np.abs(letter.astype(int) - np.array((232, 240, 244))).max(axis=2) > 60).any(axis=1))[0]
            cap = float(rows.max() - rows.min() + 1)
            line = measure_line(img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), det_box(img, (232, 240, 244), 8))
            self.assertIsNotNone(line)
            self.assertAlmostEqual(line.cap_px, cap, delta=max(2.0, 0.15 * cap), msg=f"scale {scale}")
            self.assertAlmostEqual(line.font_px, line.cap_px / CAP_EM, places=6)

    def test_dark_and_light_text_are_measured_the_same(self) -> None:
        dark = draw("Same words here", 1.2)
        light = draw("Same words here", 1.2, fg=(240, 240, 240), bg=(40, 28, 24))
        a = measure_line(dark, cv2.cvtColor(dark, cv2.COLOR_BGR2GRAY), det_box(dark, (232, 240, 244), 8))
        b = measure_line(light, cv2.cvtColor(light, cv2.COLOR_BGR2GRAY), det_box(light, (40, 28, 24), 8))
        self.assertAlmostEqual(a.cap_px, b.cap_px, delta=1.5)
        self.assertEqual(a.box, b.box)

    def test_text_on_a_chip_is_measured_against_the_chip(self) -> None:
        # Light text on a dark chip whose detection box spills onto the light page around it.
        img = np.full((200, 900, 3), (246, 246, 246), np.uint8)
        cv2.rectangle(img, (60, 70), (620, 140), (47, 40, 37), -1)
        cv2.putText(img, "The agent drafts", (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (248, 246, 246), 2, cv2.LINE_AA)
        line = measure_line(img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (50, 60, 640, 150))
        self.assertIsNotNone(line)
        self.assertGreater(line.contrast, 10.0)
        self.assertLess(int(line.bg[1:3], 16), 80, "the background is the chip, not the page")
        self.assertGreater(line.glyphs, 8)

    def test_low_contrast_text_reads_low(self) -> None:
        img = draw("Faint words on grey", 1.2, fg=(180, 180, 180), bg=(196, 196, 196))
        line = measure_line(img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), det_box(img, (196, 196, 196), 8))
        self.assertLess(line.contrast, 1.4)

    def test_text_cut_by_the_frame_edge_is_marked(self) -> None:
        img = draw("RUNS OFF THE EDGE", 1.4, at=(600, 120))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        line = measure_line(img, gray, (590, 60, 900, 150))
        self.assertIn("right", line.edge_clipped)
        self.assertEqual(line.box[2], 900)

    def test_contrast_matches_the_accessibility_audit_packs_recorded_ratios(self) -> None:
        example = pack_nouns("accessibility-audit")["example.contrast"]
        for pair in example["pairs"]:
            fg, bg = pair["foreground"], pair["background"]
            to_bgr = lambda c: (int(c[5:7], 16), int(c[3:5], 16), int(c[1:3], 16))  # noqa: E731
            self.assertEqual(round(contrast_ratio(to_bgr(fg), to_bgr(bg)), 2), example["expected"][pair["id"]]["ratio"], pair["id"])
        self.assertAlmostEqual(srgb_luminance((255, 255, 255)), 1.0)

    def test_phase_shift_leaves_its_inputs_alone(self) -> None:
        # OpenCV 5.0's phaseCorrelate writes its window into the arrays it is given.
        rng = np.random.default_rng(7)
        a = (rng.random((90, 160)) * 255).astype(np.float32)
        b = np.roll(a, 3, axis=1)
        a0, b0 = a.copy(), b.copy()
        dx, dy, response = phase_shift(a, b)
        self.assertTrue(np.array_equal(a, a0) and np.array_equal(b, b0))
        self.assertAlmostEqual(dx, 3.0, delta=0.1)
        self.assertAlmostEqual(dy, 0.0, delta=0.1)
        self.assertGreater(response, 0.5)


if __name__ == "__main__":
    unittest.main()
