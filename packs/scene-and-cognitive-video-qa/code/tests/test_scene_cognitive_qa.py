"""Unit and worked-example tests for scene-and-cognitive-video-qa."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from scene_cognitive_qa import (
    compile_scene_cognitive_report,
    evaluate_camera_and_slide_stability,
    evaluate_frosted_caption_geometry,
    evaluate_live_web_journey_provenance,
    evaluate_reading_speed_and_cognitive_load,
    evaluate_shot_dwell_and_transitions,
    wrap_caption_clauses,
)

SOURCE_JSON = Path(__file__).resolve().parents[2] / "source.json"


class SceneCognitiveQATests(unittest.TestCase):
    def test_recomputes_worked_example_from_source_json(self) -> None:
        source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n for n in source["nouns"]}
        bundle = nouns["example.scene-cognitive-bundle"]["value"]
        expected = nouns["example.qa-report"]["value"]["instance"]

        r_dwell = evaluate_shot_dwell_and_transitions(bundle["shots"], bundle["transitions"])
        r_cam = evaluate_camera_and_slide_stability(bundle["scene_tracks"])
        r_cog = evaluate_reading_speed_and_cognitive_load(bundle["text_items"], bundle["speech_cues"])
        r_web = evaluate_live_web_journey_provenance(bundle["journeys"])
        r_cap = evaluate_frosted_caption_geometry(bundle["caption_band"], bundle["caption_cues"])
        report = compile_scene_cognitive_report(
            media_sha256=bundle["media_sha256"],
            dwell_and_transitions=r_dwell,
            slide_stability=r_cam,
            cognitive_load=r_cog,
            web_provenance=r_web,
            caption_geometry=r_cap,
        )
        self.assertEqual(report, expected)

    def test_clean_video_bundle_passes_all_five_evaluators(self) -> None:
        r_dwell = evaluate_shot_dwell_and_transitions(
            shots=[
                {"id": "shot01", "start_s": 0.0, "end_s": 4.9, "has_stage_text": True},
                {"id": "shot02", "start_s": 4.9, "end_s": 10.6, "has_stage_text": True},
            ],
            transitions=[{"from_shot": "shot01", "to_shot": "shot02", "kind": "cut", "frames": 0}],
        )
        self.assertEqual(r_dwell["verdict"], "pass")
        self.assertEqual(r_dwell["flash_shots"], 0)
        self.assertEqual(r_dwell["ghost_transitions"], 0)

        r_cam = evaluate_camera_and_slide_stability([
            {
                "id": "shot02-static",
                "scene_kind": "static_slide",
                "has_focal_target": False,
                "samples": [
                    {"t_s": 4.9, "scale": 1.0, "tx_px": 0.0, "ty_px": 0.0},
                    {"t_s": 10.6, "scale": 1.0, "tx_px": 0.0, "ty_px": 0.0},
                ],
            }
        ])
        self.assertEqual(r_cam["verdict"], "pass")

        r_cog = evaluate_reading_speed_and_cognitive_load(
            text_items=[
                {
                    "id": "hero-headline",
                    "text": "Spare capacity for community intake work.",
                    "start_s": 4.9,
                    "end_s": 10.4,
                    "must_read": True,
                }
            ],
            speech_cues=[
                {
                    "id": "c1",
                    "text": "Spare capacity helps community groups finish intake work.",
                    "start_s": 5.0,
                    "end_s": 9.8,
                }
            ],
        )
        self.assertEqual(r_cog["verdict"], "pass")

        r_web = evaluate_live_web_journey_provenance([
            {
                "id": "homepage-to-intake",
                "viewport_width_px": 1440,
                "has_browser_chrome": True,
                "shows_entry_landing": True,
                "shows_click_transition": True,
                "navigated_urls": ["https://example.org/", "https://example.org/intake"],
                "form_submitted": False,
            }
        ])
        self.assertEqual(r_web["verdict"], "pass")

        wrapped = "\n".join(wrap_caption_clauses(
            "It reuses checked pieces from seed packs, and tests the kit on synthetic cases."
        ))
        r_cap = evaluate_frosted_caption_geometry(
            caption_band={
                "burned_into_video": True,
                "uses_native_track_in_fullscreen": False,
                "has_frosted_glass_pill": True,
                "rounded_radius_px": 18.0,
                "pill_center_x": 960.0,
                "pill_center_y": 1002.0,
                "pill_top_y": 948.0,
                "pill_bottom_y": 1056.0,
                "pill_left_x": 380.0,
                "pill_right_x": 1540.0,
            },
            cues=[{"id": "c1", "text": wrapped}],
        )
        self.assertEqual(r_cap["verdict"], "pass")

        report = compile_scene_cognitive_report(
            media_sha256="a" * 64,
            dwell_and_transitions=r_dwell,
            slide_stability=r_cam,
            cognitive_load=r_cog,
            web_provenance=r_web,
            caption_geometry=r_cap,
        )
        self.assertEqual(report["overall_verdict"], "pass")

    def test_wrap_caption_clauses_breaks_at_comma_and_avoids_orphans(self) -> None:
        lines = wrap_caption_clauses(
            "It reuses checked pieces from seed packs, and tests the kit on made-up cases.",
            max_chars=42,
        )
        self.assertEqual(
            lines,
            [
                "It reuses checked pieces from seed packs,",
                "and tests the kit on made-up cases.",
            ],
        )
        short = wrap_caption_clauses("Spare capacity for good.", max_chars=42)
        self.assertEqual(short, ["Spare capacity for good."])


if __name__ == "__main__":
    unittest.main()
