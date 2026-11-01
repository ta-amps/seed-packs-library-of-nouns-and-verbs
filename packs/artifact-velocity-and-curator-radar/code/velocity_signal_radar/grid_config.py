"""Declarative NodeGrid, ParameterBounds, GridLedger, OperationCostLedger and AST/naming gates."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass
import hashlib
import itertools
import json
from pathlib import Path
import re
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "velocity_radar_grid.json"

CELL_LIFECYCLE_ORDER: tuple[str, ...] = (
    "represented",
    "applicable",
    "proposed",
    "dispatched",
    "evaluated",
    "verified",
    "promoted",
)


def load_grid_spec(path: Path | None = None) -> dict[str, Any]:
    """Load the externalized configuration grid specification from JSON."""
    target = path or CONFIG_PATH
    return dict(json.loads(target.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class ParameterBounds:
    """Runtime clamping and axis enumeration for a single NodeGrid parameter."""

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
            values: list[float] = []
            current = float(self.low)
            step_f = float(self.step)
            while current <= float(self.high) + (1.0 / (1.0 + float(self.float_round_digits))) * step_f:
                values.append(round(current, self.float_round_digits))
                current += step_f
            return values
        raise ValueError(f"unsupported param_type: {self.param_type}")


@dataclass(frozen=True)
class NodeParameter:
    """Named tunable dimension inside a multi-dimensional NodeGrid."""

    name: str
    bounds: ParameterBounds
    default: Any

    @classmethod
    def from_dict(cls, spec: Mapping[str, Any], *, float_round_digits: int) -> NodeParameter:
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
    """Multi-dimensional configuration settings grid with cross-axis constraints and boundary auto-expansion."""

    def __init__(self, spec: Mapping[str, Any] | None = None) -> None:
        raw = copy.deepcopy(dict(spec) if spec is not None else load_grid_spec())
        self.spec: dict[str, Any] = raw
        self.grid_id: str = str(raw["grid_id"])
        self.generation: int = int(raw.get("generation", 1))
        self.expansion_factor: int = int(raw["expansion_factor"])
        self.sha256_prefix_chars: int = int(raw["sha256_prefix_chars"])
        self.float_round_digits: int = int(raw["float_round_digits"])
        self.score_scale_milli: int = int(raw["score_scale_milli"])
        self.simhash_bit_width: int = int(raw["simhash_bit_width"])
        self.simhash_hex_nibbles: int = int(raw["simhash_hex_nibbles"])
        self.lsh_band_count: int = int(raw["lsh_band_count"])
        self.lsh_nibbles_per_band: int = int(raw["lsh_nibbles_per_band"])
        self.default_shingle_size: int = int(raw["default_shingle_size"])
        self.bits_per_byte: int = int(raw["bits_per_byte"])
        self.seconds_per_day: int = int(raw["seconds_per_day"])
        self.high_priority: int = int(raw["high_priority"])
        self.default_priority: int = int(raw["default_priority"])
        self.low_priority: int = int(raw["low_priority"])
        self.default_complexity_milli: int = int(raw["default_complexity_milli"])
        self.demo_complexity_milli: int = int(raw["demo_complexity_milli"])
        self.allow_authenticated_wall_scraping: bool = bool(raw["allow_authenticated_wall_scraping"])
        self.prohibited_wall_hosts: tuple[str, ...] = tuple(str(h).lower() for h in raw["prohibited_wall_hosts"])
        self.sanctioned_upstream_hosts: tuple[str, ...] = tuple(str(h).lower() for h in raw["sanctioned_upstream_hosts"])
        self.permissive_spdx_licenses: tuple[str, ...] = tuple(str(x) for x in raw["permissive_spdx_licenses"])
        self.hype_marker_phrases: tuple[str, ...] = tuple(str(x).lower() for x in raw["hype_marker_phrases"])
        self.quickstart_command_prefixes: tuple[str, ...] = tuple(str(x).lower() for x in raw["quickstart_command_prefixes"])
        self.rubric_axes: tuple[str, ...] = tuple(str(ax) for ax in raw["rubric_axes"])
        self.parameters: list[NodeParameter] = [
            NodeParameter.from_dict(item, float_round_digits=self.float_round_digits)
            for item in raw["parameters"]
        ]
        self.param_by_name: dict[str, NodeParameter] = {param.name: param for param in self.parameters}
        self.constraints: list[dict[str, Any]] = list(raw.get("constraints", []))
        self.regime_defaults: dict[str, dict[str, Any]] = dict(raw.get("regime_defaults", {}))

    def cell_id(self, cell: Mapping[str, Any]) -> str:
        canonical = json.dumps(dict(cell), sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()[: self.sha256_prefix_chars]
        return f"{self.grid_id}@g{self.generation}:{digest}"

    def clamp_cell(self, candidate: Mapping[str, Any] | None = None) -> dict[str, Any]:
        raw_cell = dict(candidate) if candidate is not None else {}
        clamped: dict[str, Any] = {}
        for param in self.parameters:
            raw_val = raw_cell.get(param.name, param.default)
            clamped[param.name] = param.bounds.clamp(raw_val)
        return clamped

    def is_applicable(self, cell: Mapping[str, Any]) -> bool:
        for rule in self.constraints:
            when_clause = rule.get("when", {})
            if all(cell.get(key) == expected for key, expected in when_clause.items()):
                require_in = rule.get("require_in", {})
                for target_key, allowed_vals in require_in.items():
                    if cell.get(target_key) not in allowed_vals:
                        return False
        return True

    def enumerate_cells(self) -> dict[str, list[dict[str, Any]]]:
        names = [param.name for param in self.parameters]
        axes = [param.bounds.enumerate_axis() for param in self.parameters]
        represented: list[dict[str, Any]] = []
        applicable: list[dict[str, Any]] = []
        for combo in itertools.product(*axes):
            cell = dict(zip(names, combo))
            represented.append(cell)
            if self.is_applicable(cell):
                applicable.append(cell)
        return {"represented": represented, "applicable": applicable}

    def regime_weights(self, regime: str) -> dict[str, float]:
        weights_by_regime = self.spec["regime_rubric_weights"]
        selected = weights_by_regime.get(regime) or weights_by_regime[self.param_by_name["radar_regime"].default]
        return {str(k): float(v) for k, v in selected.items()}

    def scoring_normalization(self) -> dict[str, float]:
        return {str(k): float(v) for k, v in self.spec["scoring_normalization"].items()}

    def auto_expand_if_saturated(self, empirical_optimum: Mapping[str, Any]) -> tuple[NodeGrid, list[str]]:
        """Automatically expand saturated axis boundaries into generation + 1."""
        expanded_axes: list[str] = []
        next_spec = copy.deepcopy(self.spec)
        for param_dict in next_spec["parameters"]:
            pname = str(param_dict["name"])
            ptype = str(param_dict["param_type"])
            if ptype not in ("integer_range", "float_range") or pname not in empirical_optimum:
                continue
            val = empirical_optimum[pname]
            low = param_dict["low"]
            high = param_dict["high"]
            if val >= high:
                new_high = (
                    int(high) * self.expansion_factor
                    if ptype == "integer_range"
                    else round(float(high) * float(self.expansion_factor), self.float_round_digits)
                )
                param_dict["high"] = new_high
                expanded_axes.append(f"{pname}:high->{new_high}")
            elif val <= low and float(low) > 0.0:
                if ptype == "integer_range":
                    new_low_i = max(1, int(low) // self.expansion_factor)
                    param_dict["low"] = new_low_i
                    expanded_axes.append(f"{pname}:low->{new_low_i}")
                else:
                    new_low_f = round(float(low) / float(self.expansion_factor), self.float_round_digits)
                    param_dict["low"] = new_low_f
                    expanded_axes.append(f"{pname}:low->{new_low_f}")
        if expanded_axes:
            next_spec["generation"] = self.generation + 1
        return NodeGrid(next_spec), expanded_axes


class GridLedger:
    """Tracks cell lifecycle transitions and requires distinct verifier principals before promotion."""

    def __init__(self, grid: NodeGrid) -> None:
        self.grid = grid
        self.http_ok = int(grid.spec["http_ok_status"])
        self.http_conflict = int(grid.spec["http_conflict_status"])
        self.records: dict[str, dict[str, Any]] = {}
        enumerated = grid.enumerate_cells()
        for cell in enumerated["represented"]:
            cid = grid.cell_id(cell)
            self.records[cid] = {
                "cell_id": cid,
                "cell": dict(cell),
                "state": "applicable" if grid.is_applicable(cell) else "represented",
                "proposer_worker_id": None,
                "proposer_key_id": None,
                "verifier_worker_id": None,
                "verifier_key_id": None,
                "metrics": None,
            }

    def transition(
        self,
        cell: Mapping[str, Any],
        target_state: str,
        *,
        worker_id: str = "",
        key_id: str = "",
        metrics: Mapping[str, float] | None = None,
    ) -> dict[str, Any]:
        clamped = self.grid.clamp_cell(cell)
        cid = self.grid.cell_id(clamped)
        if cid not in self.records:
            raise KeyError(f"unknown grid cell: {cid}")
        rec = self.records[cid]
        cur_idx = CELL_LIFECYCLE_ORDER.index(rec["state"])
        tgt_idx = CELL_LIFECYCLE_ORDER.index(target_state)
        if rec["state"] == "represented" and tgt_idx > 0:
            return {"ok": False, "status_code": self.http_conflict, "reason": "inapplicable_constraint_cell"}
        if tgt_idx != cur_idx + 1:
            return {
                "ok": False,
                "status_code": self.http_conflict,
                "reason": f"invalid_lifecycle_jump:{rec['state']}->{target_state}",
            }
        if target_state == "proposed":
            rec["proposer_worker_id"] = worker_id
            rec["proposer_key_id"] = key_id
        elif target_state == "evaluated" and metrics is not None:
            rec["metrics"] = {str(k): float(v) for k, v in metrics.items()}
        elif target_state == "verified":
            if (
                not worker_id
                or not key_id
                or worker_id == rec["proposer_worker_id"]
                or key_id == rec["proposer_key_id"]
            ):
                return {
                    "ok": False,
                    "status_code": self.http_conflict,
                    "reason": "distinct_verifier_required",
                }
            rec["verifier_worker_id"] = worker_id
            rec["verifier_key_id"] = key_id
        rec["state"] = target_state
        return {"ok": True, "status_code": self.http_ok, "cell_id": cid, "state": target_state}


class OperationCostLedger:
    """Contextual regime cell selector backed by empirical quality and cost observations."""

    def __init__(self, grid: NodeGrid, ledger: GridLedger) -> None:
        self.grid = grid
        self.ledger = ledger
        self.observations: list[dict[str, Any]] = []

    def record_observation(
        self,
        *,
        regime: str,
        cell: Mapping[str, Any],
        quality_score: float,
        cost_units: float,
    ) -> str:
        clamped = self.grid.clamp_cell(cell)
        cid = self.grid.cell_id(clamped)
        self.observations.append({
            "regime": regime,
            "cell_id": cid,
            "cell": clamped,
            "quality_score": float(quality_score),
            "cost_units": float(cost_units),
        })
        return cid

    def resolve_for_regime(self, regime: str, *, min_quality: float = 0.0) -> dict[str, Any]:
        candidates: list[tuple[float, str, dict[str, Any]]] = []
        for obs in self.observations:
            if obs["regime"] != regime or obs["quality_score"] < min_quality:
                continue
            cid = obs["cell_id"]
            state = self.ledger.records.get(cid, {}).get("state", "")
            if state in ("verified", "promoted"):
                candidates.append((obs["cost_units"], cid, obs["cell"]))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]))
            best_cost, best_cid, best_cell = candidates[0]
            return {
                "regime": regime,
                "source": "verified_ledger_optimum",
                "cell_id": best_cid,
                "cell": dict(best_cell),
                "cost_units": best_cost,
            }
        fallback_raw = self.grid.regime_defaults.get(regime, {})
        fallback_cell = self.grid.clamp_cell(fallback_raw)
        return {
            "regime": regime,
            "source": "regime_default",
            "cell_id": self.grid.cell_id(fallback_cell),
            "cell": fallback_cell,
            "cost_units": None,
        }


class ZeroHardcodedValuesAstGate:
    """Mechanical AST gate rejecting numeric literals outside canonical mathematical identities."""

    @staticmethod
    def scan_source(
        source_code: str,
        *,
        allowed_identities: Sequence[int | float] = (-1, 0, 1, -1.0, 0.0, 1.0),
        source_name: str = "<memory>",
    ) -> dict[str, Any]:
        allowed = {float(val) for val in allowed_identities}
        tree = ast.parse(source_code, filename=source_name)
        violations: list[dict[str, Any]] = []

        def _walk(node: ast.AST, in_annotation: bool) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                all_args = (
                    list(node.args.posonlyargs)
                    + list(node.args.args)
                    + list(node.args.kwonlyargs)
                    + ([node.args.vararg] if node.args.vararg else [])
                    + ([node.args.kwarg] if node.args.kwarg else [])
                )
                for arg in all_args:
                    if arg.annotation is not None:
                        _walk(arg.annotation, True)
                if node.returns is not None:
                    _walk(node.returns, True)
                for default_expr in list(node.args.defaults) + [
                    item for item in node.args.kw_defaults if item is not None
                ]:
                    _walk(default_expr, False)
                for stmt in node.body:
                    _walk(stmt, False)
                return
            if isinstance(node, ast.AnnAssign):
                _walk(node.annotation, True)
                if node.value is not None:
                    _walk(node.value, False)
                return
            if not in_annotation:
                if (
                    isinstance(node, ast.UnaryOp)
                    and isinstance(node.op, ast.USub)
                    and isinstance(node.operand, ast.Constant)
                    and isinstance(node.operand.value, (int, float))
                    and not isinstance(node.operand.value, bool)
                ):
                    neg_val = -node.operand.value
                    if float(neg_val) not in allowed:
                        violations.append({
                            "source": source_name,
                            "line": node.lineno,
                            "col": node.col_offset,
                            "literal": neg_val,
                        })
                    return
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, (int, float))
                    and not isinstance(node.value, bool)
                ):
                    if float(node.value) not in allowed:
                        violations.append({
                            "source": source_name,
                            "line": node.lineno,
                            "col": node.col_offset,
                            "literal": node.value,
                        })
            for child in ast.iter_child_nodes(node):
                _walk(child, in_annotation)

        _walk(tree, False)
        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }

    @classmethod
    def scan_paths(
        cls,
        paths: Sequence[Path],
        *,
        allowed_identities: Sequence[int | float] = (-1, 0, 1, -1.0, 0.0, 1.0),
    ) -> dict[str, Any]:
        all_violations: list[dict[str, Any]] = []
        scanned = 0
        for path in sorted(paths):
            files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
            for py_file in files:
                scanned += 1
                result = cls.scan_source(
                    py_file.read_text(encoding="utf-8"),
                    allowed_identities=allowed_identities,
                    source_name=py_file.name,
                )
                all_violations.extend(result["violations"])
        return {
            "passed": len(all_violations) == 0,
            "files_scanned": scanned,
            "violation_count": len(all_violations),
            "violations": all_violations,
        }


class DomainAgnosticNamingGate:
    """Mechanical naming gate rejecting industry-specific identifiers in files, schemas and AST definitions."""

    @staticmethod
    def _split_tokens(identifier: str) -> list[str]:
        return [
            word.lower()
            for word in re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|[A-Z]?[a-z]+|\d+", identifier)
        ]

    @classmethod
    def _matches_banned(cls, name: str, forbidden_tokens: Sequence[str]) -> str | None:
        words = cls._split_tokens(name)
        joined = "_".join(words)
        for raw_token in forbidden_tokens:
            tok = str(raw_token).lower()
            if tok in words or ("_" in tok and f"_{tok}_" in f"_{joined}_"):
                return tok
        return None

    @classmethod
    def scan_source(
        cls,
        source_code: str,
        *,
        forbidden_tokens: Sequence[str],
        source_name: str = "<memory>",
    ) -> dict[str, Any]:
        tree = ast.parse(source_code, filename=source_name)
        violations: list[dict[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                matched = cls._matches_banned(node.name, forbidden_tokens)
                if matched is not None:
                    violations.append({
                        "source": source_name,
                        "identifier": node.name,
                        "token": matched,
                    })
        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }

    @classmethod
    def scan_workspace(
        cls,
        paths: Sequence[Path],
        *,
        forbidden_tokens: Sequence[str],
        schema_ids: Sequence[str] = (),
    ) -> dict[str, Any]:
        violations: list[dict[str, str]] = []
        for schema_id in schema_ids:
            matched = cls._matches_banned(schema_id, forbidden_tokens)
            if matched is not None:
                violations.append({"source": "<schema_id>", "identifier": schema_id, "token": matched})
        for path in sorted(paths):
            entries = sorted(path.rglob("*")) if path.is_dir() else [path]
            for entry in entries:
                if any(part.startswith(".") or part == "__pycache__" or part.endswith(".egg-info") for part in entry.parts):
                    continue
                matched_name = cls._matches_banned(entry.stem, forbidden_tokens)
                if matched_name is not None:
                    violations.append({
                        "source": entry.name,
                        "identifier": entry.name,
                        "token": matched_name,
                    })
                if entry.is_file() and entry.suffix == ".py":
                    res = cls.scan_source(
                        entry.read_text(encoding="utf-8"),
                        forbidden_tokens=forbidden_tokens,
                        source_name=entry.name,
                    )
                    violations.extend(res["violations"])
        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }
