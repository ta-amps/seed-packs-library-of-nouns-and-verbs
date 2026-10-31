"""UCB1 + empirical-Bayes anti-stall bandit loop and 7-tier Compute & Resource Cascade Heuristic."""

from __future__ import annotations

import hashlib
import math
from typing import Any

from .grid import resolve_grid_cell


class BanditAntiStallLoopAndResourceHeuristic:
    """Selects exploration arms with tombstone suppression + plateau mutation and routes 7 compute tiers."""

    def __init__(
        self,
        grid_overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.cell, self.constants = resolve_grid_cell(grid_overrides, regime=regime, spec=spec)

    def select_arm_and_anti_stall(
        self,
        *,
        arms: list[dict[str, Any]],
        consecutive_zero_yield_waves: int,
        base_query: str,
        negative_tombstones: set[str] | list[str] = (),
    ) -> dict[str, Any]:
        """Select UCB1 + empirical-Bayes arm while suppressing tombstoned signatures and mutating stalled queries."""
        round_d = int(self.constants["round_digits"])
        tombstone_set = {str(t) for t in negative_tombstones}
        prior_strength = float(self.cell["bayes_prior_strength"])
        prior_mean = float(self.cell["bayes_prior_mean"])
        ucb_c = float(self.cell["ucb_exploration_c"])
        unpulled_bonus = float(self.constants["unpulled_ucb_bonus"])

        eligible_arms: list[dict[str, Any]] = []
        suppressed_arm_ids: list[str] = []
        for arm in arms:
            arm_id = str(arm["arm_id"])
            sig = str(arm.get("signature", arm_id))
            if arm_id in tombstone_set or sig in tombstone_set:
                suppressed_arm_ids.append(arm_id)
                continue
            eligible_arms.append(arm)

        total_pulls = max(1, sum(max(0, int(a.get("pulls", 0))) for a in eligible_arms))
        scored_arms: list[dict[str, Any]] = []
        for arm in eligible_arms:
            arm_id = str(arm["arm_id"])
            pulls = max(0, int(arm.get("pulls", 0)))
            reward_sum = float(arm.get("reward_sum", 0.0))
            shrunk_mean = (prior_strength * prior_mean + reward_sum) / (prior_strength + float(pulls))
            if pulls == 0:
                ucb_score = shrunk_mean + unpulled_bonus
            else:
                explore_term = math.sqrt(ucb_c * math.log(float(max(1, total_pulls))) / float(pulls))
                ucb_score = shrunk_mean + explore_term
            scored_arms.append(
                {
                    "arm_id": arm_id,
                    "pulls": pulls,
                    "shrunk_mean": round(shrunk_mean, round_d),
                    "ucb_score": round(ucb_score, round_d),
                }
            )

        scored_arms.sort(key=lambda item: (-float(item["ucb_score"]), str(item["arm_id"])))
        selected_arm_id = scored_arms[0]["arm_id"] if scored_arms else None

        stall_limit = int(self.cell["stall_wave_limit"])
        zero_waves = max(0, int(consecutive_zero_yield_waves))
        plateau_detected = zero_waves >= stall_limit
        mutated_query = base_query
        applied_operator: str | None = None

        if plateau_detected:
            operators = [str(op) for op in self.constants["mutation_operators"]]
            slice_chars = int(self.constants["digest_slice_chars"])
            radix = int(self.constants["hex_radix"])
            start_idx = int(hashlib.sha256(base_query.encode("utf-8")).hexdigest()[:slice_chars], radix) % len(
                operators
            )
            for offset in range(len(operators)):
                op_name = operators[(start_idx + offset) % len(operators)]
                candidate_q = f"{base_query} [{op_name}:wave_{zero_waves}]"
                if candidate_q not in tombstone_set and op_name not in tombstone_set:
                    mutated_query = candidate_q
                    applied_operator = op_name
                    break

        return {
            "selected_arm_id": selected_arm_id,
            "scored_arms": scored_arms,
            "suppressed_arm_ids": suppressed_arm_ids,
            "plateau_detected": plateau_detected,
            "mutation_operator": applied_operator,
            "effective_query": mutated_query,
        }

    def select_compute_tier(self, workload: dict[str, Any]) -> dict[str, Any]:
        """Select minimum-cost valid tier across the 7-tier Compute & Resource Cascade Heuristic."""
        round_d = int(self.constants["round_digits"])
        privacy_rank = self.constants["privacy_rank"]
        tokens_unit = float(self.constants["tokens_per_cost_unit"])

        det_eligible = bool(workload.get("deterministic_eligible", False))
        req_cap = max(1, int(workload.get("required_capability_rank", 1)))
        req_ctx = max(1, int(workload.get("required_context_tokens", 1)))
        req_tpm = max(0, int(workload.get("required_tpm", 0)))
        est_total_tokens = max(1, int(workload.get("estimated_total_tokens", 1)))
        spend_cap = max(0.0, float(workload.get("remaining_spend_cap_usd", 0.0)))
        req_priv = str(workload.get("privacy_tier", "internal"))
        req_priv_level = int(privacy_rank[req_priv])
        tpm_overrides = workload.get("tier_tpm_headroom_overrides") or {}

        rejected: list[dict[str, Any]] = []
        valid_candidates: list[dict[str, Any]] = []

        for tier in self.constants["compute_tiers"]:
            tid = str(tier["tier_id"])
            reasons: list[str] = []

            if bool(tier["requires_deterministic"]) and not det_eligible:
                reasons.append("requires_deterministic_task")
            if int(tier["capability_rank"]) < req_cap:
                reasons.append("insufficient_capability_rank")
            if int(tier["max_context_tokens"]) < req_ctx:
                reasons.append("insufficient_context_window")

            avail_tpm = int(tpm_overrides.get(tid, tier["default_tpm_headroom"]))
            if avail_tpm < req_tpm:
                reasons.append("insufficient_tpm_headroom")

            tier_priv_level = int(privacy_rank[str(tier["max_privacy_tier"])])
            if tier_priv_level < req_priv_level:
                reasons.append("insufficient_privacy_tier")
            if req_priv != "public" and bool(tier.get("contributor_training", False)):
                reasons.append("contributor_training_disallowed")

            est_cost = (float(est_total_tokens) / tokens_unit) * float(tier["cost_per_1k_tokens_usd"])
            if est_cost > spend_cap:
                reasons.append("exceeds_remaining_spend_cap")

            if reasons:
                rejected.append({"tier_id": tid, "reasons": reasons})
            else:
                valid_candidates.append(
                    {
                        "tier_id": tid,
                        "estimated_cost_usd": round(est_cost, round_d),
                        "capability_rank": int(tier["capability_rank"]),
                    }
                )

        if not valid_candidates:
            return {
                "selected_tier": None,
                "estimated_cost_usd": None,
                "status": "blocked_budget_or_policy",
                "rejected_tiers": rejected,
            }

        # Pick minimum-cost valid tier (preserving cascade order on ties)
        best = min(valid_candidates, key=lambda item: float(item["estimated_cost_usd"]))
        return {
            "selected_tier": str(best["tier_id"]),
            "estimated_cost_usd": float(best["estimated_cost_usd"]),
            "status": "tier_selected",
            "rejected_tiers": rejected,
        }
