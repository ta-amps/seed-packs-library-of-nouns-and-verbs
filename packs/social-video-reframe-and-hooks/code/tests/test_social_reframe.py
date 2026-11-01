"""Unit tests for social_reframe (standard library only)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from social_reframe import (
    build_cutdown_plan,
    check_claim_preservation,
    plan_crop_trajectory,
    reflow_captions,
    score_hook_beats,
)


class SocialReframeTests(unittest.TestCase):
    def test_crop_trajectory_clamps_bounds_and_deadband(self) -> None:
        keyframes = [
            {"time_s": 0.0, "subject_bbox": [800, 200, 320, 600], "critical_regions": [[820, 220, 280, 560]]},
            {"time_s": 0.5, "subject_bbox": [812, 205, 320, 600], "critical_regions": [[820, 220, 280, 560]]},
            {"time_s": 1.0, "subject_bbox": [1700, 200, 200, 600], "critical_regions": []},
        ]
        res = plan_crop_trajectory(keyframes, src_w=1920, src_h=1080, aspect="9:16", deadband_px=36.0, max_pan_px_per_sec=400.0)
        self.assertEqual(res["crop_size"], [608, 1080])
        # Second keyframe shifted by only +12px (< 36px deadband), so crop_x stays identical.
        self.assertEqual(res["keyframes"][0]["crop_x"], res["keyframes"][1]["crop_x"])
        # Third keyframe pan step is velocity-clamped to <= 200px over 0.5s.
        self.assertLessEqual(abs(res["keyframes"][2]["crop_x"] - res["keyframes"][1]["crop_x"]), 201)
        for row in res["keyframes"]:
            self.assertGreaterEqual(row["crop_x"], 0)
            self.assertLessEqual(row["crop_x"] + row["crop_w"], 1920)

    def test_wide_critical_table_triggers_pillarbox_fallback(self) -> None:
        keyframes = [
            {"time_s": 2.0, "subject_bbox": [200, 180, 1400, 500], "critical_regions": [[200, 180, 1400, 500]]}
        ]
        res = plan_crop_trajectory(keyframes, aspect="9:16")
        self.assertFalse(res["all_subjects_safe"])
        self.assertEqual(res["keyframes"][0]["framing_mode"], "pillarbox_inset")
        self.assertGreaterEqual(len(res["clip_violations"]), 1)

    def test_square_aspect_crop_size(self) -> None:
        keyframes = [{"time_s": 0.0, "subject_bbox": [700, 200, 400, 400]}]
        res = plan_crop_trajectory(keyframes, src_w=1920, src_h=1080, aspect="1:1")
        self.assertEqual(res["crop_size"], [1080, 1080])
        self.assertTrue(res["all_subjects_safe"])

    def test_hook_scoring_penalizes_filler_and_rewards_concrete_outcome(self) -> None:
        beats = [
            {
                "beat_id": "intro-splash",
                "start_s": 0.0,
                "end_s": 3.5,
                "visual_change_score": 0.3,
                "audio_clarity_score": 0.8,
                "concrete_outcome_shown": False,
                "filler_opening": True,
            },
            {
                "beat_id": "live-demo-result",
                "start_s": 14.0,
                "end_s": 17.5,
                "visual_change_score": 0.85,
                "audio_clarity_score": 0.9,
                "concrete_outcome_shown": True,
                "filler_opening": False,
            },
        ]
        ranked = score_hook_beats(beats, max_hook_seconds=5.0)
        self.assertEqual(ranked[0]["beat_id"], "live-demo-result")
        self.assertTrue(ranked[0]["eligible_opening_hook"])
        self.assertFalse(ranked[1]["eligible_opening_hook"])
        self.assertEqual(ranked[1]["disqualifier"], "filler_opening")

    def test_caption_reflow_flags_excessive_reading_speed_and_shifts_safe_band(self) -> None:
        cues = [
            {"cue_id": "c1", "start_s": 0.0, "end_s": 3.0, "text": "Warm cache latency dropped to 42ms.", "lower_band_occupied": True},
            {
                "cue_id": "c2",
                "start_s": 3.0,
                "end_s": 3.5,
                "text": "This sentence is much too long to be read comfortably inside half a second by any viewer.",
            },
        ]
        out = reflow_captions(cues, aspect="9:16", max_chars_per_line=28, max_cps=18.0)
        self.assertFalse(out["all_cues_valid"])
        self.assertTrue(out["cues"][0]["valid"])
        self.assertLess(out["cues"][0]["anchor_y_frac"], 0.30)
        self.assertFalse(out["cues"][1]["valid"])

    def test_claim_preservation_blocks_dropped_qualifier(self) -> None:
        source_claims = [
            {
                "claim_id": "CLM-1",
                "headline_phrase": "42ms median latency",
                "required_qualifiers": ["warm cache", "synthetic workload"],
                "evidence_timestamp_s": 15.0,
            }
        ]
        bad_gate = check_claim_preservation(
            source_claims,
            retained_segments=[{"start_s": 14.0, "end_s": 18.0}],
            cutdown_captions=[{"start_s": 0.0, "end_s": 3.0, "text": "We achieved 42ms median latency in our warm cache test."}],
        )
        self.assertFalse(bad_gate["claim_preservation_passed"])
        self.assertEqual(bad_gate["violations"][0]["dropped_qualifiers"], ["synthetic workload"])

        good_gate = check_claim_preservation(
            source_claims,
            retained_segments=[{"start_s": 14.0, "end_s": 18.0}],
            cutdown_captions=[{"start_s": 0.0, "end_s": 4.0, "text": "42ms median latency on a warm cache synthetic workload."}],
        )
        self.assertTrue(good_gate["claim_preservation_passed"])

    def test_cli_end_to_end(self) -> None:
        spec = {
            "source_width": 1920,
            "source_height": 1080,
            "keyframes": [{"time_s": 0.0, "subject_bbox": [750, 200, 420, 620]}],
            "candidate_beats": [
                {
                    "beat_id": "b1",
                    "start_s": 4.0,
                    "end_s": 7.5,
                    "visual_change_score": 0.9,
                    "audio_clarity_score": 0.85,
                    "concrete_outcome_shown": True,
                }
            ],
            "retained_segments": [{"start_s": 4.0, "end_s": 12.0}],
            "captions": [{"cue_id": "q1", "start_s": 0.0, "end_s": 3.5, "text": "2x throughput on local SQLite fixture."}],
            "source_claims": [
                {
                    "claim_id": "c1",
                    "headline_phrase": "2x throughput",
                    "required_qualifiers": ["local sqlite fixture"],
                    "evidence_timestamp_s": 6.0,
                }
            ],
        }
        expected = build_cutdown_plan(spec, aspect="9:16")
        self.assertTrue(expected["ready_for_render"])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "spec.json"
            p.write_text(json.dumps(spec), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "social_reframe", "plan", str(p), "--aspect", "9:16"],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(json.loads(proc.stdout), expected)


if __name__ == "__main__":
    unittest.main()
