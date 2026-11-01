"""Deterministic pre-dispatch capability ceiling, secret-redaction, and model data-tier firewall."""

from .firewall import (
    DATA_SENSITIVITY_ORDER,
    EFFECT_ORDER,
    ENDPOINT_TRAINING_TIERS,
    check_effect_ceiling,
    check_model_tier_routing,
    evaluate_dispatch,
    scan_and_redact_payload,
    shannon_entropy,
)

__all__ = [
    "DATA_SENSITIVITY_ORDER",
    "EFFECT_ORDER",
    "ENDPOINT_TRAINING_TIERS",
    "check_effect_ceiling",
    "check_model_tier_routing",
    "evaluate_dispatch",
    "scan_and_redact_payload",
    "shannon_entropy",
]
