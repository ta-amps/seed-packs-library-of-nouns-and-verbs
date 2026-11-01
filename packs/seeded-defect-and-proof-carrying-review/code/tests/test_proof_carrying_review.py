"""Unit tests for seeded-defect-and-proof-carrying-review (including AST magic-literal gate)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from proof_carrying_review import (
    NodeGrid,
    ProofCarryingReviewVerifier,
    SeededDefectMutantSuite,
    StatisticalIntervalAuditor,
    ZeroHardcodedValuesAstGate,
    canonical_sha256,
    scan_directory_for_hardcoded_values,
)
from proof_carrying_review.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "proof_carrying_review"


def _make_clean_bundle(bundle_id: str = "cand-01") -> dict:
    payload = {"record": bundle_id, "verified": True}
    return {
        "bundle_id": bundle_id,
        "artifact": {
            "payload": payload,
            "declared_sha256": canonical_sha256(payload),
        },
        "boundary": {
            "observed": 8,
            "max_allowed": 8,
        },
        "code_snippet": "def compute_total(items: list[int]) -> int:\n    return sum(items)\n",
        "capability": {
            "requested_effect": "write-internal",
            "granted_ceiling": "write-internal",
        },
        "attestation": {
            "drafter_principal": "worker:drafter-01",
            "drafter_key_id": "key_drafter_01",
            "reviewer_principal": "worker:reviewer-02",
            "reviewer_key_id": "key_reviewer_02",
        },
        "sources": {
            "src-1": "All candidate outputs carry deterministic SHA-256 content pins and witness IDs."
        },
        "citations": [
            {
                "source_id": "src-1",
                "exact_quote": "deterministic SHA-256 content pins",
            }
        ],
    }


class ProofCarryingReviewTests(unittest.TestCase):
    def test_zero_hardcoded_values_ast_gate_clean(self) -> None:
        violations = scan_directory_for_hardcoded_values(PKG_DIR)
        self.assertEqual(violations, [], f"Unexpected magic literals: {violations}")
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"])
        self.assertGreaterEqual(report["files_scanned"], 6)

        bad_scan = ZeroHardcodedValuesAstGate.scan_source("def bad_ci() -> float:\n    return 1.96\n")
        self.assertFalse(bad_scan["passed"])

    def test_node_grid_constraints_and_auto_expansion(self) -> None:
        grid = NodeGrid()
        self.assertFalse(
            grid.is_applicable(
                {
                    "min_mutant_kill_rate": 0.85,
                    "max_clean_false_positive_rate": 0.0,
                    "confidence_level": 0.99,
                    "bootstrap_resamples": 200,
                    "require_witness_substring_match": True,
                }
            )
        )
        expanded, axes = grid.auto_expand_if_saturated({"bootstrap_resamples": 2000})
        self.assertEqual(expanded.generation, 2)
        self.assertEqual(axes, ["bootstrap_resamples:high->4000"])

    def test_all_six_seeded_defect_classes_caught_by_targeted_checks_and_clean_passes(self) -> None:
        suite = SeededDefectMutantSuite()
        clean = _make_clean_bundle("clean-alpha")
        clean_checks = suite.run_checks(clean)
        self.assertTrue(all(c["passed"] for c in clean_checks))

        twins = suite.generate_twin_suite([clean])
        self.assertEqual(len(twins), 6)
        for mrec in twins:
            checks = {c["check_id"]: c for c in suite.run_checks(mrec["bundle"])}
            expected_cid = mrec["expected_failing_check"]
            self.assertFalse(checks[expected_cid]["passed"], mrec["defect_class"])
            self.assertTrue(bool(checks[expected_cid]["witness"]))
            other_failed = [cid for cid, c in checks.items() if not c["passed"] and cid != expected_cid]
            self.assertEqual(other_failed, [], f"Mutant {mrec['defect_class']} leaked into {other_failed}")

    def test_proof_carrying_verifier_rejects_unfounded_refusal_and_rubber_stamp_approval(self) -> None:
        verifier = ProofCarryingReviewVerifier(regime="release_admission_gate")
        suite = verifier.suite
        clean = _make_clean_bundle("clean-beta")

        cal_strong = verifier.calibrate_reviewer(
            [clean],
            lambda b: (
                {
                    "verdict": "refuse",
                    "failing_checks": [
                        {"check_id": c["check_id"], "witness": c["witness"]}
                        for c in suite.run_checks(b)
                        if not c["passed"]
                    ],
                }
                if any(not c["passed"] for c in suite.run_checks(b))
                else {"verdict": "approve", "failing_checks": []}
            ),
        )
        self.assertEqual(cal_strong["status"], "trusted_reviewer")
        self.assertEqual(cal_strong["mutant_kill_rate"], 1.0)
        self.assertEqual(cal_strong["clean_false_positive_rate"], 0.0)

        # Unfounded refusal without failing check
        empty_refusal = verifier.verify_review_decision(
            clean, {"verdict": "refuse", "failing_checks": []}, calibration=cal_strong
        )
        self.assertFalse(empty_refusal["accepted"])

        # Unfounded refusal citing a passing check
        bogus_refusal = verifier.verify_review_decision(
            clean,
            {
                "verdict": "refuse",
                "failing_checks": [{"check_id": "chk_boundary_invariant", "witness": "observed=9>max_allowed=8"}],
            },
            calibration=cal_strong,
        )
        self.assertFalse(bogus_refusal["accepted"])
        self.assertIn("unfounded_refusal_check_passed", bogus_refusal["reason"])

        # Rubber-stamp approver rejected despite clean candidate
        cal_rubber = verifier.calibrate_reviewer(
            [clean], lambda _b: {"verdict": "approve", "failing_checks": []}
        )
        self.assertEqual(cal_rubber["mutant_kill_rate"], 0.0)
        rubber_dec = verifier.verify_review_decision(
            clean, {"verdict": "approve", "failing_checks": []}, calibration=cal_rubber
        )
        self.assertFalse(rubber_dec["accepted"])
        self.assertIn("reviewer_below_mutant_kill_threshold", rubber_dec["reason"])

    def test_wilson_score_and_paired_bootstrap_intervals_exact_and_deterministic(self) -> None:
        auditor = StatisticalIntervalAuditor()
        w_perfect = auditor.wilson_score_interval(12, 12, confidence_level=0.95)
        self.assertEqual(w_perfect["point_estimate"], 1.0)
        self.assertEqual(w_perfect["ci_high"], 1.0)
        self.assertGreater(w_perfect["ci_low"], 0.75)
        self.assertLess(w_perfect["ci_low"], 0.76)

        w_zero = auditor.wilson_score_interval(0, 12, confidence_level=0.95)
        self.assertEqual(w_zero["ci_low"], 0.0)
        self.assertAlmostEqual(w_zero["ci_high"], round(1.0 - w_perfect["ci_low"], 4), places=3)

        base = [0.60, 0.62, 0.58, 0.65, 0.61, 0.59, 0.63, 0.60]
        cand = [0.78, 0.80, 0.77, 0.82, 0.79, 0.76, 0.81, 0.79]
        b1 = auditor.paired_bootstrap_interval(base, cand, seed=42)
        b2 = auditor.paired_bootstrap_interval(base, cand, seed=42)
        self.assertEqual(b1, b2)
        self.assertTrue(b1["statistically_significant_gain"])
        self.assertGreater(b1["ci_low"], 0.15)

    def test_worked_example_recomputes_exact_receipt_and_cli_runs(self) -> None:
        source_path = PACK_DIR / "source.json"
        if not source_path.exists():
            return
        src = json.loads(source_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.proof-carrying-review-bundle"]
        expected = nouns["example.proof-carrying-review-receipt"]["instance"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, expected)

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "proof_carrying_review", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out, expected)


if __name__ == "__main__":
    unittest.main()
