"""Unit tests for multimodal_align."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from multimodal_align import (
    align_multimodal_timeline,
    box_iou,
    group_words_into_utterances,
    mask_intrusion_ratio,
    polygon_to_bbox_and_area,
)


class MultimodalAlignTests(unittest.TestCase):
    def test_box_iou_and_intrusion_math(self) -> None:
        self.assertEqual(box_iou([0.0, 0.0, 0.5, 0.5], [0.5, 0.5, 0.4, 0.4]), 0.0)
        self.assertAlmostEqual(box_iou([0.1, 0.1, 0.4, 0.4], [0.1, 0.1, 0.4, 0.4]), 1.0)
        self.assertAlmostEqual(mask_intrusion_ratio([0.0, 0.8, 1.0, 0.2], [0.0, 0.8, 0.5, 0.2]), 0.5)

    def test_polygon_mask_conversion_and_shoelace_area(self) -> None:
        bbox, area = polygon_to_bbox_and_area([[0.1, 0.2], [0.5, 0.2], [0.5, 0.7], [0.1, 0.7]])
        self.assertEqual(bbox, [0.1, 0.2, 0.4, 0.5])
        self.assertAlmostEqual(area, 0.2)

    def test_bottom_subject_occlusion_reroutes_caption_to_top_band(self) -> None:
        timeline = {
            "clip_id": "demo-reroute",
            "words": [
                {"word": "Inspect", "start_s": 0.0, "end_s": 0.3, "confidence": 0.95},
                {"word": "valve", "start_s": 0.32, "end_s": 0.70, "confidence": 0.93},
            ],
            "mask_frames": [
                {"t_s": 0.30, "label": "valve", "bbox": [0.10, 0.70, 0.80, 0.25], "confidence": 0.98},
            ],
        }
        report = align_multimodal_timeline(timeline, max_drift_ms=250.0, max_intrusion=0.05)
        self.assertTrue(report["ready_for_render"])
        self.assertEqual(report["placements"][0]["selected_zone_id"], "top_band")
        self.assertEqual(report["placements"][0]["max_intrusion_ratio"], 0.0)
        self.assertEqual(report["av_sync_events"][0]["av_offset_ms"], 20.0)

    def test_audio_visual_drift_violation_flagged(self) -> None:
        timeline = {
            "clip_id": "drift-case",
            "words": [
                {"word": "sensor", "start_s": 2.40, "end_s": 2.80, "confidence": 0.91},
            ],
            "mask_frames": [
                {"t_s": 1.50, "label": "sensor", "bbox": [0.35, 0.35, 0.20, 0.20]},
            ],
        }
        report = align_multimodal_timeline(timeline, max_drift_ms=250.0)
        self.assertEqual(report["av_drift_violations"], 1)
        self.assertFalse(report["ready_for_render"])
        self.assertTrue(report["av_sync_events"][0]["drift_exceeded"])

    def test_pixel_coordinates_and_hud_exclusions_normalized(self) -> None:
        timeline = {
            "clip_id": "pixel-coords",
            "frame_width": 1080,
            "frame_height": 1920,
            "hud_exclusion_boxes": [[0, 1450, 1080, 470]],
            "words": [{"word": "Testing", "start_s": 0.0, "end_s": 0.4, "confidence": 0.62}],
            "mask_frames": [{"t_s": 0.1, "label": "subject", "bbox": [300, 700, 480, 500]}],
        }
        report = align_multimodal_timeline(timeline, min_word_confidence=0.70)
        self.assertEqual(report["placements"][0]["selected_zone_id"], "top_band")
        self.assertEqual(report["placements"][0]["low_confidence_words"], ["Testing"])

    def test_invalid_word_timing_rejected(self) -> None:
        with self.assertRaises(ValueError):
            group_words_into_utterances([{"word": "bad", "start_s": 2.0, "end_s": 1.5}])

    def test_cli_align_deterministic(self) -> None:
        code_dir = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            tpath = Path(tmp) / "timeline.json"
            tpath.write_text(
                json.dumps(
                    {
                        "clip_id": "cli-01",
                        "words": [{"word": "panel", "start_s": 0.5, "end_s": 0.9, "confidence": 0.99}],
                        "mask_frames": [{"t_s": 0.45, "label": "panel", "bbox": [0.3, 0.3, 0.3, 0.3]}],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "multimodal_align", "align", str(tpath)],
                cwd=code_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            parsed = json.loads(proc.stdout)
            self.assertTrue(parsed["ready_for_render"])
            self.assertEqual(parsed["placements"][0]["selected_zone_id"], "bottom_band")


if __name__ == "__main__":
    unittest.main()
