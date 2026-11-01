"""Multi-objective Pareto dominance, regime-weighted rubric ranking and deterministic demo synthesis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .grid_config import NodeGrid
from .intelligence_cards import ToolProfile


@dataclass(frozen=True)
class EvaluationRecord:
    """Universal head-to-head micro-benchmark measurement record for a niche candidate."""

    candidate_id: str
    niche_id: str
    cost_per_1k_ops_usd: float
    p99_latency_ms: float
    peak_ram_mb: float
    dependency_count: int
    single_maintainer_ergonomic: bool
    kubernetes_ready: bool
    accuracy: float
    reproducible_demo_verified: bool
    demo_command: str


def build_evaluation_record(raw: Mapping[str, Any]) -> EvaluationRecord:
    """Construct a typed EvaluationRecord from a raw measurement mapping."""
    return EvaluationRecord(
        candidate_id=str(raw["candidate_id"]).strip(),
        niche_id=str(raw["niche_id"]).strip(),
        cost_per_1k_ops_usd=float(raw["cost_per_1k_ops_usd"]),
        p99_latency_ms=float(raw["p99_latency_ms"]),
        peak_ram_mb=float(raw["peak_ram_mb"]),
        dependency_count=int(raw["dependency_count"]),
        single_maintainer_ergonomic=bool(raw["single_maintainer_ergonomic"]),
        kubernetes_ready=bool(raw["kubernetes_ready"]),
        accuracy=max(0.0, min(1.0, float(raw["accuracy"]))),
        reproducible_demo_verified=bool(raw["reproducible_demo_verified"]),
        demo_command=str(raw["demo_command"]).strip(),
    )


def compute_axis_scores(record: EvaluationRecord, *, grid: NodeGrid) -> dict[str, float]:
    """Normalize raw latency, cost, RAM, dependency, cluster, accuracy and demo measurements into [0.0, 1.0]."""
    bounds = grid.normalization_bounds()
    rnd = grid.float_round_digits

    cost_cap = bounds["cost_per_1k_ops_ceiling_usd"]
    cheapest = max(0.0, min(1.0, 1.0 - (record.cost_per_1k_ops_usd / cost_cap)))

    sub10_anchor = bounds["p99_latency_sub10ms_anchor_ms"]
    lat_cap = bounds["p99_latency_ceiling_ms"]
    if record.p99_latency_ms <= sub10_anchor:
        fastest = 1.0
    elif record.p99_latency_ms >= lat_cap:
        fastest = 0.0
    else:
        fastest = sub10_anchor / record.p99_latency_ms

    laptop_budget = bounds["small_laptop_ram_budget_mb"]
    ram_cap = bounds["ram_ceiling_mb"]
    fit_floor = bounds["small_laptop_fit_floor"]
    if record.peak_ram_mb <= laptop_budget:
        headroom = 1.0 - (record.peak_ram_mb / laptop_budget)
        small_laptop = fit_floor + (1.0 - fit_floor) * headroom
    elif record.peak_ram_mb >= ram_cap:
        small_laptop = 0.0
    else:
        small_laptop = fit_floor * (1.0 - ((record.peak_ram_mb - laptop_budget) / (ram_cap - laptop_budget)))

    dep_cap = bounds["dependency_count_ceiling"]
    erg_w = bounds["ergonomic_bonus_weight"]
    dep_score = max(0.0, min(1.0, 1.0 - (float(record.dependency_count) / dep_cap)))
    erg_score = 1.0 if record.single_maintainer_ergonomic else 0.0
    zero_dep_score = (1.0 - erg_w) * dep_score + erg_w * erg_score

    k8s_score = 1.0 if record.kubernetes_ready else 0.0
    demo_score = 1.0 if record.reproducible_demo_verified and bool(record.demo_command) else 0.0

    return {
        "cheapest_per_1k_ops": round(cheapest, rnd),
        "fastest_p99_sub10ms": round(fastest, rnd),
        "runs_on_small_4gb_laptop": round(small_laptop, rnd),
        "single_maintainer_zero_dep": round(zero_dep_score, rnd),
        "kubernetes_production_ready": round(k8s_score, rnd),
        "accuracy": round(record.accuracy, rnd),
        "reproducible_demo_walkthrough": round(demo_score, rnd),
    }


def pareto_dominates(
    scores_a: Mapping[str, float],
    scores_b: Mapping[str, float],
    *,
    axes: Sequence[str],
    epsilon: float,
) -> bool:
    """Return True iff candidate A is at least as good on every axis and strictly better on at least one."""
    no_worse_all = all(scores_a[axis] >= scores_b[axis] - epsilon for axis in axes)
    strictly_better_any = any(scores_a[axis] > scores_b[axis] + epsilon for axis in axes)
    return no_worse_all and strictly_better_any


def rank_niche_candidates(
    records: Sequence[EvaluationRecord],
    *,
    grid: NodeGrid,
    cell: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute Pareto frontier, axis champions and contextual regime-weighted leaderboard."""
    clamped = grid.clamp_cell(cell)
    regime = str(clamped["ranking_regime"])
    require_demo = bool(clamped["require_reproducible_demo"])
    weights = grid.regime_weights(regime)
    axes = grid.rubric_axes
    scale_max = grid.score_scale_max
    rnd = grid.float_round_digits
    eps = grid.pareto_tie_epsilon

    eligible: list[EvaluationRecord] = []
    filtered_out_ids: list[str] = []
    for rec in records:
        if require_demo and (not rec.reproducible_demo_verified or not rec.demo_command):
            filtered_out_ids.append(rec.candidate_id)
        else:
            eligible.append(rec)

    scored_rows: list[dict[str, Any]] = []
    for rec in eligible:
        ax_scores = compute_axis_scores(rec, grid=grid)
        weighted_unit = sum(ax_scores[ax] * weights.get(ax, 0.0) for ax in axes)
        scored_rows.append({
            "candidate_id": rec.candidate_id,
            "niche_id": rec.niche_id,
            "axis_scores": ax_scores,
            "weighted_score": round(weighted_unit * scale_max, rnd),
            "demo_command": rec.demo_command,
        })

    pareto_frontier_ids: list[str] = []
    for idx_a, row_a in enumerate(scored_rows):
        dominated = False
        for idx_b, row_b in enumerate(scored_rows):
            if idx_a == idx_b:
                continue
            if pareto_dominates(row_b["axis_scores"], row_a["axis_scores"], axes=axes, epsilon=eps):
                dominated = True
                break
        row_a["pareto_optimal"] = not dominated
        if not dominated:
            pareto_frontier_ids.append(row_a["candidate_id"])

    scored_rows.sort(
        key=lambda item: (
            -float(item["weighted_score"]),
            0 if item["pareto_optimal"] else 1,
            str(item["candidate_id"]),
        )
    )

    axis_champions: dict[str, str | None] = {}
    for ax in axes:
        if not scored_rows:
            axis_champions[ax] = None
        else:
            winner = max(scored_rows, key=lambda item: (item["axis_scores"][ax], item["weighted_score"]))
            axis_champions[ax] = str(winner["candidate_id"])

    return {
        "regime": regime,
        "cell_id": grid.cell_id(clamped),
        "ranked_candidates": scored_rows,
        "pareto_frontier_ids": sorted(pareto_frontier_ids),
        "axis_champions": axis_champions,
        "filtered_missing_demo_ids": sorted(filtered_out_ids),
        "top_candidate_id": scored_rows[0]["candidate_id"] if scored_rows else None,
    }


def synthesize_demo_walkthrough(
    ranked_result: Mapping[str, Any],
    profiles_by_id: Mapping[str, ToolProfile],
    *,
    grid: NodeGrid,
) -> dict[str, Any]:
    """Synthesize a deterministic runnable component demo and 4-beat walkthrough for the top niche candidate."""
    _ = grid
    ranked = list(ranked_result.get("ranked_candidates", ()))
    if not ranked:
        raise ValueError("cannot synthesize demo walkthrough for empty candidate ranking")
    winner = ranked[0]
    cand_id = str(winner["candidate_id"])
    niche_id = str(winner["niche_id"])
    profile = profiles_by_id.get(cand_id)

    io_sig = profile.port_signature_sha256 if profile is not None else "unregistered_port_signature"
    verify_cmd = profile.verification_command if profile is not None else str(winner["demo_command"])
    failure_guard = profile.failure_modes[0] if (profile is not None and profile.failure_modes) else "timeout_or_schema_mismatch"

    raw_beats = [
        (
            "fixture_and_io_contract_lock",
            f"Pin synthetic niche fixture for {niche_id} matching port signature {io_sig}.",
            "Input media_type and schema_ref validate offline with zero network calls.",
        ),
        (
            "deterministic_component_invocation",
            f"Run verification command: {verify_cmd}",
            f"Candidate {cand_id} emits schema-valid output port artifact.",
        ),
        (
            "pareto_and_regime_comparison",
            f"Compare {cand_id} against Pareto frontier {ranked_result.get('pareto_frontier_ids', [])} under regime {ranked_result.get('regime')}.",
            f"Weighted score {winner['weighted_score']} and axis champions reproduce identically.",
        ),
        (
            "failure_mode_probe",
            f"Inject synthetic malformed input to exercise failure mode '{failure_guard}'.",
            "Component fails closed with structured diagnostic and zero silent corruption.",
        ),
    ]
    storyboard_beats = [
        {
            "beat_index": idx,
            "stage": stage,
            "action": action,
            "expected_check": expected_check,
        }
        for idx, (stage, action, expected_check) in enumerate(raw_beats, start=1)
    ]

    return {
        "niche_id": niche_id,
        "regime": str(ranked_result["regime"]),
        "top_candidate_id": cand_id,
        "top_weighted_score": float(winner["weighted_score"]),
        "pareto_frontier_ids": list(ranked_result["pareto_frontier_ids"]),
        "io_port_signature_sha256": io_sig,
        "verification_command": verify_cmd,
        "storyboard_beats": storyboard_beats,
    }
