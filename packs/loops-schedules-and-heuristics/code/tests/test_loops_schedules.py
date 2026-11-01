"""Unit tests for loops-schedules-and-heuristics (including self-conformance AST gate)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from loops_schedules import (
    BanditAntiStallLoopAndResourceHeuristic,
    DeclarativeScheduleAndCadenceCompiler,
    SwappableLearnerAdvisors,
    ZeroHardcodedValuesAstGate,
)
from loops_schedules.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "loops_schedules"


class LoopsSchedulesTests(unittest.TestCase):
    def test_package_passes_zero_hardcoded_values_ast_gate(self) -> None:
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"], f"Unexpected magic literals in loops_schedules: {report}")
        self.assertEqual(report["violation_count"], 0)

    def test_declarative_schedule_compiler_urgency_and_aimd(self) -> None:
        compiler = DeclarativeScheduleAndCadenceCompiler()
        with self.assertRaises(ValueError):
            compiler.evaluate_schedule_window(
                {"schedule_id": "bad_daemon", "auto_enqueued": True},
                now_epoch_seconds=3600,
            )

        sched = {
            "schedule_id": "freshness_audit",
            "auto_enqueued": False,
            "cadence_seconds": 3600,
            "max_jitter_seconds": 0,
            "due_window_width_seconds": 300,
            "stop_at_epoch_seconds": 72000,
            "consecutive_low_yield_windows": 0,
        }
        in_win = compiler.evaluate_schedule_window(sched, now_epoch_seconds=3610)
        self.assertTrue(in_win["due"])
        self.assertFalse(in_win["auto_enqueued"])
        self.assertEqual(in_win["idempotency_key"], "schedule:freshness_audit:1970-01-01T01:00:00Z")

        # Same window yields identical idempotency_key
        in_win_repeat = compiler.evaluate_schedule_window(sched, now_epoch_seconds=3700)
        self.assertEqual(in_win["idempotency_key"], in_win_repeat["idempotency_key"])

        # Outside due window performs zero storage I/O
        out_win = compiler.evaluate_schedule_window(sched, now_epoch_seconds=5000)
        self.assertFalse(out_win["due"])
        self.assertEqual(out_win["storage_io_ops"], 0)

        # Past stop_at deadline refuses execution with zero storage I/O
        past_stop = compiler.evaluate_schedule_window(sched, now_epoch_seconds=72000)
        self.assertFalse(past_stop["due"])
        self.assertEqual(past_stop["reason"], "past_stop_at_deadline")
        self.assertEqual(past_stop["storage_io_ops"], 0)

        # Low-yield exponential backoff doubles effective cadence (3600 -> 7200)
        backed_off = compiler.evaluate_schedule_window(
            {**sched, "consecutive_low_yield_windows": 1},
            now_epoch_seconds=7210,
        )
        self.assertEqual(backed_off["effective_cadence_seconds"], 7200)

        # systemd --user inert template generation
        units = compiler.render_systemd_user_units(sched)
        self.assertIn("Type=oneshot", units["service_unit"])
        self.assertIn("OnUnitActiveSec=3600s", units["timer_unit"])

        # Fragility Half-Life Urgency: age == half_life => freshness == 0.5, urgency == importance * 0.5
        ranked = compiler.rank_fragility_urgency(
            [
                {"item_id": "fresh_low", "age_hours": 1.0, "half_life_hours": 24.0, "importance": 0.5},
                {"item_id": "stale_critical", "age_hours": 24.0, "half_life_hours": 24.0, "importance": 1.0},
            ]
        )
        self.assertEqual(ranked[0]["item_id"], "stale_critical")
        self.assertAlmostEqual(ranked[0]["freshness"], 0.5, places=6)
        self.assertAlmostEqual(ranked[0]["urgency"], 0.5, places=6)

        # AIMD Claim Pacing: additive increase yielded to fair-share cap, multiplicative decrease on latency spike
        inc = compiler.step_aimd_claim_pacing(
            current_concurrency=4,
            prev_ewma_latency_ms=300.0,
            observed_latency_ms=300.0,
            total_pool_slots=16,
            active_peer_workers=4,
        )
        self.assertEqual(inc["pacing_action"], "additive_increase")
        self.assertTrue(inc["fair_share_yielded"])
        self.assertEqual(inc["next_concurrency"], 4)

        dec = compiler.step_aimd_claim_pacing(
            current_concurrency=8,
            prev_ewma_latency_ms=900.0,
            observed_latency_ms=1400.0,
            total_pool_slots=32,
            active_peer_workers=2,
        )
        self.assertEqual(dec["pacing_action"], "multiplicative_decrease")
        self.assertEqual(dec["next_concurrency"], 4)

    def test_bandit_anti_stall_and_seven_tier_compute_cascade(self) -> None:
        engine = BanditAntiStallLoopAndResourceHeuristic()
        res = engine.select_arm_and_anti_stall(
            arms=[
                {"arm_id": "arm_dead", "pulls": 2, "reward_sum": 2.0, "signature": "tombstone:dead01"},
                {"arm_id": "arm_proven", "pulls": 10, "reward_sum": 9.0},
                {"arm_id": "arm_weak", "pulls": 10, "reward_sum": 1.0},
            ],
            consecutive_zero_yield_waves=3,
            base_query="validate envelope schema",
            negative_tombstones=["tombstone:dead01"],
        )
        self.assertEqual(res["suppressed_arm_ids"], ["arm_dead"])
        self.assertEqual(res["selected_arm_id"], "arm_proven")
        self.assertTrue(res["plateau_detected"])
        self.assertNotEqual(res["effective_query"], "validate envelope schema")

        # Deterministic task selects 0_code_shim ($0)
        t0 = engine.select_compute_tier(
            {
                "deterministic_eligible": True,
                "required_capability_rank": 1,
                "required_context_tokens": 2048,
                "required_tpm": 1000,
                "estimated_total_tokens": 5000,
                "remaining_spend_cap_usd": 0.0,
                "privacy_tier": "confidential",
            }
        )
        self.assertEqual(t0["selected_tier"], "0_code_shim")

        # Confidential + capability 4 + 32k context skips 0_code_shim (non-deterministic),
        # 1_local_edge_small (cap 2, ctx 16k), and 2_free_dual_t4_batch (max_privacy internal, cap 3),
        # selecting 3_serverless_gpu_credit!
        t3 = engine.select_compute_tier(
            {
                "deterministic_eligible": False,
                "required_capability_rank": 4,
                "required_context_tokens": 32000,
                "required_tpm": 100000,
                "estimated_total_tokens": 10000,
                "remaining_spend_cap_usd": 0.05,
                "privacy_tier": "confidential",
            }
        )
        self.assertEqual(t3["selected_tier"], "3_serverless_gpu_credit")

    def test_six_swappable_learner_advisors(self) -> None:
        advisors = SwappableLearnerAdvisors()
        l1 = advisors.phrasing_acceptance_uplift(
            {"baseline_trials": 10, "baseline_accepts": 5, "candidate_trials": 10, "candidate_accepts": 9}
        )
        self.assertTrue(l1["advice_only"])
        self.assertTrue(l1["keep_baseline_valid"])
        self.assertEqual(l1["recommendation"], "adopt_candidate_phrasing")

        l2 = advisors.searchability_scent_ranker(
            [
                {"candidate_id": "concise_exact", "text": "fencing token cas retry procedure"},
                {"candidate_id": "vague_filler", "text": "general notes and miscellaneous items"},
            ],
            ["fencing token cas"],
        )
        self.assertEqual(l2["top_candidate_id"], "concise_exact")

        l3 = advisors.shim_injection_matched_uplift(
            [{"pairs": 20, "unshimmed_pass_rate": 0.60, "shimmed_pass_rate": 0.80, "extra_shim_tokens": 100}]
        )
        self.assertEqual(l3["recommendation"], "retain_shim")

        l4 = advisors.decomposition_split_breakeven(
            {"single_pass_prob": 0.45, "subtask_pass_prob": 0.90, "subtask_count": 2}
        )
        self.assertEqual(l4["recommendation"], "split_into_dag")

        l5 = advisors.pairwise_taste_bradley_terry(
            [
                {"winner": "variant_a", "loser": "variant_b"},
                {"winner": "variant_a", "loser": "variant_b"},
                {"winner": "variant_b", "loser": "variant_c"},
            ]
        )
        self.assertEqual(l5["top_item"], "variant_a")

        l6 = advisors.rights_cleared_training_manifest(
            [
                {
                    "trace_id": "tr.contrib",
                    "task_family_id": "fam_a",
                    "contributor_restricted": True,
                    "privacy_tier": "public",
                    "license": "MIT",
                },
                {
                    "trace_id": "tr.private",
                    "task_family_id": "fam_b",
                    "contributor_restricted": False,
                    "privacy_tier": "confidential",
                    "license": "MIT",
                },
                {
                    "trace_id": "tr.clean_1",
                    "task_family_id": "fam_clean_alpha",
                    "contributor_restricted": False,
                    "privacy_tier": "public",
                    "license": "MIT",
                },
                {
                    "trace_id": "tr.clean_2",
                    "task_family_id": "fam_clean_alpha",
                    "contributor_restricted": False,
                    "privacy_tier": "public",
                    "license": "Apache-2.0",
                },
            ]
        )
        self.assertEqual(l6["blocked_trace_ids"], ["tr.contrib", "tr.private"])
        self.assertEqual(l6["family_overlap_count"], 0)

    def test_worked_example_and_cli_roundtrip(self) -> None:
        src_path = PACK_DIR / "source.json"
        if not src_path.exists():
            return
        src = json.loads(src_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.loops-schedules-bundle"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, nouns["example.loops-schedules-receipt"]["instance"])

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "loops_schedules", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(json.loads(proc.stdout), recomputed)


if __name__ == "__main__":
    unittest.main()
