"""Step-slicing HarnessTax break-even calculator and 3-regime + hybrid Shim/Code/LoRA router."""

from __future__ import annotations

import math
from typing import Any

from .grid import resolve_grid_cell


class HarnessTaxAndThreeRegimeRouter:
    """Computes step-slicing HarnessTax break-even skip rates and routes repeatable interventions."""

    def __init__(
        self,
        grid_overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.cell, self.constants = resolve_grid_cell(grid_overrides, regime=regime, spec=spec)

    def compute_harness_tax(
        self,
        *,
        prefix_tokens_p: int,
        content_tokens_c: int,
        slice_count_k: int,
        observed_skip_rate: float = 0.0,
    ) -> dict[str, Any]:
        """Compute step-slicing break-even skip rate (k - 1) * P / (k * P + C)."""
        round_d = int(self.constants["round_digits"])
        p_val = max(0, int(prefix_tokens_p))
        c_val = max(0, int(content_tokens_c))
        k_val = max(1, int(slice_count_k))
        denom = k_val * p_val + c_val
        if k_val <= 1 or denom <= 0:
            break_even = 0.0
        else:
            break_even = float((k_val - 1) * p_val) / float(denom)

        unsliced_tokens = p_val + c_val
        sliced_unskipped_tokens = denom
        clamped_skip = max(0.0, min(1.0, float(observed_skip_rate)))
        expected_sliced_tokens = float(sliced_unskipped_tokens) * (1.0 - clamped_skip)
        return {
            "prefix_tokens_p": p_val,
            "content_tokens_c": c_val,
            "slice_count_k": k_val,
            "unsliced_tokens": unsliced_tokens,
            "sliced_unskipped_tokens": sliced_unskipped_tokens,
            "break_even_skip_rate": round(break_even, round_d),
            "observed_skip_rate": round(clamped_skip, round_d),
            "expected_sliced_tokens": round(expected_sliced_tokens, round_d),
            "slicing_saves_tokens": clamped_skip > break_even,
        }

    def route_intervention_regime(self, intervention: dict[str, Any]) -> dict[str, Any]:
        """Route an intervention to deterministic_code_shim, ephemeral_context_shim, peft_lora_adapter, or hybrid."""
        round_d = int(self.constants["round_digits"])
        is_det_code = bool(intervention.get("is_deterministic_validator_or_parser", False))
        instant_revoke = bool(intervention.get("requires_instant_revocation", False))
        has_volatile_pins = bool(intervention.get("has_volatile_sha256_pins", False))
        half_life_days = float(intervention.get("churn_half_life_days", 0.0))
        shim_tokens = max(1, int(intervention.get("shim_tokens", 1)))
        train_tokens = max(1, int(intervention.get("train_tokens", 1)))
        horizon_calls = max(0, int(intervention.get("expected_horizon_calls", 0)))

        volatile_floor = float(self.cell["volatile_half_life_days_floor"])
        pointer_tokens = int(self.cell["pointer_shim_token_cost"])

        if is_det_code:
            return {
                "selected_regime": "deterministic_code_shim",
                "per_call_inference_tokens": 0,
                "horizon_total_tokens": 0,
                "break_even_calls": 0,
                "rationale": "Deterministic validation or parsing executes in code at zero inference token cost.",
            }

        pure_shim_horizon = horizon_calls * shim_tokens
        if instant_revoke or half_life_days < volatile_floor:
            return {
                "selected_regime": "ephemeral_context_shim",
                "per_call_inference_tokens": shim_tokens,
                "horizon_total_tokens": pure_shim_horizon,
                "break_even_calls": math.ceil(float(train_tokens) / float(shim_tokens)),
                "rationale": "Instant revocation or short half-life requires a revocable ephemeral context shim.",
            }

        if has_volatile_pins:
            effective_pointer = min(shim_tokens, pointer_tokens)
            saved_per_call = shim_tokens - effective_pointer
            hybrid_horizon = train_tokens + horizon_calls * effective_pointer
            if saved_per_call > 0 and hybrid_horizon < pure_shim_horizon:
                return {
                    "selected_regime": "hybrid_lora_plus_pointer_shim",
                    "per_call_inference_tokens": effective_pointer,
                    "horizon_total_tokens": hybrid_horizon,
                    "break_even_calls": math.ceil(float(train_tokens) / float(saved_per_call)),
                    "rationale": round(float(pure_shim_horizon - hybrid_horizon), round_d) >= 0.0
                    and "Stable procedure amortizes LoRA training while volatile SHA-256 pins stay in a compact pointer shim.",
                }
            return {
                "selected_regime": "ephemeral_context_shim",
                "per_call_inference_tokens": shim_tokens,
                "horizon_total_tokens": pure_shim_horizon,
                "break_even_calls": math.ceil(float(train_tokens) / float( max(1, saved_per_call))),
                "rationale": "Horizon call volume does not yet amortize hybrid LoRA training cost.",
            }

        if pure_shim_horizon > train_tokens:
            return {
                "selected_regime": "peft_lora_adapter",
                "per_call_inference_tokens": 0,
                "horizon_total_tokens": train_tokens,
                "break_even_calls": math.ceil(float(train_tokens) / float(shim_tokens)),
                "rationale": "Stable long-lived behavior exceeds LoRA training token break-even.",
            }

        return {
            "selected_regime": "ephemeral_context_shim",
            "per_call_inference_tokens": shim_tokens,
            "horizon_total_tokens": pure_shim_horizon,
            "break_even_calls": math.ceil(float(train_tokens) / float(shim_tokens)),
            "rationale": "Low expected call volume stays cheaper as an ephemeral context shim.",
        }
