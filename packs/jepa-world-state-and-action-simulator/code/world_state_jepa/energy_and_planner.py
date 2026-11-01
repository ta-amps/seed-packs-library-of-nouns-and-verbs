"""Representation-space epistemic energy anomaly gate and counterfactual multi-step rollout planner."""

from __future__ import annotations

import copy
from typing import Any

from .grid import NodeGrid, load_default_grid_spec
from .predictor import ActionConditionedStatePredictor, FactoredWorldState


class EpistemicEnergyAnomalyGate:
    """Computes JEPA representation-space surprise E(s_hat_{t+1}, s_obs_{t+1}) and gates execution."""

    def __init__(
        self,
        *,
        review_energy_threshold: float | None = None,
        rollback_energy_threshold: float | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        grid = NodeGrid(cfg)
        num = cfg["numerics"]
        eg = cfg["energy_gate"]

        self._round_digits = int(num["round_digits"])
        self._w_quota = float(eg["quota_l2_weight"])
        self._w_lease = float(eg["lease_mismatch_weight"])
        self._w_digest = float(eg["digest_divergence_weight"])
        self._w_taint = float(eg["taint_escalation_weight"])
        self._w_invariant = float(eg["invariant_breach_weight"])
        self._w_latent = float(eg["latent_l2_weight"])

        clamped = grid.clamp_cell({
            "review_energy_threshold": (
                review_energy_threshold
                if review_energy_threshold is not None
                else eg["default_review_threshold"]
            ),
            "rollback_energy_threshold": (
                rollback_energy_threshold
                if rollback_energy_threshold is not None
                else eg["default_rollback_threshold"]
            ),
        })
        self.review_energy_threshold = float(clamped["review_energy_threshold"])
        self.rollback_energy_threshold = float(clamped["rollback_energy_threshold"])

    def evaluate_surprise(
        self,
        predicted: FactoredWorldState,
        observed: FactoredWorldState,
    ) -> dict[str, Any]:
        """Compute factored + latent energy E(s_hat, s_obs) and return continue/require_review/trigger_rollback."""
        all_quotas = sorted(set(predicted.resource_quotas) | set(observed.resource_quotas))
        quota_sq = 0.0
        for q_key in all_quotas:
            diff = predicted.resource_quotas.get(q_key, 0.0) - observed.resource_quotas.get(q_key, 0.0)
            quota_sq += diff * diff

        all_leases = sorted(set(predicted.leases) | set(observed.leases))
        lease_mismatches = sum(
            1 for l_key in all_leases if predicted.leases.get(l_key) != observed.leases.get(l_key)
        )

        all_records = sorted(set(predicted.record_digests) | set(observed.record_digests))
        digest_mismatches = 0
        for r_key in all_records:
            p_rec = predicted.record_digests.get(r_key, {})
            o_rec = observed.record_digests.get(r_key, {})
            if p_rec.get("version") != o_rec.get("version") or p_rec.get("digest") != o_rec.get("digest"):
                digest_mismatches += 1

        unpredicted_taints = set(observed.capability_taints) - set(predicted.capability_taints)
        broken_invariants = sum(1 for ok in observed.invariant_predicates.values() if not ok)

        latent_sq = sum(
            (a - b) * (a - b) for a, b in zip(predicted.latent_vector, observed.latent_vector)
        )

        total_energy = (
            self._w_quota * quota_sq
            + self._w_lease * float(lease_mismatches)
            + self._w_digest * float(digest_mismatches)
            + self._w_taint * float(len(unpredicted_taints))
            + self._w_invariant * float(broken_invariants)
            + self._w_latent * latent_sq
        )

        if broken_invariants > 0 or total_energy >= self.rollback_energy_threshold:
            decision = "trigger_rollback"
        elif total_energy >= self.review_energy_threshold:
            decision = "require_review"
        else:
            decision = "continue"

        return {
            "total_surprise_energy": round(total_energy, self._round_digits),
            "quota_l2_energy": round(quota_sq, self._round_digits),
            "lease_mismatch_count": lease_mismatches,
            "digest_mismatch_count": digest_mismatches,
            "unpredicted_taints": sorted(unpredicted_taints),
            "broken_invariant_count": broken_invariants,
            "latent_l2_energy": round(latent_sq, self._round_digits),
            "decision": decision,
        }


class CounterfactualRolloutPlanner:
    """Simulates K candidate multi-step action sequences in representation space and ranks safe plans."""

    def __init__(
        self,
        *,
        predictor: ActionConditionedStatePredictor | None = None,
        max_rollout_horizon: int | None = None,
        risk_energy_weight: float | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        grid = NodeGrid(cfg)
        num = cfg["numerics"]
        rp = cfg["rollout_planner"]

        self.predictor = predictor if predictor is not None else ActionConditionedStatePredictor(spec=cfg)
        self._round_digits = int(num["round_digits"])
        self._w_goal_rec = float(rp["goal_record_mismatch_weight"])
        self._w_goal_lease = float(rp["goal_unreleased_lease_weight"])
        self._w_goal_taint = float(rp["goal_remaining_taint_weight"])
        self._w_goal_quota = float(rp["goal_quota_shortfall_weight"])

        clamped = grid.clamp_cell({
            "max_rollout_horizon": (
                max_rollout_horizon if max_rollout_horizon is not None else rp["default_max_horizon"]
            ),
            "risk_energy_weight": (
                risk_energy_weight if risk_energy_weight is not None else rp["default_risk_weight"]
            ),
        })
        self.max_rollout_horizon = int(clamped["max_rollout_horizon"])
        self.risk_energy_weight = float(clamped["risk_energy_weight"])

    def goal_distance_energy(self, terminal_state: FactoredWorldState, goal: dict[str, Any]) -> float:
        """Measure representation-space distance between terminal rollout state s_hat_H and goal specification."""
        target_versions = dict(goal.get("target_record_versions", {}))
        rec_misses = 0
        for rec_key, wanted_ver in target_versions.items():
            cur_ver = int(terminal_state.record_digests.get(str(rec_key), {}).get("version", 0))
            if cur_ver < int(wanted_ver):
                rec_misses += int(wanted_ver) - cur_ver

        require_clean_leases = bool(goal.get("require_all_leases_released", False))
        dangling_leases = len(terminal_state.leases) if require_clean_leases else 0

        forbidden_terminal_taints = set(str(t) for t in goal.get("forbid_taints", []))
        remaining_taints = len(set(terminal_state.capability_taints) & forbidden_terminal_taints)

        min_quota_floors = dict(goal.get("min_quota_remaining", {}))
        quota_shortfall = sum(
            max(0.0, float(floor_val) - terminal_state.resource_quotas.get(str(q_key), 0.0))
            for q_key, floor_val in min_quota_floors.items()
        )

        dist = (
            self._w_goal_rec * float(rec_misses)
            + self._w_goal_lease * float(dangling_leases)
            + self._w_goal_taint * float(remaining_taints)
            + self._w_goal_quota * quota_shortfall
        )
        return round(dist, self._round_digits)

    def evaluate_sequence(
        self,
        initial_state: FactoredWorldState,
        candidate_sequence: dict[str, Any],
        goal: dict[str, Any],
    ) -> dict[str, Any]:
        """Simulate a single multi-step candidate trajectory in latent world-state space."""
        seq_id = str(candidate_sequence["sequence_id"])
        actions = list(candidate_sequence["actions"])[: self.max_rollout_horizon]

        cur_state = initial_state
        cumulative_risk = 0.0
        feasible = True
        violated_step: int | None = None

        for step_idx, act in enumerate(actions):
            step_out = self.predictor.predict_transition(cur_state, act)
            cur_state = step_out["predicted_state"]
            cumulative_risk += float(step_out["step_risk_energy"])
            if not step_out["invariants_hold"] and feasible:
                feasible = False
                violated_step = step_idx

        goal_dist = self.goal_distance_energy(cur_state, goal)
        total_obj = goal_dist + self.risk_energy_weight * cumulative_risk

        return {
            "sequence_id": seq_id,
            "steps_simulated": len(actions),
            "feasible": feasible,
            "first_violation_step": violated_step,
            "goal_distance_energy": round(goal_dist, self._round_digits),
            "cumulative_risk_energy": round(cumulative_risk, self._round_digits),
            "total_objective_energy": round(total_obj, self._round_digits),
            "terminal_state": cur_state.to_dict(),
        }

    def rank_candidates(
        self,
        initial_state: FactoredWorldState,
        candidates: list[dict[str, Any]],
        goal: dict[str, Any],
    ) -> dict[str, Any]:
        """Simulate K candidate sequences and rank feasible minimum-energy trajectories first."""
        evaluated = [self.evaluate_sequence(initial_state, seq, goal) for seq in candidates]
        evaluated.sort(
            key=lambda row: (
                not row["feasible"],
                row["goal_distance_energy"],
                row["total_objective_energy"],
                row["sequence_id"],
            )
        )
        best = evaluated[0] if evaluated else None
        return {
            "ranked_sequences": evaluated,
            "recommended_sequence_id": best["sequence_id"] if best and best["feasible"] else None,
            "feasible_count": sum(1 for row in evaluated if row["feasible"]),
        }
