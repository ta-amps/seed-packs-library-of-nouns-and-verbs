"""Agent-callable 'which-fits' compatibility matcher for memory systems and harness feed entries."""

from __future__ import annotations

from typing import Any

from .grid import resolve_grid_cell
from .router import HarnessTaxAndThreeRegimeRouter


class WhichFitsCompatibilityMatcher:
    """Scores candidate memory/harness entries across privacy, churn, HarnessTax, freshness, and budget."""

    def __init__(
        self,
        grid_overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.cell, self.constants = resolve_grid_cell(grid_overrides, regime=regime, spec=spec)
        self._tax_router = HarnessTaxAndThreeRegimeRouter(grid_overrides, regime=regime, spec=spec)

    @staticmethod
    def _dominates(metrics_a: tuple[float, ...], metrics_b: tuple[float, ...]) -> bool:
        at_least_all = all(val_a >= val_b for val_a, val_b in zip(metrics_a, metrics_b))
        strictly_better_one = any(val_a > val_b for val_a, val_b in zip(metrics_a, metrics_b))
        return at_least_all and strictly_better_one

    def recommend_which_fits(
        self,
        workload_request: dict[str, Any],
        candidate_entries: list[dict[str, Any]],
        grid_cell: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Rank compatible entries, compute Pareto winners, and explain disqualified candidates."""
        active_cell = dict(self.cell)
        if grid_cell:
            active_cell.update(grid_cell)
        round_d = int(self.constants["round_digits"])
        decay_base = float(self.constants["decay_base"])
        privacy_rank = self.constants["privacy_rank"]

        req_privacy = str(workload_request.get("data_privacy_tier", "internal"))
        req_priv_level = int(privacy_rank[req_privacy])
        req_half_life = max(0.0, float(workload_request.get("churn_half_life_days", 1.0)))
        req_instant_revoke = bool(workload_request.get("requires_instant_revocation", False))
        req_budget = max(1, int(workload_request.get("token_budget", active_cell["token_budget"])))
        slice_k = max(1, int(workload_request.get("slice_count_k", 1)))
        content_c = max(1, int(workload_request.get("task_content_tokens_c", 1)))

        w_fresh = float(active_cell["which_fits_freshness_weight"])
        w_tax = float(active_cell["which_fits_tax_weight"])
        w_budget = float(active_cell["which_fits_budget_weight"])
        w_churn = float(active_cell["which_fits_churn_weight"])
        weight_sum = w_fresh + w_tax + w_budget + w_churn
        norm_div = weight_sum if weight_sum > 0.0 else 1.0

        qualified: list[dict[str, Any]] = []
        disqualified: list[dict[str, Any]] = []

        for entry in candidate_entries:
            entry_id = str(entry["entry_id"])
            reasons: list[str] = []

            cand_priv = str(entry.get("max_privacy_tier", "public"))
            cand_priv_level = int(privacy_rank[cand_priv])
            contrib_train = bool(entry.get("contributor_training_enabled", False))

            if req_privacy != "public" and contrib_train:
                reasons.append("contributor_training_refused_for_non_public_data")
            if cand_priv_level < req_priv_level:
                reasons.append("insufficient_privacy_tier")

            overhead_tokens = max(0, int(entry.get("entry_token_overhead", 0)))
            if overhead_tokens > req_budget:
                reasons.append("exceeds_token_budget")

            if req_instant_revoke and not bool(entry.get("supports_instant_revocation", True)):
                reasons.append("lacks_instant_revocation")

            min_half_life = float(entry.get("min_supported_half_life_days", 0.0))
            if req_half_life < min_half_life:
                reasons.append("churn_too_fast_for_entry")

            if reasons:
                disqualified.append(
                    {
                        "entry_id": entry_id,
                        "disqualified_reasons": reasons,
                    }
                )
                continue

            age_days = max(0.0, float(entry.get("age_days", 0.0)))
            fresh_half_life = max(1.0, float(entry.get("freshness_half_life_days", 1.0)))
            freshness_score = decay_base ** (age_days / fresh_half_life)

            prefix_p = max(0, int(entry.get("harness_prefix_tokens_p", 0)))
            tax_info = self._tax_router.compute_harness_tax(
                prefix_tokens_p=prefix_p,
                content_tokens_c=content_c,
                slice_count_k=slice_k,
            )
            tax_efficiency = 1.0 - float(tax_info["break_even_skip_rate"])
            budget_headroom = 1.0 - (float(overhead_tokens) / float(req_budget))

            optimal_hl = max(1.0, float(entry.get("optimal_half_life_days", max(1.0, req_half_life))))
            hl_denom = max(1.0, max(req_half_life, optimal_hl))
            churn_fit = max(0.0, 1.0 - (abs(req_half_life - optimal_hl) / hl_denom))

            composite = (
                w_fresh * freshness_score
                + w_tax * tax_efficiency
                + w_budget * budget_headroom
                + w_churn * churn_fit
            ) / norm_div

            qualified.append(
                {
                    "entry_id": entry_id,
                    "composite_score": round(composite, round_d),
                    "freshness_score": round(freshness_score, round_d),
                    "tax_efficiency": round(tax_efficiency, round_d),
                    "break_even_skip_rate": float(tax_info["break_even_skip_rate"]),
                    "budget_headroom": round(budget_headroom, round_d),
                    "churn_fit": round(churn_fit, round_d),
                    "_pareto_vec": (freshness_score, tax_efficiency, budget_headroom, churn_fit),
                }
            )

        qualified.sort(key=lambda item: (-float(item["composite_score"]), str(item["entry_id"])))
        pareto_ids: list[str] = []
        for idx, cand in enumerate(qualified):
            dominated = False
            for other_idx, other in enumerate(qualified):
                if idx == other_idx:
                    continue
                if self._dominates(other["_pareto_vec"], cand["_pareto_vec"]):
                    dominated = True
                    break
            cand["pareto_optimal"] = not dominated
            if not dominated:
                pareto_ids.append(str(cand["entry_id"]))

        for cand in qualified:
            cand.pop("_pareto_vec", None)

        return {
            "ranked_candidates": qualified,
            "pareto_winners": pareto_ids,
            "disqualified": disqualified,
        }


def recommend_which_fits(
    workload_request: dict[str, Any],
    candidate_entries: list[dict[str, Any]],
    grid_cell: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience entry point for agent-callable compatibility matching."""
    matcher = WhichFitsCompatibilityMatcher(grid_cell)
    return matcher.recommend_which_fits(workload_request, candidate_entries, grid_cell)
