"""Unit tests and worked-example recomputation for parametric_composer."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from parametric_composer.camera import (
    plan_product_hub_trajectory,
    project_point_3d,
    quintic_ease,
    sample_trajectory,
)
from parametric_composer.layout import (
    CAPTION_BAND_BOX,
    STAGE_SAFE_BOX,
    compute_browser_chrome_layout,
    verify_safe_area_and_caption_band,
)
from parametric_composer.transitions import (
    compute_card_aura,
    interpolate_edge_packet,
    validate_zero_double_exposure,
)

PACK_SOURCE = Path(__file__).resolve().parents[2] / "source.json"


class ParametricComposerTest(unittest.TestCase):
    def test_1x3_and_2x2_product_hub_trajectories_and_projection(self) -> None:
        self.assertEqual(quintic_ease(0.0), 0.0)
        self.assertEqual(quintic_ease(1.0), 1.0)
        self.assertAlmostEqual(quintic_ease(0.5), 0.5, places=6)

        plan_1x3 = plan_product_hub_trajectory("1x3", ["ingest", "verify", "report"])
        phases = [s["phase"] for s in plan_1x3["segments"]]
        self.assertEqual(phases[0], "overview")
        self.assertIn("pillar_focus", phases)
        self.assertIn("bridge_zoom_out", phases)
        self.assertEqual(phases[-1], "finale_hub")

        # At t=0 (overview), all 3 cards project inside STAGE_SAFE_BOX
        pose0 = sample_trajectory(plan_1x3, 0.5)
        for card in plan_1x3["cards"]:
            x0, y0, x1, y1 = card["box"]
            p_tl = project_point_3d((x0, y0, 0.0), pose0)
            p_br = project_point_3d((x1, y1, 0.0), pose0)
            self.assertGreaterEqual(p_tl[0], STAGE_SAFE_BOX[0])
            self.assertLessEqual(p_br[0], STAGE_SAFE_BOX[2])
            self.assertGreaterEqual(p_tl[1], STAGE_SAFE_BOX[1])
            self.assertLessEqual(p_br[1], STAGE_SAFE_BOX[3])

        plan_2x2 = plan_product_hub_trajectory("2x2")
        self.assertEqual(len(plan_2x2["cards"]), 4)
        self.assertEqual(plan_2x2["segments"][-1]["phase"], "finale_hub")

    def test_browser_chrome_and_safe_area_caption_band_collisions(self) -> None:
        chrome = compute_browser_chrome_layout([160, 92, 1760, 796], ["Hub", "Detectors", "Receipts"], active_tab_index=1)
        self.assertEqual(len(chrome["traffic_lights"]), 3)
        self.assertEqual(len(chrome["tabs"]), 3)
        self.assertTrue(chrome["tabs"][1]["active"])
        self.assertEqual(chrome["viewport_box"], [162, 174, 1758, 794])

        clean = verify_safe_area_and_caption_band([
            {"id": "browser-main", "role": "browser", "box": chrome["outer_box"]},
            {"id": "cue-01", "role": "caption", "box": [240, 868, 1680, 964]},
        ])
        self.assertTrue(clean["valid"])
        self.assertEqual(clean["violations"], [])

        bad = verify_safe_area_and_caption_band([
            {"id": "low-card", "role": "card", "box": [200, 620, 900, 890]},
            {"id": "bad-caption", "role": "caption", "box": [40, 800, 1880, 900]},
        ])
        self.assertFalse(bad["valid"])
        kinds = {v["kind"] for v in bad["violations"]}
        self.assertIn("caption_band_collision", kinds)
        self.assertIn("outside_safe_stage", kinds)
        self.assertIn("caption_outside_band", kinds)
        self.assertEqual(CAPTION_BAND_BOX, (0, 836, 1920, 1080))

    def test_zero_double_exposure_and_aura_packet_curves(self) -> None:
        shots = [
            {"id": "s1", "has_text": True, "has_ui_chrome": True},
            {"id": "s2", "has_text": True, "has_ui_chrome": False},
            {"id": "s3", "has_text": False, "has_ui_chrome": False},
        ]
        bad_tr = validate_zero_double_exposure(shots, [
            {"from_shot": "s1", "to_shot": "s2", "kind": "crossfade", "duration_s": 0.5},
            {"from_shot": "s2", "to_shot": "s3", "kind": "crossfade", "duration_s": 0.5},
        ])
        self.assertFalse(bad_tr["valid"])
        self.assertEqual(len(bad_tr["violations"]), 1)
        self.assertEqual(bad_tr["violations"][0]["kind"], "double_exposure_text_crossfade")

        good_tr = validate_zero_double_exposure(shots, [
            {"from_shot": "s1", "to_shot": "s2", "kind": "camera_move", "duration_s": 0.9},
            {"from_shot": "s2", "to_shot": "s3", "kind": "hard_cut", "duration_s": 0.0},
        ])
        self.assertTrue(good_tr["valid"])

        p0 = interpolate_edge_packet((400.0, 440.0), (960.0, 440.0), 0.0)
        pm = interpolate_edge_packet((400.0, 440.0), (960.0, 440.0), 0.5, curvature_px=30.0)
        p1 = interpolate_edge_packet((400.0, 440.0), (960.0, 440.0), 1.0)
        self.assertEqual(p0["opacity"], 0.0)
        self.assertEqual(p1["opacity"], 0.0)
        self.assertGreater(pm["opacity"], 0.5)
        self.assertNotEqual(pm["y"], 440.0)

        aura = compute_card_aura(1.0, focused=True, ceiling_opacity=0.22)
        self.assertLessEqual(aura["opacity"], 0.22)

    def test_pack_worked_example_recomputes_exactly(self) -> None:
        source = json.loads(PACK_SOURCE.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in source["nouns"]}
        inp = nouns["example.hub-scene-spec"]
        expected = nouns["example.composition-check"]["instance"]

        traj = plan_product_hub_trajectory(inp["grid_mode"], inp["pillar_ids"])
        chrome = compute_browser_chrome_layout(inp["browser_outer_box"], inp["browser_tabs"])
        layout_res = verify_safe_area_and_caption_band(inp["elements"])
        trans_res = validate_zero_double_exposure(inp["shots"], inp["transitions"])

        self.assertEqual(traj["total_duration_s"], expected["trajectory_duration_s"])
        self.assertEqual(len(traj["segments"]), expected["segment_count"])
        self.assertEqual(chrome["viewport_box"], expected["browser_viewport_box"])
        self.assertEqual(layout_res["valid"], expected["layout_valid"])
        self.assertEqual(len(layout_res["violations"]), expected["layout_violation_count"])
        self.assertEqual(trans_res["valid"], expected["transitions_valid"])
        self.assertEqual(len(trans_res["violations"]), expected["transition_violation_count"])


if __name__ == "__main__":
    unittest.main()
