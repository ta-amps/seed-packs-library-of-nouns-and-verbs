"""CLI entry point for jepa-world-state-and-action-simulator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .energy_and_planner import CounterfactualRolloutPlanner, EpistemicEnergyAnomalyGate
from .grid import load_default_grid_spec
from .predictor import ActionConditionedStatePredictor


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()

    predictor = ActionConditionedStatePredictor(spec=cfg)
    gate = EpistemicEnergyAnomalyGate(spec=cfg)
    planner = CounterfactualRolloutPlanner(predictor=predictor, spec=cfg)

    initial_state = predictor.encode_observation(dict(bundle["initial_observation"]))
    plan_report = planner.rank_candidates(
        initial_state=initial_state,
        candidates=list(bundle["candidate_sequences"]),
        goal=dict(bundle["goal"]),
    )

    step_action = dict(bundle["executed_step_action"])
    pred_step = predictor.predict_transition(initial_state, step_action)["predicted_state"]

    clean_obs = predictor.encode_observation(dict(bundle["clean_post_observation"]))
    clean_surprise = gate.evaluate_surprise(pred_step, clean_obs)

    anomaly_cases = list(bundle["anomaly_observations"])
    anomaly_triggers = 0
    max_anomaly_energy = 0.0
    for raw_anom in anomaly_cases:
        obs_anom = predictor.encode_observation(dict(raw_anom))
        res_anom = gate.evaluate_surprise(pred_step, obs_anom)
        if res_anom["decision"] == "trigger_rollback":
            anomaly_triggers += 1
        if res_anom["total_surprise_energy"] > max_anomaly_energy:
            max_anomaly_energy = res_anom["total_surprise_energy"]

    anomaly_recall = (
        float(anomaly_triggers) / float(len(anomaly_cases)) if anomaly_cases else 0.0
    )
    round_digits = int(cfg["numerics"]["round_digits"])

    ranked = plan_report["ranked_sequences"]
    best_plan = ranked[0]

    return {
        "recommended_sequence_id": plan_report["recommended_sequence_id"],
        "feasible_sequence_count": plan_report["feasible_count"],
        "best_goal_distance_energy": best_plan["goal_distance_energy"],
        "best_cumulative_risk_energy": best_plan["cumulative_risk_energy"],
        "best_total_objective_energy": best_plan["total_objective_energy"],
        "clean_observation_energy": clean_surprise["total_surprise_energy"],
        "clean_observation_decision": clean_surprise["decision"],
        "anomaly_case_count": len(anomaly_cases),
        "anomaly_rollback_recall": round(anomaly_recall, round_digits),
        "max_anomaly_energy": round(max_anomaly_energy, round_digits),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run jepa-world-state-and-action-simulator bundle evaluation."
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
