"""HarnessTax token overhead, cost-per-verified-task, MCP reliability and benchmark normalization."""

from __future__ import annotations

import math
from typing import Any


def compute_harness_tax(total_harness_tokens: int, raw_task_tokens: int) -> dict[str, float | int]:
    """Compute token overhead imposed by an agent harness scaffold over raw prompt/completion tokens.

    `tax_ratio = (total_harness_tokens - raw_task_tokens) / raw_task_tokens`
    `multiplier = total_harness_tokens / raw_task_tokens`
    """
    if raw_task_tokens <= 0:
        raise ValueError("raw_task_tokens must be positive")
    if total_harness_tokens < raw_task_tokens:
        raise ValueError("total_harness_tokens cannot be less than raw_task_tokens")
    overhead = total_harness_tokens - raw_task_tokens
    return {
        "total_harness_tokens": int(total_harness_tokens),
        "raw_task_tokens": int(raw_task_tokens),
        "overhead_tokens": int(overhead),
        "tax_ratio": round(overhead / raw_task_tokens, 4),
        "multiplier": round(total_harness_tokens / raw_task_tokens, 4),
    }


def wilson_interval_95(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score confidence interval for binomial proportions."""
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not (0 <= successes <= trials):
        raise ValueError("successes must be between 0 and trials")
    p = successes / trials
    denom = 1.0 + (z * z) / trials
    center = (p + (z * z) / (2.0 * trials)) / denom
    half = z * math.sqrt((p * (1.0 - p)) / trials + (z * z) / (4.0 * trials * trials)) / denom
    return round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)


def compute_cost_per_verified_task(
    total_cost_usd: float,
    verified_successes: int,
    total_tasks: int,
) -> dict[str, Any]:
    """Compute nominal cost per attempt and effective cost per verified solved task."""
    if total_tasks <= 0:
        raise ValueError("total_tasks must be positive")
    if total_cost_usd < 0.0:
        raise ValueError("total_cost_usd cannot be negative")
    if not (0 <= verified_successes <= total_tasks):
        raise ValueError("verified_successes out of range")
    cost_per_attempt = round(total_cost_usd / total_tasks, 4)
    cost_per_verified = round(total_cost_usd / verified_successes, 4) if verified_successes > 0 else None
    solve_rate = round(verified_successes / total_tasks, 4)
    ci_lo, ci_hi = wilson_interval_95(verified_successes, total_tasks)
    return {
        "total_cost_usd": round(total_cost_usd, 4),
        "total_tasks": int(total_tasks),
        "verified_successes": int(verified_successes),
        "solve_rate": solve_rate,
        "solve_rate_wilson_95": [ci_lo, ci_hi],
        "cost_per_attempt_usd": cost_per_attempt,
        "cost_per_verified_task_usd": cost_per_verified,
    }


def normalize_harness_benchmark(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a harness benchmark run across SWE-bench / Terminal-Bench, HarnessTax and MCP reliability."""
    tax = compute_harness_tax(int(raw["total_harness_tokens"]), int(raw["raw_task_tokens"]))
    cost = compute_cost_per_verified_task(
        float(raw["total_cost_usd"]),
        int(raw["verified_successes"]),
        int(raw["total_tasks"]),
    )
    mcp_ok = int(raw["mcp_calls_succeeded"])
    mcp_total = int(raw["mcp_calls_total"])
    mcp_rate = round(mcp_ok / mcp_total, 4) if mcp_total > 0 else 0.0
    mcp_ci = list(wilson_interval_95(mcp_ok, mcp_total)) if mcp_total > 0 else [0.0, 0.0]

    setup_fields = ("harness_version", "model_id", "suite_id", "timeout_s")
    setup_complete = all(bool(raw.get(k)) for k in setup_fields)

    return {
        "harness_id": str(raw["harness_id"]),
        "suite_id": str(raw.get("suite_id", "")),
        "model_id": str(raw.get("model_id", "")),
        "harness_version": str(raw.get("harness_version", "")),
        "setup_complete": setup_complete,
        "solve_rate": cost["solve_rate"],
        "solve_rate_wilson_95": cost["solve_rate_wilson_95"],
        "cost_per_verified_task_usd": cost["cost_per_verified_task_usd"],
        "harness_tax_ratio": tax["tax_ratio"],
        "harness_tax_multiplier": tax["multiplier"],
        "mcp_reliability": mcp_rate,
        "mcp_reliability_wilson_95": mcp_ci,
    }
