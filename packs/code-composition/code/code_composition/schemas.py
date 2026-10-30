"""Strict Pydantic v2 schemas for prewritten verified nodes, step recipes, plans, and receipts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PortType = Literal["records", "table", "series", "text", "json", "metrics", "artifact"]
ParamType = Literal["int", "float", "str", "bool", "str_list"]
ALLOWED_SPDX_LICENSES: frozenset[str] = frozenset({"MIT", "Apache-2.0", "BSD-3-Clause", "CC0-1.0"})

STEP_ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
NODE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
PORT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
FUNC_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")


def port_value_matches(port_type: str, value: Any) -> bool:
    """Check a declared port's outer value contract, without coercion.

    This function is also embedded in standalone emitted modules. A records
    port is a list of objects; domain-specific fields still belong to node tests.
    """
    if port_type in {"text", "artifact"}:
        return isinstance(value, str)
    if port_type == "records":
        return isinstance(value, list) and all(isinstance(row, dict) for row in value)
    if port_type == "series":
        return isinstance(value, list) and all(
            type(item) is int or (type(item) is float and math.isfinite(item)) for item in value
        )
    if port_type in {"table", "metrics"}:
        return isinstance(value, dict)
    if port_type == "json":
        return isinstance(value, (dict, list))
    return False


def canonical_json(value: Any) -> str:
    """Serialize any JSON-compatible value into deterministic canonical form."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    """Compute lowercase hexadecimal SHA-256 over UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_source_code(source_code: str) -> str:
    """Normalize line endings and trailing whitespace for stable SHA-256 hashing."""
    lines = [ln.rstrip() for ln in source_code.replace("\r\n", "\n").strip().split("\n")]
    return "\n".join(lines) + "\n"


def compute_code_sha256(source_code: str) -> str:
    """Compute canonical SHA-256 digest of a prewritten Python function body."""
    return sha256_hex(normalize_source_code(source_code))


class PortSpec(BaseModel):
    """Typed input or output port contract on a prewritten code node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    port_type: PortType
    description: str
    required: bool = True

    @field_validator("name")
    @classmethod
    def _valid_port_name(cls, value: str) -> str:
        if not PORT_NAME_RE.match(value):
            raise ValueError(f"Invalid port name {value!r}; expected lowercase identifier.")
        return value


class ParamSpec(BaseModel):
    """Typed configuration parameter specification with static bounds and choices."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    param_type: ParamType
    description: str = ""
    default: Any = None
    required: bool = False
    min_value: float | None = None
    max_value: float | None = None
    choices: list[str] | None = None

    @field_validator("name")
    @classmethod
    def _valid_param_name(cls, value: str) -> str:
        if not PORT_NAME_RE.match(value):
            raise ValueError(f"Invalid param name {value!r}; expected lowercase identifier.")
        return value

    @model_validator(mode="after")
    def _check_bounds(self) -> ParamSpec:
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError(
                f"ParamSpec {self.name!r} has min_value ({self.min_value}) > max_value ({self.max_value})."
            )
        return self


class PrewrittenNode(BaseModel):
    """Verified, content-addressed prewritten Python node stored in NodeDatabase."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    version: str = "1.0.0"
    spdx_license: str = "MIT"
    governance_tags: list[str] = Field(default_factory=lambda: ["status:verified"])
    revision: int = Field(default=1, ge=1)
    category: str
    summary: str
    inputs: list[PortSpec]
    outputs: list[PortSpec]
    params: list[ParamSpec] = Field(default_factory=list)
    function_name: str
    source_code: str
    code_sha256: str = ""
    test_cases: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _populate_and_verify_code_hash(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        if isinstance(data.get("source_code"), str):
            norm = normalize_source_code(data["source_code"])
            expected = sha256_hex(norm)
            provided = str(data.get("code_sha256") or "").strip()
            if provided and provided != expected:
                raise ValueError(
                    f"code_sha256 mismatch for {data.get('node_id')!r}: "
                    f"expected {expected}, got {provided}."
                )
            data["source_code"] = norm
            data["code_sha256"] = expected
        return data

    @field_validator("node_id")
    @classmethod
    def _valid_node_id(cls, value: str) -> str:
        if not NODE_ID_RE.match(value):
            raise ValueError(
                f"Invalid node_id {value!r}; expected dotted slug like 'clean.dedupe_by_key'."
            )
        return value

    @field_validator("function_name")
    @classmethod
    def _valid_func_name(cls, value: str) -> str:
        if not FUNC_NAME_RE.match(value):
            raise ValueError(f"Invalid function_name {value!r}.")
        return value

    @model_validator(mode="after")
    def _unique_ports_and_params(self) -> PrewrittenNode:
        in_names = [p.name for p in self.inputs]
        if len(in_names) != len(set(in_names)):
            raise ValueError(f"Duplicate input port names on {self.node_id!r}.")
        out_names = [p.name for p in self.outputs]
        if len(out_names) != len(set(out_names)):
            raise ValueError(f"Duplicate output port names on {self.node_id!r}.")
        if not self.outputs:
            raise ValueError(f"Node {self.node_id!r} must declare at least one output port.")
        param_names = [p.name for p in self.params]
        if len(param_names) != len(set(param_names)):
            raise ValueError(f"Duplicate param names on {self.node_id!r}.")
        return self

    def signature_line(self) -> str:
        """Render a compact typed 1-line signature (~30-45 tokens) for LLM prompts."""
        in_sig = ", ".join(
            f"{p.name}:{p.port_type}{'' if p.required else '?'}" for p in self.inputs
        )
        out_sig = ", ".join(f"{p.name}:{p.port_type}" for p in self.outputs)
        param_parts: list[str] = []
        for param in self.params:
            if param.required and param.default is None:
                param_parts.append(f"{param.name}:{param.param_type}")
            else:
                param_parts.append(f"{param.name}:{param.param_type}={json.dumps(param.default)}")
        param_sig = f" [{', '.join(param_parts)}]" if param_parts else ""
        return f"{self.node_id}({in_sig}){param_sig} -> ({out_sig}) # {self.summary}"


class RecipeStep(BaseModel):
    """Single declarative node invocation in an LLM-emitted recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    node_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""

    @field_validator("step_id")
    @classmethod
    def _valid_step_id(cls, value: str) -> str:
        if not STEP_ID_RE.match(value):
            raise ValueError(
                f"Invalid step_id {value!r}; expected alphanumeric/underscore identifier."
            )
        return value


class RecipeEdge(BaseModel):
    """Directed dataflow connection wiring one upstream output port to a downstream input port."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    src_step: str
    src_port: str
    dst_step: str
    dst_port: str


class RecipeSpec(BaseModel):
    """Declarative recipe emitted by an LLM or developer instead of raw source code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipe_id: str
    title: str
    goal: str
    steps: list[RecipeStep]
    edges: list[RecipeEdge] = Field(default_factory=list, max_length=256)
    external_inputs: list[str] = Field(default_factory=list)

    @field_validator("recipe_id")
    @classmethod
    def _non_empty_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("recipe_id must not be empty.")
        return cleaned

    def canonical_sha256(self) -> str:
        """Compute canonical SHA-256 over the declarative RecipeSpec."""
        return sha256_hex(canonical_json(self.model_dump(mode="json")))


class GraphEntryInput(BaseModel):
    """External runtime input required to feed an unwired root/declared port of a compiled DAG."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    port_name: str
    port_type: PortType
    required: bool
    description: str


class TerminalOutputSpec(BaseModel):
    """Output port not consumed by any downstream edge (exposed as a terminal pipeline output)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    port_name: str
    port_type: PortType


class CompilerWarning(BaseModel):
    """Static non-fatal diagnostic emitted by DeterministicCompiler (e.g. dead/isolated step)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    step_id: str
    message: str


class CompiledStep(BaseModel):
    """Topologically ordered, contract-verified step with Merkle upstream sub-DAG fingerprint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    node_id: str
    version: str
    function_name: str
    code_sha256: str
    resolved_params: dict[str, Any]
    incoming_edges: list[RecipeEdge]
    entry_inputs: list[PortSpec]
    outputs: list[PortSpec]
    subgraph_fingerprint: str


class CompiledPlan(BaseModel):
    """Deterministic executable DAG plan produced by DeterministicCompiler."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipe_id: str
    title: str
    goal: str
    recipe_sha256: str
    topological_order: list[str]
    steps: list[CompiledStep]
    edges: list[RecipeEdge]
    entry_inputs: list[GraphEntryInput]
    terminal_outputs: list[TerminalOutputSpec]
    node_digests: list[str]
    warnings: list[CompilerWarning] = Field(default_factory=list)
    plan_sha256: str


class ExecutionReceipt(BaseModel):
    """Canonical SHA-256 execution receipt proving zero runtime LLM tokens and cache provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    recipe_id: str
    recipe_sha256: str
    plan_sha256: str
    node_digests: list[str]
    input_sha256: str
    output_sha256: str
    memo_hits: list[str]
    executed_steps: list[str]
    llm_tokens_at_runtime: Literal[0] = 0
    receipt_sha256: str


class ExecutionResult(BaseModel):
    """Result bundle from DeterministicRuntime.execute."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan: CompiledPlan
    step_outputs: dict[str, dict[str, Any]]
    terminal_outputs: dict[str, dict[str, Any]]
    receipt: ExecutionReceipt
    python_equivalence_verified: bool = False
