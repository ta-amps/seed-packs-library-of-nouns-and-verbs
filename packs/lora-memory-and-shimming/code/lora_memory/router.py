"""Decision policy choosing prompt/context shimming vs LoRA weight updates vs hybrid routing."""

from __future__ import annotations

import math
from typing import Any


def route_adaptation_strategy(spec: dict[str, Any]) -> dict[str, Any]:
    """Choose `prompt_context_shim`, `lora_weight_update`, or `hybrid_shim_and_lora`.

    Inputs in `spec`:
      - `churn_half_life_days`: expected days before facts change materially
      - `queries_per_day`: expected request volume needing this knowledge
      - `shim_tokens_per_query`: prompt tokens consumed if injected via context shim
      - `training_equivalent_tokens`: one-time token-cost equivalent of training and gating a LoRA adapter
      - `requires_instant_revocation`: bool (whether individual facts must be revocable in seconds)
      - `has_volatile_pins_plus_stable_syntax`: bool (mixed stable conventions + volatile version pins)
    """
    churn_days = float(spec["churn_half_life_days"])
    qpd = float(spec["queries_per_day"])
    shim_toks = int(spec["shim_tokens_per_query"])
    train_toks = int(spec.get("training_equivalent_tokens", 2_000_000))
    instant_revoke = bool(spec.get("requires_instant_revocation", False))
    mixed_layer = bool(spec.get("has_volatile_pins_plus_stable_syntax", False))
    horizon_days = min(max(1.0, churn_days), 30.0)

    horizon_shim_tokens = int(round(qpd * horizon_days * shim_toks))
    breakeven_queries = int(math.ceil(train_toks / max(1, shim_toks)))

    if instant_revoke or churn_days < 14.0:
        mode = "prompt_context_shim"
        reason = (
            "Facts churn faster than 14 days or require instant per-item revocation; "
            "context shimming avoids stale weights."
        )
    elif mixed_layer and horizon_shim_tokens >= train_toks:
        mode = "hybrid_shim_and_lora"
        reason = (
            "Stable domain syntax amortizes LoRA training over the horizon while volatile "
            "version pins stay in a compact revocable prompt shim."
        )
    elif churn_days >= 30.0 and horizon_shim_tokens >= train_toks:
        mode = "lora_weight_update"
        reason = (
            "Knowledge half-life is at least 30 days and cumulative context-shim token cost "
            "exceeds LoRA training and holdout gating cost."
        )
    else:
        mode = "prompt_context_shim"
        reason = (
            "Query volume within the stability horizon does not yet amortize LoRA training; "
            "keep facts in a pinned prompt/context shim."
        )

    return {
        "selected_strategy": mode,
        "horizon_days_evaluated": round(horizon_days, 2),
        "horizon_shim_tokens": horizon_shim_tokens,
        "training_equivalent_tokens": train_toks,
        "breakeven_queries": breakeven_queries,
        "amortized": horizon_shim_tokens >= train_toks,
        "rationale": reason,
    }
