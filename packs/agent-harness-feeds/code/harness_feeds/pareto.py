"""Multi-objective Pareto frontier ranking and release-aware freshness decay for agent harnesses."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Sequence


def _dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Return True if candidate `a` Pareto-dominates `b` across 4 objectives:
    maximize `solve_rate`, maximize `mcp_reliability`,
    minimize `cost_per_verified_task_usd`, minimize `harness_tax_ratio`.
    """
    cost_a = a["cost_per_verified_task_usd"] if a["cost_per_verified_task_usd"] is not None else float("inf")
    cost_b = b["cost_per_verified_task_usd"] if b["cost_per_verified_task_usd"] is not None else float("inf")

    ge_all = (
        a["solve_rate"] >= b["solve_rate"]
        and a["mcp_reliability"] >= b["mcp_reliability"]
        and cost_a <= cost_b
        and a["harness_tax_ratio"] <= b["harness_tax_ratio"]
    )
    if not ge_all:
        return False
    strictly_better = (
        a["solve_rate"] > b["solve_rate"]
        or a["mcp_reliability"] > b["mcp_reliability"]
        or cost_a < cost_b
        or a["harness_tax_ratio"] < b["harness_tax_ratio"]
    )
    return strictly_better


def pareto_frontier(candidates: Sequence[dict[str, Any]]) -> list[str]:
    """Return sorted `harness_id`s on the non-dominated Pareto frontier among setup-complete runs."""
    eligible = [c for c in candidates if c.get("setup_complete", True)]
    frontier: list[str] = []
    for cand in eligible:
        if not any(_dominates(other, cand) for other in eligible if other["harness_id"] != cand["harness_id"]):
            frontier.append(str(cand["harness_id"]))
    return sorted(frontier)


def compute_freshness_decay(
    observed_date: str,
    as_of_date: str,
    *,
    half_life_days: float = 21.0,
    missed_releases: int = 0,
) -> dict[str, Any]:
    """Compute exponential freshness score in (0, 1] penalized by age and missed upstream releases."""
    d_obs = _dt.date.fromisoformat(observed_date)
    d_now = _dt.date.fromisoformat(as_of_date)
    age_days = max(0, (d_now - d_obs).days)
    time_weight = 0.5 ** (age_days / max(1.0, half_life_days))
    release_weight = 0.85 ** max(0, int(missed_releases))
    freshness = round(time_weight * release_weight, 4)
    if freshness >= 0.70 and missed_releases == 0:
        status = "fresh"
    elif freshness >= 0.40:
        status = "aging"
    else:
        status = "stale"
    return {
        "observed_date": observed_date,
        "as_of_date": as_of_date,
        "age_days": age_days,
        "missed_releases": int(missed_releases),
        "freshness_score": freshness,
        "status": status,
    }


def select_harness(
    candidates: Sequence[dict[str, Any]],
    *,
    max_cost_per_verified_usd: float | None = None,
    max_harness_tax_ratio: float | None = None,
    min_mcp_reliability: float = 0.90,
) -> dict[str, Any]:
    """Rank normalized harness runs under explicit budget, HarnessTax and MCP reliability constraints."""
    frontier_ids = set(pareto_frontier(candidates))
    scored: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for c in candidates:
        hid = str(c["harness_id"])
        reasons: list[str] = []
        cost = c.get("cost_per_verified_task_usd")
        if not c.get("setup_complete", True):
            reasons.append("incomplete_benchmark_setup")
        if cost is None or (max_cost_per_verified_usd is not None and cost > max_cost_per_verified_usd):
            reasons.append("exceeds_cost_ceiling")
        if max_harness_tax_ratio is not None and c["harness_tax_ratio"] > max_harness_tax_ratio:
            reasons.append("exceeds_harness_tax_ceiling")
        if c["mcp_reliability"] < min_mcp_reliability:
            reasons.append("below_mcp_reliability_floor")

        if reasons:
            rejected.append({"harness_id": hid, "reasons": reasons})
            continue

        assert cost is not None
        # Balanced utility: solve_rate + 0.35 * mcp_reliability - 0.15 * tax_ratio - 0.08 * cost
        utility = round(
            float(c["solve_rate"])
            + 0.35 * float(c["mcp_reliability"])
            - 0.15 * float(c["harness_tax_ratio"])
            - 0.08 * float(cost),
            4,
        )
        scored.append({
            "harness_id": hid,
            "utility": utility,
            "on_pareto_frontier": hid in frontier_ids,
            "solve_rate": c["solve_rate"],
            "cost_per_verified_task_usd": cost,
            "harness_tax_ratio": c["harness_tax_ratio"],
            "mcp_reliability": c["mcp_reliability"],
        })

    scored.sort(key=lambda r: (-r["utility"], r["harness_id"]))
    return {
        "pareto_frontier": sorted(frontier_ids),
        "selected_harness_id": scored[0]["harness_id"] if scored else None,
        "ranked": scored,
        "rejected": sorted(rejected, key=lambda r: r["harness_id"]),
    }
