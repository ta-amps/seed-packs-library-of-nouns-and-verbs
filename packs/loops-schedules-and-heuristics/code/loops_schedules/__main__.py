"""CLI entry point for loops-schedules-and-heuristics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .heuristics import BanditAntiStallLoopAndResourceHeuristic
from .learners import SwappableLearnerAdvisors
from .schedules import DeclarativeScheduleAndCadenceCompiler


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Evaluate inert schedule windows, fragility urgency, AIMD pacing, UCB1 anti-stall, 7-tier compute, and 6 learners."""
    grid_cell = bundle.get("grid_cell")
    sched_compiler = DeclarativeScheduleAndCadenceCompiler(grid_cell)

    due_check = sched_compiler.evaluate_schedule_window(
        bundle["schedule_noun"],
        now_epoch_seconds=int(bundle["due_probe_epoch"]),
        completed_idempotency_keys=bundle.get("completed_keys", []),
    )
    off_window_check = sched_compiler.evaluate_schedule_window(
        bundle["schedule_noun"],
        now_epoch_seconds=int(bundle["outside_window_epoch"]),
        completed_idempotency_keys=bundle.get("completed_keys", []),
    )
    urgency_ranked = sched_compiler.rank_fragility_urgency(bundle["fragility_items"])
    aimd_in = bundle["aimd_probe"]
    aimd_res = sched_compiler.step_aimd_claim_pacing(
        current_concurrency=int(aimd_in["current_concurrency"]),
        prev_ewma_latency_ms=float(aimd_in["prev_ewma_latency_ms"]),
        observed_latency_ms=float(aimd_in["observed_latency_ms"]),
        total_pool_slots=int(aimd_in["total_pool_slots"]),
        active_peer_workers=int(aimd_in["active_peer_workers"]),
        had_throttle_error=bool(aimd_in.get("had_throttle_error", False)),
    )

    loop_engine = BanditAntiStallLoopAndResourceHeuristic(grid_cell)
    bandit_in = bundle["bandit_probe"]
    bandit_res = loop_engine.select_arm_and_anti_stall(
        arms=bandit_in["arms"],
        consecutive_zero_yield_waves=int(bandit_in["consecutive_zero_yield_waves"]),
        base_query=str(bandit_in["base_query"]),
        negative_tombstones=bandit_in.get("negative_tombstones", []),
    )
    tier_decisions = {
        str(w["workload_id"]): loop_engine.select_compute_tier(w)["selected_tier"]
        for w in bundle["compute_workloads"]
    }

    advisors = SwappableLearnerAdvisors(grid_cell)
    l_in = bundle["learners_input"]
    l1 = advisors.phrasing_acceptance_uplift(l_in["phrasing"])
    l2 = advisors.searchability_scent_ranker(
        l_in["scent_candidates"],
        l_in["scent_queries"],
    )
    l3 = advisors.shim_injection_matched_uplift(l_in["shim_strata"])
    l4 = advisors.decomposition_split_breakeven(l_in["decomposition"])
    l5 = advisors.pairwise_taste_bradley_terry(l_in["pairwise_comparisons"])
    l6 = advisors.rights_cleared_training_manifest(l_in["training_traces"])

    all_advice_only = all(
        bool(r["advice_only"]) and bool(r["keep_baseline_valid"])
        for r in (l1, l2, l3, l4, l5, l6)
    )

    return {
        "schedule_auto_enqueued": bool(due_check["auto_enqueued"]),
        "due_window_idempotency_key": str(due_check["idempotency_key"]),
        "due_window_active": bool(due_check["due"]),
        "outside_window_storage_io_ops": int(off_window_check["storage_io_ops"]),
        "top_urgent_item_id": str(urgency_ranked[0]["item_id"]),
        "aimd_next_concurrency": int(aimd_res["next_concurrency"]),
        "aimd_action": str(aimd_res["pacing_action"]),
        "selected_arm_id": str(bandit_res["selected_arm_id"]),
        "suppressed_arm_ids": bandit_res["suppressed_arm_ids"],
        "plateau_detected": bool(bandit_res["plateau_detected"]),
        "tier_decisions": tier_decisions,
        "all_learners_advice_only": all_advice_only,
        "learner_headlines": {
            "phrasing": str(l1["recommendation"]),
            "top_scent": str(l2["top_candidate_id"]),
            "shim_uplift": str(l3["recommendation"]),
            "decomposition": str(l4["recommendation"]),
            "top_bradley_terry": str(l5["top_item"]),
        },
        "cleared_train_trace_ids": l6["train_trace_ids"],
        "cleared_holdout_trace_ids": l6["holdout_trace_ids"],
        "blocked_trace_ids": l6["blocked_trace_ids"],
        "family_overlap_count": int(l6["family_overlap_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run loops-schedules-and-heuristics bundle evaluation.")
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
