"""Unit tests for self-rewarding-and-iterative-dpo-flywheel (including AST magic-literal gate)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from iterative_rpo_flywheel import (
    IterativeRpoPairCurator,
    NodeGrid,
    PreRegisteredFlywheelPromoter,
    RubricJudgeCalibrationGate,
    ZeroHardcodedValuesAstGate,
    load_default_grid_spec,
    scan_directory_for_hardcoded_values,
)
from iterative_rpo_flywheel.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "iterative_rpo_flywheel"


class IterativeRpoFlywheelTests(unittest.TestCase):
    def test_zero_hardcoded_values_ast_gate_clean(self) -> None:
        self.assertEqual(scan_directory_for_hardcoded_values(PKG_DIR), [])
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"], f"Unexpected magic literals: {report}")
        self.assertGreaterEqual(report["files_scanned"], 6)

    def test_node_grid_requires_positive_rpo_alpha_for_made_up_pairs(self) -> None:
        grid = NodeGrid(load_default_grid_spec())
        valid = grid.resolve_regime("verified_iterative_rpo")
        self.assertTrue(grid.is_applicable(valid))
        invalid = {**valid, "allow_made_up_rubric_pairs": True, "rpo_nll_alpha": 0.0}
        self.assertFalse(grid.is_applicable(invalid))

    def test_rpo_nll_regularizer_prevents_chosen_logp_collapse_ranking_trap(self) -> None:
        healthy_pair = {
            "pair_id": "healthy",
            "prompt": "Check expected version before CAS write",
            "chosen_verified": "Verify current version matches expected version",
            "rejected_tombstone": "Write unconditionally without version check",
            "policy_logp_chosen": -3.6,
            "ref_logp_chosen": -4.0,
            "policy_logp_rejected": -12.0,
            "ref_logp_rejected": -5.0,
            "chosen_token_count": 6,
            "rejected_token_count": 6,
        }
        collapsed_pair = {
            "pair_id": "collapsed",
            "prompt": "Validate digest before promoting record",
            "chosen_verified": "Compare sha256 digest against pinned manifest",
            "rejected_tombstone": "Skip sha256 digest check entirely",
            "policy_logp_chosen": -15.0,
            "ref_logp_chosen": -4.0,
            "policy_logp_rejected": -40.0,
            "ref_logp_rejected": -5.0,
            "chosen_token_count": 6,
            "rejected_token_count": 5,
        }
        pure_dpo = IterativeRpoPairCurator(rpo_nll_alpha=0.0, min_chosen_logp_drift_per_token=-10.0)
        s_healthy_dpo = pure_dpo.score_pair(healthy_pair)
        s_collapsed_dpo = pure_dpo.score_pair(collapsed_pair)
        # Pure DPO prefers the collapsed pair because its margin (2.4) > healthy margin (0.74)!
        self.assertLess(s_collapsed_dpo["dpo_loss"], s_healthy_dpo["dpo_loss"])

        # Iterative RPO (alpha=1.0) penalizes NLL_chosen (2.5 vs 0.6) AND rejects chosen logp collapse!
        iter_rpo = IterativeRpoPairCurator(rpo_nll_alpha=1.0)
        s_healthy_rpo = iter_rpo.score_pair(healthy_pair)
        s_collapsed_rpo = iter_rpo.score_pair(collapsed_pair)
        self.assertLess(s_healthy_rpo["rpo_loss"], s_collapsed_rpo["rpo_loss"])
        self.assertTrue(s_collapsed_rpo["chosen_logp_collapsed"])

        curated = iter_rpo.curate_pairs([collapsed_pair, healthy_pair])
        self.assertEqual(curated["admitted_ids"], ["healthy"])
        self.assertEqual(curated["rejection_reasons"]["chosen_logp_collapse"], 1)

    def test_length_ratio_filter_and_three_key_deduplication(self) -> None:
        curator = IterativeRpoPairCurator()
        base = {
            "pair_id": "p-1",
            "prompt": "Verify bucket fingerprint in cuckoo table",
            "chosen_verified": "Inspect primary bucket 1 and alternate xor bucket 2 for fingerprint",
            "rejected_tombstone": "Scan every bucket linearly across table",
            "policy_logp_chosen": -4.0,
            "ref_logp_chosen": -4.5,
            "policy_logp_rejected": -12.0,
            "ref_logp_rejected": -5.0,
            "chosen_token_count": 11,
            "rejected_token_count": 7,
        }
        chosen_skeleton_clone = {
            **base,
            "pair_id": "p-skeleton-dup",
            "prompt": "Different prompt asking about alternate cuckoo bucket lookup",
            "chosen_verified": "Inspect primary bucket 8 and alternate xor bucket 9 for fingerprint",
        }
        verbose_pair = {
            **base,
            "pair_id": "p-verbose",
            "prompt": "Check single boolean flag",
            "chosen_verified": "word " * 30,
            "rejected_tombstone": "no",
            "chosen_token_count": 30,
            "rejected_token_count": 1,
        }
        res = curator.curate_pairs([base, chosen_skeleton_clone, verbose_pair])
        self.assertEqual(res["admitted_ids"], ["p-1"])
        self.assertEqual(res["rejection_reasons"]["structural_duplicate"], 1)
        self.assertEqual(res["rejection_reasons"]["length_ratio_bias"], 1)

    def test_rubric_judge_calibration_gate_blocks_high_fpr_or_low_kappa(self) -> None:
        gate = RubricJudgeCalibrationGate()
        synth = [{"pair_id": "s-1"}]
        good_records = [
            {"rubric_approved": True, "verifier_passed": True},
            {"rubric_approved": True, "verifier_passed": True},
            {"rubric_approved": True, "verifier_passed": True},
            {"rubric_approved": False, "verifier_passed": False},
            {"rubric_approved": False, "verifier_passed": False},
            {"rubric_approved": False, "verifier_passed": False},
        ]
        good_res = gate.gate_made_up_pairs(synth, good_records)
        self.assertTrue(good_res["calibration"]["calibrated"])
        self.assertEqual(good_res["calibration"]["cohens_kappa"], 1.0)
        self.assertEqual(good_res["admitted_made_up_count"], 1)

        bad_records = [
            {"rubric_approved": True, "verifier_passed": False},
            {"rubric_approved": True, "verifier_passed": True},
            {"rubric_approved": True, "verifier_passed": False},
            {"rubric_approved": False, "verifier_passed": False},
            {"rubric_approved": True, "verifier_passed": True},
            {"rubric_approved": False, "verifier_passed": True},
        ]
        bad_res = gate.gate_made_up_pairs(synth, bad_records)
        self.assertFalse(bad_res["calibration"]["calibrated"])
        self.assertEqual(bad_res["admitted_made_up_count"], 0)
        self.assertEqual(bad_res["blocked_made_up_count"], 1)

    def test_preregistered_flywheel_promoter_rejects_tampering_self_review_and_regressions(self) -> None:
        promoter = PreRegisteredFlywheelPromoter()
        suite = [
            {"id": "h1", "prompt": "alpha"},
            {"id": "h2", "prompt": "beta"},
            {"id": "h3", "prompt": "gamma"},
            {"id": "h4", "prompt": "delta"},
        ]
        lock = promoter.compute_holdout_sha256(suite)
        base_out = {"h1": True, "h2": True, "h3": False, "h4": False}
        cand_out = {"h1": True, "h2": True, "h3": True, "h4": False}
        sanity = {"s1": True, "s2": True}

        ok_res = promoter.evaluate_round(
            holdout_suite=suite,
            preregistered_holdout_sha256=lock,
            baseline_outcomes=base_out,
            candidate_outcomes=cand_out,
            sanity_outcomes=sanity,
            mean_chosen_logp_drift_per_token=0.05,
            proposer_id="worker-a",
            reviewer_id="worker-b",
        )
        self.assertTrue(ok_res["promote_round"])

        tampered = promoter.evaluate_round(
            holdout_suite=[*suite[:-1], {"id": "h4", "prompt": "tampered"}],
            preregistered_holdout_sha256=lock,
            baseline_outcomes=base_out,
            candidate_outcomes=cand_out,
            sanity_outcomes=sanity,
            mean_chosen_logp_drift_per_token=0.05,
            proposer_id="worker-a",
            reviewer_id="worker-b",
        )
        self.assertFalse(tampered["promote_round"])
        self.assertIn("holdout_sha256_mismatch", tampered["failed_gates"])

        self_rev = promoter.evaluate_round(
            holdout_suite=suite,
            preregistered_holdout_sha256=lock,
            baseline_outcomes=base_out,
            candidate_outcomes=cand_out,
            sanity_outcomes=sanity,
            mean_chosen_logp_drift_per_token=0.05,
            proposer_id="worker-same",
            reviewer_id="worker-same",
        )
        self.assertFalse(self_rev["promote_round"])
        self.assertIn("self_review_forbidden", self_rev["failed_gates"])

        regressed = promoter.evaluate_round(
            holdout_suite=suite,
            preregistered_holdout_sha256=lock,
            baseline_outcomes=base_out,
            candidate_outcomes={"h1": False, "h2": True, "h3": True, "h4": True},
            sanity_outcomes=sanity,
            mean_chosen_logp_drift_per_token=0.05,
            proposer_id="worker-a",
            reviewer_id="worker-b",
        )
        self.assertFalse(regressed["promote_round"])
        self.assertIn("regression_rate_exceeded", regressed["failed_gates"])

    def test_worked_example_recomputes_exact_receipt_and_cli_runs(self) -> None:
        src = json.loads((PACK_DIR / "source.json").read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.iterative-rpo-flywheel-bundle"]
        expected = nouns["example.iterative-rpo-flywheel-receipt"]["instance"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, expected)

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "iterative_rpo_flywheel", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(json.loads(proc.stdout), expected)


if __name__ == "__main__":
    unittest.main()
