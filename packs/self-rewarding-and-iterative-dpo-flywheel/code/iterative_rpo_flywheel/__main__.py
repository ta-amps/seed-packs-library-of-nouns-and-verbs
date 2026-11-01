"""CLI entry point for self-rewarding-and-iterative-dpo-flywheel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .calibration_and_promotion import PreRegisteredFlywheelPromoter, RubricJudgeCalibrationGate
from .grid import load_default_grid_spec
from .rpo_curator import IterativeRpoPairCurator


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()

    cal_gate = RubricJudgeCalibrationGate(spec=cfg)
    calibrated_gate = cal_gate.gate_synthetic_pairs(
        list(bundle["synthetic_pairs"]),
        list(bundle["calibrated_judge_records"]),
    )
    uncalibrated_gate = cal_gate.gate_synthetic_pairs(
        list(bundle["synthetic_pairs"]),
        list(bundle["uncalibrated_judge_records"]),
    )

    curator = IterativeRpoPairCurator(spec=cfg)
    combined_candidates = list(bundle["verified_candidates"]) + calibrated_gate["admitted_synthetic_pairs"]
    curated = curator.curate_pairs(combined_candidates)

    promoter = PreRegisteredFlywheelPromoter(spec=cfg)
    holdout_suite = list(bundle["holdout_suite"])
    expected_sha = str(
        bundle.get(
            "preregistered_holdout_sha256",
            promoter.compute_holdout_sha256(holdout_suite),
        )
    )
    admitted_drifts = [p["chosen_logp_drift_per_token"] for p in curated["admitted_pairs"]]
    mean_drift = sum(admitted_drifts) / float(max(1, len(admitted_drifts))) if admitted_drifts else 0.0

    promo = promoter.evaluate_round(
        holdout_suite=holdout_suite,
        preregistered_holdout_sha256=expected_sha,
        baseline_outcomes=dict(bundle["baseline_outcomes"]),
        candidate_outcomes=dict(bundle["candidate_outcomes"]),
        sanity_outcomes=dict(bundle["sanity_outcomes"]),
        mean_chosen_logp_drift_per_token=mean_drift,
        proposer_id=str(bundle["proposer_id"]),
        reviewer_id=str(bundle["reviewer_id"]),
    )

    return {
        "calibrated_judge_kappa": calibrated_gate["calibration"]["cohens_kappa"],
        "calibrated_judge_fpr": calibrated_gate["calibration"]["false_positive_approval_rate"],
        "calibrated_judge_passed": calibrated_gate["calibration"]["calibrated"],
        "uncalibrated_judge_kappa": uncalibrated_gate["calibration"]["cohens_kappa"],
        "uncalibrated_synthetic_admitted": uncalibrated_gate["admitted_synthetic_count"],
        "admitted_pair_ids": curated["admitted_ids"],
        "admitted_pair_count": curated["admitted_count"],
        "rejected_length_bias_count": curated["rejection_reasons"]["length_ratio_bias"],
        "rejected_logp_collapse_count": curated["rejection_reasons"]["chosen_logp_collapse"],
        "rejected_duplicate_count": curated["rejection_reasons"]["structural_duplicate"],
        "mean_dpo_margin": curated["mean_dpo_margin"],
        "mean_rpo_loss": curated["mean_rpo_loss"],
        "holdout_lock_valid": promo["holdout_lock_valid"],
        "net_holdout_gain": promo["net_holdout_gain"],
        "regression_rate": promo["regression_rate"],
        "sanity_retention_rate": promo["sanity_retention_rate"],
        "promote_round": promo["promote_round"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run self-rewarding-and-iterative-dpo-flywheel bundle evaluation."
    )
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    cfg = load_default_grid_spec()
    indent = int(cfg["formatting"]["json_indent"])
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
