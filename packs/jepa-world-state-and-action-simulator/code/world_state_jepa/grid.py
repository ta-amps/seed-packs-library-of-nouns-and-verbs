"""Declarative NodeParameter, ParameterBounds and NodeGrid for JEPA world-state simulation."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SPEC_PATH = Path(__file__).resolve().parent / "default_grid_spec.json"


def load_default_grid_spec() -> dict[str, Any]:
    """Load externalized configuration grid specification."""
    return dict(json.loads(SPEC_PATH.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class ParameterBounds:
    """Runtime clamping and axis enumeration for a single grid parameter."""

    param_type: str
    low: int | float | None = None
    high: int | float | None = None
    step: int | float | None = None
    choices: tuple[Any, ...] = ()
    float_round_digits: int = 1

    def clamp(self, raw_value: Any) -> Any:
        if self.param_type == "boolean":
            return bool(raw_value)
        if self.param_type == "choice":
            if raw_value in self.choices:
                return raw_value
            if not self.choices:
                raise ValueError("choice parameter requires non-empty choices")
            return self.choices[0]
        if self.param_type == "integer_range":
            if self.low is None or self.high is None:
                raise ValueError("integer_range requires low and high")
            clamped = max(int(self.low), min(int(self.high), int(raw_value)))
            if self.step is not None and int(self.step) > 0:
                step_i = int(self.step)
                offset = clamped - int(self.low)
                clamped = int(self.low) + (offset // step_i) * step_i
            return clamped
        if self.param_type == "float_range":
            if self.low is None or self.high is None:
                raise ValueError("float_range requires low and high")
            clamped_f = max(float(self.low), min(float(self.high), float(raw_value)))
            return round(clamped_f, self.float_round_digits)
        raise ValueError(f"unsupported param_type: {self.param_type}")

    def enumerate_axis(self) -> list[Any]:
        if self.param_type == "boolean":
            return [False, True]
        if self.param_type == "choice":
            return list(self.choices)
        if self.param_type == "integer_range":
            if self.low is None or self.high is None:
                raise ValueError("integer_range requires low and high")
            step_i = int(self.step) if self.step is not None and int(self.step) > 0 else 1
            return list(range(int(self.low), int(self.high) + 1, step_i))
        if self.param_type == "float_range":
            if self.low is None or self.high is None:
                raise ValueError("float_range requires low and high")
            if self.step is None or float(self.step) <= 0.0:
                return [float(self.low), float(self.high)]
            vals: list[float] = []
            cur = float(self.low)
            while round(cur, self.float_round_digits) <= float(self.high):
                vals.append(round(cur, self.float_round_digits))
                cur += float(self.step)
            return vals
        raise ValueError(f"unsupported param_type: {self.param_type}")


@dataclass(frozen=True)
class NodeParameter:
    """Named tunable dimension inside a NodeGrid."""

    name: str
    bounds: ParameterBounds
    default: Any

    @classmethod
    def from_dict(cls, spec: dict[str, Any], *, float_round_digits: int) -> NodeParameter:
        ptype = str(spec["param_type"])
        bounds = ParameterBounds(
            param_type=ptype,
            low=spec.get("low"),
            high=spec.get("high"),
            step=spec.get("step"),
            choices=tuple(spec.get("choices", ())),
            float_round_digits=float_round_digits,
        )
        return cls(name=str(spec["name"]), bounds=bounds, default=bounds.clamp(spec["default"]))


class NodeGrid:
    """Multi-dimensional configuration grid with cross-parameter constraints."""

    def __init__(self, spec: dict[str, Any] | None = None) -> None:
        raw = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        self.spec = raw
        self.grid_id = str(raw["grid_id"])
        self.generation = int(raw.get("generation", 1))
        self.expansion_factor = int(raw["expansion_factor"])
        self.sha256_prefix_chars = int(raw["sha256_prefix_chars"])
        float_digits = int(raw["float_axis_round_digits"])
        self.parameters = [
            NodeParameter.from_dict(p, float_round_digits=float_digits) for p in raw["parameters"]
        ]
        self.param_by_name = {p.name: p for p in self.parameters}
        self.constraints: list[dict[str, Any]] = list(raw.get("constraints", []))
        self.regime_defaults: dict[str, dict[str, Any]] = dict(raw.get("regime_defaults", {}))

    def cell_id(self, cell: dict[str, Any]) -> str:
        canonical = json.dumps(cell, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()[: self.sha256_prefix_chars]
        return f"{self.grid_id}@g{self.generation}:{digest}"

    def clamp_cell(self, candidate: dict[str, Any]) -> dict[str, Any]:
        clamped: dict[str, Any] = {}
        for param in self.parameters:
            raw_val = candidate.get(param.name, param.default)
            clamped[param.name] = param.bounds.clamp(raw_val)
        return clamped

    def resolve_regime(self, regime_name: str) -> dict[str, Any]:
        return self.clamp_cell(self.regime_defaults.get(regime_name, {}))

    def is_applicable(self, cell: dict[str, Any]) -> bool:
        for rule in self.constraints:
            when_clause = rule.get("when", {})
            if all(cell.get(k) == v for k, v in when_clause.items()):
                req_in = rule.get("require_in", {})
                for target_key, allowed_vals in req_in.items():
                    if cell.get(target_key) not in allowed_vals:
                        return False
        return True

    def enumerate_cells(self) -> dict[str, list[dict[str, Any]]]:
        names = [p.name for p in self.parameters]
        axes = [p.bounds.enumerate_axis() for p in self.parameters]
        represented: list[dict[str, Any]] = []
        applicable: list[dict[str, Any]] = []
        for combo in itertools.product(*axes):
            cell = dict(zip(names, combo))
            represented.append(cell)
            if self.is_applicable(cell):
                applicable.append(cell)
        return {"represented": represented, "applicable": applicable}
