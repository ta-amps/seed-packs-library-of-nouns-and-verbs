"""Proof-carrying review verifier and statistical confidence interval auditor."""

from __future__ import annotations

import math
import random
from statistics import NormalDist
from typing import Any, Callable

from .grid import resolve_grid_cell
from .mutants import SeededDefectMutantSuite


class StatisticalIntervalAuditor:
    """Computes exact Wilson score intervals and deterministic paired bootstrap intervals."""

    def __init__(
        self,
        *,
        overrides: dict[str, Any] | None = None,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.grid, self.cell, self.constants = resolve_grid_cell(
            overrides, regime=regime, spec=spec
        )
        self.confidence_level: float = float(self.cell["confidence_level"])
        self.bootstrap_resamples: int = int(self.cell["bootstrap_resamples"])
        self.half_divisor: float = float(self.constants["wilson_half_divisor"])
        self.quarter_factor: float = float(self.constants["wilson_quarter_factor"])
        self.default_seed: int = int(self.constants["default_bootstrap_seed"])
        self.practical_margin: float = float(self.constants["practical_delta_margin"])
        self.round_digits: int = int(self.constants["round_digits"])

    def wilson_score_interval(
        self,
        successes: int,
        trials: int,
        *,
        confidence_level: float | None = None,
    ) -> dict[str, Any]:
        """Compute exact Wilson score confidence interval for binomial proportion successes/trials."""
        if trials < 0 or successes < 0 or successes > trials:
            raise ValueError(f"invalid binomial counts: successes={successes}, trials={trials}")
        conf = float(confidence_level if confidence_level is not None else self.confidence_level)
        if trials == 0:
            return {
                "point_estimate": 0.0,
                "ci_low": 0.0,
                "ci_high": 1.0,
                "confidence_level": conf,
                "trials": 0,
            }
        z = NormalDist().inv_cdf((1.0 + conf) / self.half_divisor)
        z_sq = z * z
        n = float(trials)
        p_hat = float(successes) / n
        denom = 1.0 + z_sq / n
        center = (p_hat + z_sq / (self.half_divisor * n)) / denom
        radicand = (p_hat * (1.0 - p_hat) / n) + (z_sq / (self.quarter_factor * n * n))
        margin = (z * math.sqrt(max(0.0, radicand))) / denom
        low = max(0.0, center - margin)
        high = min(1.0, center + margin)
        return {
            "point_estimate": round(p_hat, self.round_digits),
            "ci_low": round(low, self.round_digits),
            "ci_high": round(high, self.round_digits),
            "confidence_level": conf,
            "trials": trials,
        }

    def paired_bootstrap_interval(
        self,
        baseline_scores: list[float],
        candidate_scores: list[float],
        *,
        confidence_level: float | None = None,
        resamples: int | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Compute deterministic paired bootstrap CI for mean(candidate - baseline)."""
        if len(baseline_scores) != len(candidate_scores) or not baseline_scores:
            raise ValueError("baseline_scores and candidate_scores must have equal non-zero length")
        conf = float(confidence_level if confidence_level is not None else self.confidence_level)
        b_count = int(resamples if resamples is not None else self.bootstrap_resamples)
        rng_seed = int(seed if seed is not None else self.default_seed)

        n = len(baseline_scores)
        deltas = [float(c) - float(b) for b, c in zip(baseline_scores, candidate_scores)]
        observed_mean = sum(deltas) / float(n)

        rng = random.Random(rng_seed)
        boot_means: list[float] = []
        indices = list(range(n))
        for _ in range(b_count):
            sample_total = 0.0
            for _ in range(n):
                sample_total += deltas[rng.choice(indices)]
            boot_means.append(sample_total / float(n))
        boot_means.sort()

        alpha = 1.0 - conf
        lower_q = alpha / self.half_divisor
        upper_q = 1.0 - lower_q
        low_idx = max(0, min(b_count - 1, int(math.floor(lower_q * float(b_count)))))
        high_idx = max(0, min(b_count - 1, int(math.ceil(upper_q * float(b_count)) - 1)))
        ci_low = boot_means[low_idx]
        ci_high = boot_means[high_idx]

        wins = sum(1 for d in deltas if d > 0.0)
        losses = sum(1 for d in deltas if d < 0.0)
        ties = n - wins - losses

        return {
            "paired_n": n,
            "mean_delta": round(observed_mean, self.round_digits),
            "ci_low": round(ci_low, self.round_digits),
            "ci_high": round(ci_high, self.round_digits),
            "confidence_level": conf,
            "resamples": b_count,
            "wins": wins,
            "ties": ties,
            "losses": losses,
            "statistically_significant_gain": ci_low > self.practical_margin,
        }


class ProofCarryingReviewVerifier:
    """Enforces 'no refusal without a failing check; no approval without mutant kill threshold'."""

    def __init__(
        self,
        *,
        overrides: dict[str, Any] | None = None,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.grid, self.cell, self.constants = resolve_grid_cell(
            overrides, regime=regime, spec=spec
        )
        self.suite = SeededDefectMutantSuite(overrides=overrides, regime=regime, spec=spec)
        self.auditor = StatisticalIntervalAuditor(overrides=overrides, regime=regime, spec=spec)
        self.min_kill_rate: float = float(self.cell["min_mutant_kill_rate"])
        self.max_clean_fpr: float = float(self.cell["max_clean_false_positive_rate"])
        self.require_witness_match: bool = bool(self.cell["require_witness_substring_match"])
        self.round_digits: int = int(self.constants["round_digits"])

    def calibrate_reviewer(
        self,
        clean_bundles: list[dict[str, Any]],
        reviewer_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Measure reviewer sensitivity and specificity across clean twins and 6-class seeded mutants."""
        mutants = self.suite.generate_twin_suite(clean_bundles)
        clean_fp = 0
        for clean in clean_bundles:
            rev = reviewer_fn(clean)
            if str(rev.get("verdict")) != "approve":
                clean_fp += 1

        kills = 0
        per_class_totals: dict[str, int] = {d: 0 for d in self.suite.defect_classes}
        per_class_kills: dict[str, int] = {d: 0 for d in self.suite.defect_classes}

        for mrec in mutants:
            dclass = str(mrec["defect_class"])
            per_class_totals[dclass] += 1
            rev = reviewer_fn(mrec["bundle"])
            check_eval = self.verify_review_decision(
                mrec["bundle"],
                rev,
                calibration={"mutant_kill_rate": 1.0, "clean_false_positive_rate": 0.0},
            )
            if str(rev.get("verdict")) == "refuse" and bool(check_eval["valid_proof"]):
                kills += 1
                per_class_kills[dclass] += 1

        clean_n = len(clean_bundles)
        mut_n = len(mutants)
        fpr = (float(clean_fp) / float(clean_n)) if clean_n > 0 else 0.0
        specificity = 1.0 - fpr
        sensitivity = (float(kills) / float(mut_n)) if mut_n > 0 else 0.0
        kill_ci = self.auditor.wilson_score_interval(kills, mut_n)

        eligible = sensitivity >= self.min_kill_rate and fpr <= self.max_clean_fpr
        status = (
            "trusted_reviewer"
            if eligible
            else ("overstrict_clean_rejector" if fpr > self.max_clean_fpr else "under_sensitive_reviewer")
        )
        return {
            "status": status,
            "eligible_to_approve": eligible,
            "clean_count": clean_n,
            "mutant_count": mut_n,
            "mutant_kills": kills,
            "mutant_kill_rate": round(sensitivity, self.round_digits),
            "clean_false_positive_rate": round(fpr, self.round_digits),
            "specificity": round(specificity, self.round_digits),
            "youden_j": round(sensitivity + specificity - 1.0, self.round_digits),
            "kill_rate_wilson_ci": kill_ci,
            "per_class_kill_rates": {
                k: round(float(per_class_kills[k]) / float(per_class_totals[k]), self.round_digits)
                if per_class_totals[k] > 0
                else 0.0
                for k in self.suite.defect_classes
            },
        }

    def verify_review_decision(
        self,
        candidate: dict[str, Any],
        review_submission: dict[str, Any],
        *,
        calibration: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify that a refusal proves a failing check or an approval clears checks + kill rate."""
        verdict = str(review_submission.get("verdict", ""))
        ground_checks = {c["check_id"]: c for c in self.suite.run_checks(candidate)}
        actual_failures = [cid for cid, c in ground_checks.items() if not c["passed"]]

        if verdict == "refuse":
            cited = list(review_submission.get("failing_checks", []))
            if not cited:
                return {
                    "accepted": False,
                    "valid_proof": False,
                    "reason": "refusal_missing_failing_check_witness",
                    "verified_failing_checks": [],
                }
            verified_ids: list[str] = []
            for item in cited:
                cid = str(item.get("check_id", ""))
                witness = str(item.get("witness", ""))
                if cid not in ground_checks:
                    return {
                        "accepted": False,
                        "valid_proof": False,
                        "reason": f"unknown_check_id:{cid}",
                        "verified_failing_checks": [],
                    }
                actual = ground_checks[cid]
                if actual["passed"]:
                    return {
                        "accepted": False,
                        "valid_proof": False,
                        "reason": f"unfounded_refusal_check_passed:{cid}",
                        "verified_failing_checks": [],
                    }
                if self.require_witness_match and (not witness or witness not in actual["witness"]):
                    return {
                        "accepted": False,
                        "valid_proof": False,
                        "reason": f"unreproducible_witness:{cid}",
                        "verified_failing_checks": [],
                    }
                verified_ids.append(cid)
            return {
                "accepted": True,
                "valid_proof": True,
                "reason": "verified_proof_carrying_refusal",
                "verified_failing_checks": verified_ids,
            }

        if verdict == "approve":
            if actual_failures:
                return {
                    "accepted": False,
                    "valid_proof": False,
                    "reason": "approval_blocked_by_failing_checks",
                    "verified_failing_checks": actual_failures,
                }
            kill_rate = float(calibration.get("mutant_kill_rate", 0.0))
            clean_fpr = float(calibration.get("clean_false_positive_rate", 1.0))
            if kill_rate < self.min_kill_rate:
                return {
                    "accepted": False,
                    "valid_proof": False,
                    "reason": f"reviewer_below_mutant_kill_threshold:{kill_rate}<{self.min_kill_rate}",
                    "verified_failing_checks": [],
                }
            if clean_fpr > self.max_clean_fpr:
                return {
                    "accepted": False,
                    "valid_proof": False,
                    "reason": f"reviewer_exceeds_clean_fpr_bound:{clean_fpr}>{self.max_clean_fpr}",
                    "verified_failing_checks": [],
                }
            return {
                "accepted": True,
                "valid_proof": True,
                "reason": "verified_proof_carrying_approval",
                "verified_failing_checks": [],
            }

        return {
            "accepted": False,
            "valid_proof": False,
            "reason": f"invalid_verdict:{verdict}",
            "verified_failing_checks": [],
        }
