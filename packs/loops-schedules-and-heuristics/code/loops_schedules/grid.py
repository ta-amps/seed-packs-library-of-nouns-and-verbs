"""Declarative configuration grid loader and runtime bounds clamping for loops_schedules."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

SPEC_PATH = Path(__file__).with_name("default_grid_spec.json")


def load_default_grid_spec() -> dict[str, Any]:
    """Load externalized grid specification from default_grid_spec.json."""
    return dict(json.loads(SPEC_PATH.read_text(encoding="utf-8")))


def clamp_parameter(param_spec: dict[str, Any], raw_value: Any) -> Any:
    """Clamp a single parameter value within its declarative ParameterBounds."""
    ptype = str(param_spec["param_type"])
    if ptype == "boolean":
        return bool(raw_value)
    if ptype == "choice":
        choices = list(param_spec.get("choices", []))
        return raw_value if raw_value in choices else choices[0]
    if ptype == "integer_range":
        low = int(param_spec["low"])
        high = int(param_spec["high"])
        clamped = max(low, min(high, int(raw_value)))
        step = int(param_spec.get("step", 1))
        if step > 0:
            clamped = low + ((clamped - low) // step) * step
        return clamped
    if ptype == "float_range":
        low_f = float(param_spec["low"])
        high_f = float(param_spec["high"])
        return max(low_f, min(high_f, float(raw_value)))
    raise ValueError(f"unsupported param_type: {ptype}")


def resolve_grid_cell(
    overrides: dict[str, Any] | None = None,
    *,
    regime: str | None = None,
    spec: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve clamped grid cell values and constants dictionary from declarative spec."""
    active_spec = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
    merged_inputs: dict[str, Any] = {}
    if regime and regime in active_spec.get("regime_defaults", {}):
        merged_inputs.update(active_spec["regime_defaults"][regime])
    if overrides:
        merged_inputs.update(overrides)
    cell: dict[str, Any] = {}
    for param in active_spec["parameters"]:
        pname = str(param["name"])
        raw_val = merged_inputs.get(pname, param["default"])
        cell[pname] = clamp_parameter(param, raw_val)
    constants = dict(active_spec["constants"])
    return cell, constants
