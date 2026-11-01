"""AdaptiveReasoningBudgetRouter across four compute and latent-state reasoning regimes."""

from __future__ import annotations

import math
from typing import Any

from .grid import resolve_grid_cell


class AdaptiveReasoningBudgetRouter:
    """Routes tasks across zero_step_direct, fast_sketch, compressed_state_checkpoint and full_deliberative_verify."""

    def __init__(
        self,
        overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.grid, self.cell, self.constants = resolve_grid_cell(overrides, regime=regime, spec=spec)
        self.regimes: list[str] = [str(r) for r in self.constants["regimes"]]
        self.weights: dict[str, float] = {
            str(k): float(v) for k, v in self.constants["feature_weights"].items()
        }
        self.normalizers: dict[str, float] = {
            str(k): float(v) for k, v in self.constants["feature_normalizers"].items()
        }
        self.regime_min_tokens: dict[str, int] = {
            str(k): int(v) for k, v in self.constants["regime_min_tokens"].items()
        }
        self.regime_token_fractions: dict[str, float] = {
            str(k): float(v) for k, v in self.constants["regime_token_fractions"].items()
        }
        self.regime_latency_ceilings_ms: dict[str, int] = {
            str(k): int(v) for k, v in self.constants["regime_latency_ceilings_ms"].items()
        }
        self.log_base_two = float(self.constants["log_base_two"])
        self.round_digits = int(self.constants["round_digits"])

    def ambiguity_entropy_bits(self, candidate_probs: list[float]) -> float:
        """Compute Shannon entropy H(p) in bits over candidate interpretation probabilities."""
        positive = [float(p) for p in candidate_probs if float(p) > 0.0]
        total = sum(positive)
        if total <= 0.0:
            return 0.0
        entropy = 0.0
        for val in positive:
            prob = val / total
            entropy -= prob * math.log(prob, self.log_base_two)
        return round(entropy, self.round_digits)

    def _base_regime_for_score(self, score: float) -> str:
        direct_cap = float(self.cell["direct_score_ceiling"])
        sketch_cap = float(self.cell["sketch_score_ceiling"])
        checkpoint_cap = float(self.cell["checkpoint_score_ceiling"])
        if score <= direct_cap:
            return self.regimes[0]
        if score <= sketch_cap:
            return self.regimes[1]
        if score <= checkpoint_cap:
            return self.regimes[len(self.regimes) - 1 - 1]
        return self.regimes[-1]

    def route_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Compute complexity score, ambiguity entropy and budget-clamped reasoning regime."""
        task_id = str(task.get("id", "task"))
        dep_depth = max(0.0, float(task.get("dependency_depth", 0)))
        branching = max(0.0, float(task.get("branching_factor", 1)))
        constraints = max(0.0, float(task.get("constraint_count", 0)))

        if "ambiguity_distribution" in task:
            amb_bits = self.ambiguity_entropy_bits(list(task["ambiguity_distribution"]))
        else:
            amb_bits = round(max(0.0, float(task.get("ambiguity_bits", 0.0))), self.round_digits)

        dep_norm = min(1.0, dep_depth / self.normalizers["max_dependency_depth"])
        branch_norm = min(1.0, branching / self.normalizers["max_branching_factor"])
        amb_norm = min(1.0, amb_bits / self.normalizers["max_ambiguity_bits"])
        con_norm = min(1.0, constraints / self.normalizers["max_constraint_count"])

        score = round(
            self.weights["dependency_depth_norm"] * dep_norm
            + self.weights["branching_factor_norm"] * branch_norm
            + self.weights["ambiguity_entropy_norm"] * amb_norm
            + self.weights["constraint_density_norm"] * con_norm,
            self.round_digits,
        )

        desired = self._base_regime_for_score(score)
        checkpoint_regime = self.regimes[len(self.regimes) - 1 - 1]
        deliberative_regime = self.regimes[-1]

        if bool(task.get("requires_formal_proof", False)):
            desired = deliberative_regime
        elif bool(task.get("multi_turn_state_carry", False)) and (
            self.regimes.index(desired) < self.regimes.index(checkpoint_regime)
        ):
            desired = checkpoint_regime

        grid_max_tokens = int(self.cell["max_reasoning_tokens"])
        if "token_budget" in task and task["token_budget"] is not None:
            effective_token_cap = max(0, min(grid_max_tokens, int(task["token_budget"])))
        else:
            effective_token_cap = grid_max_tokens

        latency_cap_ms: int | None = None
        if "latency_budget_ms" in task and task["latency_budget_ms"] is not None:
            latency_cap_ms = max(0, int(task["latency_budget_ms"]))

        desired_idx = self.regimes.index(desired)
        selected_idx = 0
        for idx in range(desired_idx, -1, -1):
            cand = self.regimes[idx]
            min_tok = self.regime_min_tokens[cand]
            max_lat = self.regime_latency_ceilings_ms[cand]
            tok_ok = effective_token_cap >= min_tok
            lat_ok = True if latency_cap_ms is None else (latency_cap_ms >= max_lat or idx == 0)
            if tok_ok and lat_ok:
                selected_idx = idx
                break

        selected = self.regimes[selected_idx]
        fraction = self.regime_token_fractions[selected]
        if selected_idx == 0:
            allocated_tokens = 0
        else:
            scaled = int(round(effective_token_cap * fraction))
            allocated_tokens = max(self.regime_min_tokens[selected], min(effective_token_cap, scaled))

        return {
            "id": task_id,
            "selected_regime": selected,
            "desired_regime": desired,
            "budget_clamped": selected != desired,
            "complexity_score": score,
            "ambiguity_entropy_bits": amb_bits,
            "allocated_reasoning_tokens": allocated_tokens,
            "latency_ceiling_ms": self.regime_latency_ceilings_ms[selected],
            "grid_cell_id": self.grid.cell_id(self.cell),
        }

    def route_batch(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        """Route a batch of tasks and summarize regime distribution and token savings."""
        decisions = [self.route_task(t) for t in tasks]
        grid_max_tokens = int(self.cell["max_reasoning_tokens"])
        uniform_tokens = len(decisions) * grid_max_tokens
        routed_tokens = sum(int(d["allocated_reasoning_tokens"]) for d in decisions)
        savings_ratio = (
            round(1.0 - (routed_tokens / uniform_tokens), self.round_digits)
            if uniform_tokens > 0
            else 0.0
        )
        return {
            "decisions": decisions,
            "routed_total_tokens": routed_tokens,
            "uniform_deliberative_tokens": uniform_tokens,
            "token_savings_fraction": savings_ratio,
        }
