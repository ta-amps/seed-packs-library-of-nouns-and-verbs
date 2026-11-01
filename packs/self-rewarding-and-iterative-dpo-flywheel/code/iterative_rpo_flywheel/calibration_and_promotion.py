"""Self-rewarding rubric judge calibration gate and pre-registered holdout flywheel promoter."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .grid import NodeGrid, load_default_grid_spec


class RubricJudgeCalibrationGate:
    """Calibrates self-rewarding rubric judges against deterministic ground-truth verifiers."""

    def __init__(
        self,
        *,
        min_calibration_samples: int | None = None,
        min_cohens_kappa: float | None = None,
        min_exact_agreement: float | None = None,
        max_false_positive_rate: float | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        grid = NodeGrid(cfg)
        num = cfg["numerics"]
        cg = cfg["calibration_gate"]

        self._eps = float(num["epsilon"])
        self._round_digits = int(num["round_digits"])

        clamped = grid.clamp_cell({
            "min_cohens_kappa": (
                min_cohens_kappa if min_cohens_kappa is not None else cg["min_cohens_kappa"]
            ),
            "max_false_positive_rate": (
                max_false_positive_rate
                if max_false_positive_rate is not None
                else cg["max_false_positive_rate"]
            ),
        })
        self.min_calibration_samples = int(
            min_calibration_samples
            if min_calibration_samples is not None
            else cg["min_calibration_samples"]
        )
        self.min_cohens_kappa = float(clamped["min_cohens_kappa"])
        self.min_exact_agreement = float(
            min_exact_agreement if min_exact_agreement is not None else cg["min_exact_agreement"]
        )
        self.max_false_positive_rate = float(clamped["max_false_positive_rate"])

    def evaluate_judge(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute Cohen's kappa, exact agreement and false-positive approval rate against ground truth."""
        total = len(records)
        if total == 0:
            return {
                "sample_count": 0,
                "exact_agreement": 0.0,
                "cohens_kappa": 0.0,
                "false_positive_approval_rate": 1.0,
                "calibrated": False,
            }

        tp = 0
        tn = 0
        fp = 0
        fn = 0
        for row in records:
            rubric_ok = bool(row["rubric_approved"])
            verifier_ok = bool(row["verifier_passed"])
            if rubric_ok and verifier_ok:
                tp += 1
            elif (not rubric_ok) and (not verifier_ok):
                tn += 1
            elif rubric_ok and (not verifier_ok):
                fp += 1
            else:
                fn += 1

        n_float = float(total)
        exact = float(tp + tn) / n_float
        p_rubric_pos = float(tp + fp) / n_float
        p_rubric_neg = float(tn + fn) / n_float
        p_ver_pos = float(tp + fn) / n_float
        p_ver_neg = float(tn + fp) / n_float
        p_expected = p_rubric_pos * p_ver_pos + p_rubric_neg * p_ver_neg

        denom = 1.0 - p_expected
        if denom <= self._eps:
            kappa = 1.0 if exact >= 1.0 - self._eps else 0.0
        else:
            kappa = (exact - p_expected) / denom

        neg_ground_truth = fp + tn
        fpr = float(fp) / float(max(1, neg_ground_truth)) if neg_ground_truth > 0 else 0.0

        calibrated = (
            total >= self.min_calibration_samples
            and kappa >= self.min_cohens_kappa
            and exact >= self.min_exact_agreement
            and fpr <= self.max_false_positive_rate
        )
        return {
            "sample_count": total,
            "exact_agreement": round(exact, self._round_digits),
            "cohens_kappa": round(kappa, self._round_digits),
            "false_positive_approval_rate": round(fpr, self._round_digits),
            "calibrated": calibrated,
        }

    def gate_synthetic_pairs(
        self,
        synthetic_pairs: list[dict[str, Any]],
        calibration_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Admit synthetic rubric-judged preference pairs only when the judge passes calibration."""
        cal_report = self.evaluate_judge(calibration_records)
        admitted = list(synthetic_pairs) if cal_report["calibrated"] else []
        return {
            "calibration": cal_report,
            "admitted_synthetic_pairs": admitted,
            "admitted_synthetic_count": len(admitted),
            "blocked_synthetic_count": len(synthetic_pairs) - len(admitted),
        }


class PreRegisteredFlywheelPromoter:
    """Evaluates iterative preference rounds against SHA-256 holdout locks, sanity bounds and regression caps."""

    def __init__(
        self,
        *,
        min_sanity_retention: float | None = None,
        max_regression_rate: float | None = None,
        min_holdout_gain: float | None = None,
        min_chosen_logp_drift_per_token: float | None = None,
        require_distinct_reviewer: bool | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        num = cfg["numerics"]
        fp = cfg["flywheel_promoter"]

        self._round_digits = int(num["round_digits"])
        self.min_sanity_retention = float(
            min_sanity_retention if min_sanity_retention is not None else fp["min_sanity_retention"]
        )
        self.max_regression_rate = float(
            max_regression_rate if max_regression_rate is not None else fp["max_regression_rate"]
        )
        self.min_holdout_gain = float(
            min_holdout_gain if min_holdout_gain is not None else fp["min_holdout_gain"]
        )
        self.min_chosen_logp_drift_per_token = float(
            min_chosen_logp_drift_per_token
            if min_chosen_logp_drift_per_token is not None
            else fp["min_chosen_logp_drift_per_token"]
        )
        self.require_distinct_reviewer = bool(
            require_distinct_reviewer
            if require_distinct_reviewer is not None
            else fp["require_distinct_reviewer"]
        )

    @staticmethod
    def compute_holdout_sha256(holdout_suite: list[dict[str, Any]]) -> str:
        canonical_items = sorted(
            [{"id": str(item["id"]), "prompt": str(item["prompt"])} for item in holdout_suite],
            key=lambda row: row["id"],
        )
        raw = json.dumps(canonical_items, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def evaluate_round(
        self,
        *,
        holdout_suite: list[dict[str, Any]],
        preregistered_holdout_sha256: str,
        baseline_outcomes: dict[str, bool],
        candidate_outcomes: dict[str, bool],
        sanity_outcomes: dict[str, bool],
        mean_chosen_logp_drift_per_token: float,
        proposer_id: str,
        reviewer_id: str,
    ) -> dict[str, Any]:
        """Verify holdout SHA-256 lock, sanity retention, regression ceiling and reviewer separation."""
        computed_sha = self.compute_holdout_sha256(holdout_suite)
        lock_valid = computed_sha == str(preregistered_holdout_sha256)
        distinct_ok = (not self.require_distinct_reviewer) or (
            bool(proposer_id.strip())
            and bool(reviewer_id.strip())
            and proposer_id.strip() != reviewer_id.strip()
        )

        holdout_ids = [str(item["id"]) for item in holdout_suite]
        n_holdout = max(1, len(holdout_ids))
        base_passes = sum(1 for hid in holdout_ids if bool(baseline_outcomes.get(hid, False)))
        cand_passes = sum(1 for hid in holdout_ids if bool(candidate_outcomes.get(hid, False)))
        regressions = sum(
            1
            for hid in holdout_ids
            if bool(baseline_outcomes.get(hid, False)) and (not bool(candidate_outcomes.get(hid, False)))
        )

        base_rate = float(base_passes) / float(n_holdout)
        cand_rate = float(cand_passes) / float(n_holdout)
        net_gain = cand_rate - base_rate
        reg_rate = float(regressions) / float(n_holdout)

        n_sanity = max(1, len(sanity_outcomes))
        sanity_rate = (
            float(sum(1 for ok in sanity_outcomes.values() if bool(ok))) / float(n_sanity)
            if sanity_outcomes
            else 0.0
        )
        no_logp_collapse = float(mean_chosen_logp_drift_per_token) >= self.min_chosen_logp_drift_per_token

        failed_gates: list[str] = []
        if not lock_valid:
            failed_gates.append("holdout_sha256_mismatch")
        if not distinct_ok:
            failed_gates.append("self_review_forbidden")
        if sanity_rate < self.min_sanity_retention:
            failed_gates.append("sanity_retention_below_floor")
        if reg_rate > self.max_regression_rate:
            failed_gates.append("regression_rate_exceeded")
        if net_gain < self.min_holdout_gain:
            failed_gates.append("insufficient_holdout_gain")
        if not no_logp_collapse:
            failed_gates.append("chosen_logp_collapse_detected")

        return {
            "holdout_sha256": computed_sha,
            "holdout_lock_valid": lock_valid,
            "distinct_reviewer_valid": distinct_ok,
            "baseline_holdout_rate": round(base_rate, self._round_digits),
            "candidate_holdout_rate": round(cand_rate, self._round_digits),
            "net_holdout_gain": round(net_gain, self._round_digits),
            "regression_rate": round(reg_rate, self._round_digits),
            "sanity_retention_rate": round(sanity_rate, self._round_digits),
            "promote_round": len(failed_gates) == 0,
            "failed_gates": failed_gates,
        }
