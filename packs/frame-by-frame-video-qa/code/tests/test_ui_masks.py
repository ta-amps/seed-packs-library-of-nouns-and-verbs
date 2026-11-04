"""Tests for connected-component UI segmentation, optional Meta SAM mask adapter, and UI occlusion hits."""

from __future__ import annotations

import unittest

import numpy as np

from frame_qa.ui_masks import (
    SAM_MODEL_ID,
    SamMaskAdapter,
     _segment_stdlib,
    detect_ui_mask_occlusions,
    segment_ui_regions,
)


def _made_up_ui_frame() -> np.ndarray:
    """1280x720 dark-slate frame with a content panel, an input bar, and a primary CTA button."""
    frame = np.full((720, 1280, 3), (24, 28, 36), dtype=np.uint8)
    # Main card panel: [120, 90, 820, 520]
    frame[90:520, 120:820] = (242, 244, 248)
    # Search input bar: [860, 110, 1180, 148]
    frame[110:148, 860:1180] = (235, 238, 245)
    # Bottom CTA button inside lower caption zone: [540, 620, 740, 668]
    frame[620:668, 540:740] = (46, 125, 246)
    return frame


class UIMasksTest(unittest.TestCase):
    def test_connected_components_segments_panel_input_and_button(self) -> None:
        frame = _made_up_ui_frame()
        regions = segment_ui_regions(frame, min_area_px=300)
        roles = {r.role for r in regions}
        self.assertIn("panel", roles)
        self.assertIn("input", roles)
        self.assertIn("button", roles)
        button = next(r for r in regions if r.role == "button")
        self.assertEqual(button.box, (540, 620, 740, 668))

    def test_stdlib_fallback_segments_without_numpy_array(self) -> None:
        small = [[[20, 24, 30] for _ in range(120)] for _ in range(80)]
        for y in range(52, 70):
            for x in range(35, 85):
                small[y][x] = [50, 140, 250]
        regions = _segment_stdlib(small, min_area_px=100)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].box, (35, 52, 85, 70))
        self.assertEqual(regions[0].source, "connected_components_stdlib")

    def test_sam_adapter_falls_back_cleanly_when_unconfigured(self) -> None:
        frame = _made_up_ui_frame()
        adapter = SamMaskAdapter(model_id=SAM_MODEL_ID, local_model_path="/nonexistent/local/sam")
        self.assertFalse(adapter.sam_available())
        regions, backend = adapter.segment(frame)
        self.assertEqual(backend, "connected_components")
        self.assertGreaterEqual(len(regions), 3)

    def test_sam_adapter_normalizes_sam_masks_and_flags_caption_occlusion(self) -> None:
        frame = _made_up_ui_frame()
        mask_btn = np.zeros((720, 1280), dtype=bool)
        mask_btn[620:668, 540:740] = True
        mask_input = np.zeros((720, 1280), dtype=bool)
        mask_input[110:148, 860:1180] = True

        def fake_sam_predictor(_arr: np.ndarray):
            return [
                {"segmentation": mask_btn, "predicted_iou": 0.96},
                {"segmentation": mask_input, "predicted_iou": 0.93},
            ]

        adapter = SamMaskAdapter(model_id=SAM_MODEL_ID, predictor=fake_sam_predictor)
        self.assertTrue(adapter.sam_available())
        regions, backend = adapter.segment(frame)
        self.assertEqual(backend, f"sam:{SAM_MODEL_ID}")
        self.assertEqual(len(regions), 2)

        overlays = [
            {"id": "cue-04", "kind": "caption", "box": [420, 610, 860, 680]},
            {"id": "chip-02", "kind": "callout", "box": [850, 108, 940, 146]},
        ]
        hits = detect_ui_mask_occlusions(regions, overlays, min_cover_share=0.15, major_cover_share=0.35)
        by_kind = {h["kind"]: h for h in hits}
        self.assertIn("caption_obscures_ui", by_kind)
        self.assertEqual(by_kind["caption_obscures_ui"]["severity"], "major")
        self.assertAlmostEqual(by_kind["caption_obscures_ui"]["covered_share"], 1.0, places=3)
        self.assertIn("callout_obscures_ui", by_kind)
        self.assertEqual(by_kind["callout_obscures_ui"]["region_role"], "input")


if __name__ == "__main__":
    unittest.main()
