"""CLI entry point for seeded-defect-and-proof-carrying-review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .grid import load_default_grid_spec
from .mutants import SeededDefectMutantSuite
from .verifier import ProofCarryingReviewVerifier, StatisticalIntervalAuditor


def _proof_carrying_reviewer(suite: SeededDefectMutantSuite, bundle: dict[str, Any]) -> dict[str, Any]:
    failed = [c for c in suite.run_checks(bundle) if not c["passed"]]
    if failed:
        return {
            "verdict": "refuse",
            "failing_checks": [
                {"check_id": c["check_id"], "witness": c["witness"]} for c in failed
            ],
        }
    return {"verdict": "approve", "failing_checks": []}


def _rubber_stamp_reviewer(_bundle: dict[str, Any]) -> dict[str, Any]:
    return {"verdict": "approve", "failing_checks": []}


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()
    regime = bundle.get("regime")

    verifier = ProofCarryingReviewVerifier(regime=regime, spec=cfg)
    suite = verifier.suite
    auditor = verifier.auditor

    clean_bundles = list(bundle["clean_bundles"])
    strong_cal = verifier.calibrate_reviewer(
        clean_bundles, lambda cand: _proof_carrying_reviewer(suite, cand)
    )
    rubber_cal = verifier.calibrate_reviewer(clean_bundles, _rubber_stamp_reviewer)

    clean_sample = clean_bundles[0]
    unfounded_refusal = verifier.verify_review_decision(
        clean_sample,
        {
            "verdict": "refuse",
            "failing_checks": [
                {"check_id": "chk_digest_integrity", "witness": "hallucinated_mismatch"}
            ],
        },
        calibration=strong_cal,
    )
    rubber_approval = verifier.verify_review_decision(
        clean_sample,
        {"verdict": "approve", "failing_checks": []},
        calibration=rubber_cal,
    )
    valid_approval = verifier.verify_review_decision(
        clean_sample,
        {"verdict": "approve", "failing_checks": []},
        calibration=strong_cal,
    )

    sample_mutant = suite.inject_mutant(clean_sample, "silent_exception_swallow")
    valid_refusal = verifier.verify_review_decision(
        sample_mutant,
        _proof_carrying_reviewer(suite, sample_mutant),
        calibration=strong_cal,
    )

    paired = auditor.paired_bootstrap_interval(
        [float(x) for x in bundle["baseline_system_scores"]],
        [float(x) for x in bundle["candidate_system_scores"]],
        seed=int(bundle["bootstrap_seed"]),
    )

    return {
        "defect_class_count": len(suite.defect_classes),
        "generated_mutant_count": int(strong_cal["mutant_count"]),
        "strong_reviewer_status": str(strong_cal["status"]),
        "strong_mutant_kill_rate": float(strong_cal["mutant_kill_rate"]),
        "strong_clean_fpr": float(strong_cal["clean_false_positive_rate"]),
        "strong_wilson_ci_low": float(strong_cal["kill_rate_wilson_ci"]["ci_low"]),
        "strong_wilson_ci_high": float(strong_cal["kill_rate_wilson_ci"]["ci_high"]),
        "rubber_stamp_status": str(rubber_cal["status"]),
        "unfounded_refusal_accepted": bool(unfounded_refusal["accepted"]),
        "rubber_stamp_approval_accepted": bool(rubber_approval["accepted"]),
        "proof_carrying_approval_accepted": bool(valid_approval["accepted"]),
        "proof_carrying_refusal_accepted": bool(valid_refusal["accepted"]),
        "paired_bootstrap_mean_delta": float(paired["mean_delta"]),
        "paired_bootstrap_ci_low": float(paired["ci_low"]),
        "paired_bootstrap_ci_high": float(paired["ci_high"]),
        "paired_statistically_significant": bool(paired["statistically_significant_gain"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run seeded-defect-and-proof-carrying-review bundle evaluation."
    )
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    cfg = load_default_grid_spec()
    indent = int(cfg["constants"]["json_indent"])
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
