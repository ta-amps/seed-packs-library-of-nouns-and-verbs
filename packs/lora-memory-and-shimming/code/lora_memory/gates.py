"""Pre-registered holdout paired bootstrap CI promotion gates for LoRA adapters and shims."""

from __future__ import annotations

import math
import random
from typing import Any, Sequence


def _percentile(sorted_vals: Sequence[float], pct: float) -> float:
    pos = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(math.floor(pos))
    hi = min(len(sorted_vals) - 1, lo + 1)
    frac = pos - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)


def paired_bootstrap_ci(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    n_bootstrap: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, float]:
    """Compute seeded paired bootstrap mean difference (`candidate - baseline`) and `(1-alpha)` CI."""
    if len(baseline) != len(candidate) or len(baseline) < 2:
        raise ValueError("baseline and candidate must have matching length >= 2")
    n = len(baseline)
    diffs = [float(c) - float(b) for b, c in zip(baseline, candidate)]
    mean_diff = sum(diffs) / n

    rng = random.Random(seed)
    boot_means: list[float] = []
    for _ in range(max(100, n_bootstrap)):
        acc = 0.0
        for _ in range(n):
            acc += diffs[rng.randrange(n)]
        boot_means.append(acc / n)
    boot_means.sort()

    lo_pct = 100.0 * (alpha * 0.5)
    hi_pct = 100.0 * (1.0 - alpha * 0.5)
    return {
        "mean_delta": round(mean_diff, 4),
        "ci_low": round(_percentile(boot_means, lo_pct), 4),
        "ci_high": round(_percentile(boot_means, hi_pct), 4),
    }


def evaluate_promotion_gate(
    *,
    target_baseline: Sequence[float],
    target_candidate: Sequence[float],
    retention_baseline: Sequence[float],
    retention_candidate: Sequence[float],
    candidate_hallucination_flags: Sequence[int | bool],
    n_bootstrap: int = 1000,
    seed: int = 42,
    min_target_gain_ci_low: float = 0.05,
    max_retention_drop: float = 0.015,
    max_hallucination_rate: float = 0.02,
) -> dict[str, Any]:
    """Evaluate pre-registered holdout promotion gate across target gain, capability retention and hallucinations."""
    if not candidate_hallucination_flags:
        raise ValueError("candidate_hallucination_flags must be non-empty")

    target_ci = paired_bootstrap_ci(target_baseline, target_candidate, n_bootstrap=n_bootstrap, seed=seed)
    ret_ci = paired_bootstrap_ci(retention_baseline, retention_candidate, n_bootstrap=n_bootstrap, seed=seed + 1)
    halluc_rate = round(sum(1 for f in candidate_hallucination_flags if f) / len(candidate_hallucination_flags), 4)

    failed_gates: list[str] = []
    if target_ci["ci_low"] < min_target_gain_ci_low:
        failed_gates.append("target_gain_ci_low_below_threshold")
    if ret_ci["ci_low"] < -abs(max_retention_drop):
        failed_gates.append("general_retention_regression")
    if halluc_rate > max_hallucination_rate:
        failed_gates.append("hallucination_rate_exceeded")

    return {
        "promote": len(failed_gates) == 0,
        "failed_gates": failed_gates,
        "target_gain": target_ci,
        "retention_delta": ret_ci,
        "hallucination_rate": halluc_rate,
        "thresholds": {
            "min_target_gain_ci_low": min_target_gain_ci_low,
            "max_retention_drop": max_retention_drop,
            "max_hallucination_rate": max_hallucination_rate,
        },
    }
