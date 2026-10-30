"""Deterministic recipe-to-DAG compiler, static port checker, Merkle fingerprinter, and Python emitter."""

from __future__ import annotations

import difflib
import heapq
import inspect
import pprint
from typing import Any

from code_composition.errors import (
    CycleDetectedError,
    NodeGovernanceError,
    ParameterConstraintError,
    PortNotFoundError,
    PortTypeMismatchError,
    RecipeValidationError,
)
from code_composition.registry import NodeDatabase
from code_composition.schemas import (
    ALLOWED_SPDX_LICENSES,
    CompiledPlan,
    CompiledStep,
    CompilerWarning,
    GraphEntryInput,
    ParamSpec,
    PortSpec,
    PrewrittenNode,
    RecipeEdge,
    RecipeSpec,
    RecipeStep,
    TerminalOutputSpec,
    canonical_json,
    compute_code_sha256,
    port_value_matches,
    sha256_hex,
)

TRANSFORM_CATEGORIES = frozenset({"ingest", "clean", "feature", "text", "join"})


def _close_match(target: str, candidates: list[str]) -> str | None:
    matches = difflib.get_close_matches(target, candidates, n=1, cutoff=0.45)
    return matches[0] if matches else None


def _validate_and_resolve_params(step: RecipeStep, node: PrewrittenNode) -> dict[str, Any]:
    spec_by_name: dict[str, ParamSpec] = {p.name: p for p in node.params}
    declared_names = list(spec_by_name.keys())

    for provided_name in step.params:
        if provided_name not in spec_by_name:
            raise ParameterConstraintError(
                step_id=step.step_id,
                node_id=node.node_id,
                param_name=provided_name,
                reason=f"unknown parameter (declared: {declared_names or 'none'})",
                suggestion=_close_match(provided_name, declared_names),
            )

    resolved: dict[str, Any] = {}
    for spec in node.params:
        if spec.name in step.params:
            raw_val = step.params[spec.name]
        elif spec.default is not None:
            raw_val = spec.default
        elif spec.required:
            raise ParameterConstraintError(
                step_id=step.step_id,
                node_id=node.node_id,
                param_name=spec.name,
                reason=f"missing required parameter of type {spec.param_type!r}",
            )
        else:
            continue

        resolved[spec.name] = _coerce_and_check_param(step, node, spec, raw_val)
    return resolved


def _coerce_and_check_param(
    step: RecipeStep, node: PrewrittenNode, spec: ParamSpec, value: Any
) -> Any:
    ptype = spec.param_type
    if ptype == "bool":
        if not isinstance(value, bool):
            raise ParameterConstraintError(
                step_id=step.step_id,
                node_id=node.node_id,
                param_name=spec.name,
                reason=f"expected bool, got {type(value).__name__}",
            )
        return value

    if ptype == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ParameterConstraintError(
                step_id=step.step_id,
                node_id=node.node_id,
                param_name=spec.name,
                reason=f"expected int, got {type(value).__name__}",
            )
        num_val = float(value)
        _check_numeric_bounds(step, node, spec, num_val)
        return value

    if ptype == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ParameterConstraintError(
                step_id=step.step_id,
                node_id=node.node_id,
                param_name=spec.name,
                reason=f"expected float, got {type(value).__name__}",
            )
        float_val = float(value)
        _check_numeric_bounds(step, node, spec, float_val)
        return float_val

    if ptype == "str":
        if not isinstance(value, str):
            raise ParameterConstraintError(
                step_id=step.step_id,
                node_id=node.node_id,
                param_name=spec.name,
                reason=f"expected str, got {type(value).__name__}",
            )
        if spec.choices is not None and value not in spec.choices:
            raise ParameterConstraintError(
                step_id=step.step_id,
                node_id=node.node_id,
                param_name=spec.name,
                reason=f"value {value!r} not in allowed choices {spec.choices}",
            )
        return value

    if ptype == "str_list":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ParameterConstraintError(
                step_id=step.step_id,
                node_id=node.node_id,
                param_name=spec.name,
                reason="expected list[str]",
            )
        if spec.required and not value:
            raise ParameterConstraintError(
                step_id=step.step_id,
                node_id=node.node_id,
                param_name=spec.name,
                reason="required str_list parameter must not be empty",
            )
        return list(value)

    raise ParameterConstraintError(  # pragma: no cover - guarded by ParamType Literal
        step_id=step.step_id,
        node_id=node.node_id,
        param_name=spec.name,
        reason=f"unsupported param_type {ptype!r}",
    )


def _check_numeric_bounds(
    step: RecipeStep, node: PrewrittenNode, spec: ParamSpec, numeric: float
) -> None:
    if spec.min_value is not None and numeric < spec.min_value:
        raise ParameterConstraintError(
            step_id=step.step_id,
            node_id=node.node_id,
            param_name=spec.name,
            reason=f"value {numeric} is below min_value {spec.min_value}",
        )
    if spec.max_value is not None and numeric > spec.max_value:
        raise ParameterConstraintError(
            step_id=step.step_id,
            node_id=node.node_id,
            param_name=spec.name,
            reason=f"value {numeric} exceeds max_value {spec.max_value}",
        )


def _find_cycle_path(step_ids: list[str], adj: dict[str, list[str]]) -> list[str]:
    """Extract a deterministic elementary cycle path [v0, v1, ..., v0] via three-color DFS."""
    state: dict[str, int] = dict.fromkeys(step_ids, 0)
    stack: list[str] = []
    pos_in_stack: dict[str, int] = {}

    def dfs(u: str) -> list[str] | None:
        state[u] = 1
        pos_in_stack[u] = len(stack)
        stack.append(u)
        for v in sorted(set(adj.get(u, []))):
            if state[v] == 0:
                found = dfs(v)
                if found is not None:
                    return found
            elif state[v] == 1:
                cycle_start = pos_in_stack[v]
                return [*stack[cycle_start:], v]
        stack.pop()
        pos_in_stack.pop(u, None)
        state[u] = 2
        return None

    for sid in step_ids:
        if state[sid] == 0:
            cycle = dfs(sid)
            if cycle is not None:
                return cycle
    return [step_ids[0], step_ids[0]]


def _enforce_governance_lens(step: RecipeStep, node: PrewrittenNode) -> None:
    """Enforce the Layer-1 Governance Lens before wiring any node into a DAG."""
    actual_sha = compute_code_sha256(node.source_code)
    if actual_sha != node.code_sha256:
        raise NodeGovernanceError(
            node.node_id,
            f"code_sha256 verification failed (stored {node.code_sha256!r}, computed {actual_sha!r}).",
            step_id=step.step_id,
        )
    tags = set(node.governance_tags)
    if "status:quarantined" in tags:
        raise NodeGovernanceError(
            node.node_id,
            "node is tagged 'status:quarantined' and cannot be compiled.",
            step_id=step.step_id,
        )
    if "status:verified" not in tags:
        raise NodeGovernanceError(
            node.node_id,
            f"node lacks required 'status:verified' governance tag (got {list(node.governance_tags)!r}).",
            step_id=step.step_id,
        )
    if node.spdx_license not in ALLOWED_SPDX_LICENSES:
        allowed_sorted = sorted(ALLOWED_SPDX_LICENSES)
        raise NodeGovernanceError(
            node.node_id,
            f"spdx_license {node.spdx_license!r} is not in allowlist {allowed_sorted}.",
            step_id=step.step_id,
        )


class DeterministicCompiler:
    """Compiles declarative RecipeSpecs into verified, fingerprinted DAGs and standalone Python."""

    def __init__(self, db: NodeDatabase) -> None:
        self.db = db

    def compile_recipe(self, recipe: RecipeSpec) -> CompiledPlan:
        """Alias for compile() enforcing the Layer-1 Governance Lens and static DAG gates."""
        return self.compile(recipe)

    def compile(self, recipe: RecipeSpec) -> CompiledPlan:
        """Validate governance, ports, params, wiring, and acyclicity, then emit a CompiledPlan."""
        if not recipe.steps:
            raise RecipeValidationError(
                "Recipe must declare at least one step.",
                code="empty_recipe",
            )

        steps_by_id: dict[str, RecipeStep] = {}
        decl_order: dict[str, int] = {}
        for idx, step in enumerate(recipe.steps):
            if step.step_id in steps_by_id:
                raise RecipeValidationError(
                    f"Duplicate step_id {step.step_id!r} in recipe {recipe.recipe_id!r}.",
                    code="duplicate_step_id",
                    diagnostics=[{"step_id": step.step_id}],
                )
            steps_by_id[step.step_id] = step
            decl_order[step.step_id] = idx

        all_step_ids = list(steps_by_id.keys())
        nodes_by_step: dict[str, PrewrittenNode] = {}
        params_by_step: dict[str, dict[str, Any]] = {}
        for step in recipe.steps:
            node = self.db.get_node(step.node_id)
            _enforce_governance_lens(step, node)
            nodes_by_step[step.step_id] = node
            params_by_step[step.step_id] = _validate_and_resolve_params(step, node)

        incoming_by_step: dict[str, list[RecipeEdge]] = {sid: [] for sid in all_step_ids}
        outgoing_by_step: dict[str, list[RecipeEdge]] = {sid: [] for sid in all_step_ids}
        wired_dst_ports: set[tuple[str, str]] = set()
        consumed_src_ports: set[tuple[str, str]] = set()

        for edge in recipe.edges:
            if edge.src_step not in steps_by_id:
                suggestion = _close_match(edge.src_step, all_step_ids)
                hint = f" Did you mean step {suggestion!r}?" if suggestion else ""
                raise RecipeValidationError(
                    f"Edge references unknown src_step {edge.src_step!r}.{hint}",
                    code="unknown_step",
                    diagnostics=[{"src_step": edge.src_step, "suggestion": suggestion}],
                )
            if edge.dst_step not in steps_by_id:
                suggestion = _close_match(edge.dst_step, all_step_ids)
                hint = f" Did you mean step {suggestion!r}?" if suggestion else ""
                raise RecipeValidationError(
                    f"Edge references unknown dst_step {edge.dst_step!r}.{hint}",
                    code="unknown_step",
                    diagnostics=[{"dst_step": edge.dst_step, "suggestion": suggestion}],
                )
            if edge.src_step == edge.dst_step:
                raise CycleDetectedError([edge.src_step, edge.dst_step])

            src_node = nodes_by_step[edge.src_step]
            dst_node = nodes_by_step[edge.dst_step]
            src_ports = {p.name: p for p in src_node.outputs}
            dst_ports = {p.name: p for p in dst_node.inputs}

            if edge.src_port not in src_ports:
                raise PortNotFoundError(
                    step_id=edge.src_step,
                    node_id=src_node.node_id,
                    direction="output",
                    port_name=edge.src_port,
                    available_ports=list(src_ports.keys()),
                    suggestion=_close_match(edge.src_port, list(src_ports.keys())),
                )
            if edge.dst_port not in dst_ports:
                raise PortNotFoundError(
                    step_id=edge.dst_step,
                    node_id=dst_node.node_id,
                    direction="input",
                    port_name=edge.dst_port,
                    available_ports=list(dst_ports.keys()),
                    suggestion=_close_match(edge.dst_port, list(dst_ports.keys())),
                )

            src_spec = src_ports[edge.src_port]
            dst_spec = dst_ports[edge.dst_port]
            if src_spec.port_type != dst_spec.port_type:
                raise PortTypeMismatchError(
                    src_step=edge.src_step,
                    src_port=edge.src_port,
                    src_type=src_spec.port_type,
                    dst_step=edge.dst_step,
                    dst_port=edge.dst_port,
                    dst_type=dst_spec.port_type,
                )

            consumed_src_ports.add((edge.src_step, edge.src_port))
            incoming_by_step[edge.dst_step].append(edge)
            outgoing_by_step[edge.src_step].append(edge)

        # Kahn's topological sort with declaration-order min-heap tie-breaking (runs before
        # duplicate_input_wiring so cyclic back-edges always surface CycleDetectedError first)
        adj: dict[str, list[str]] = {sid: [] for sid in all_step_ids}
        indegree: dict[str, int] = dict.fromkeys(all_step_ids, 0)
        seen_step_pairs: set[tuple[str, str]] = set()
        for edge in recipe.edges:
            pair = (edge.src_step, edge.dst_step)
            if pair not in seen_step_pairs:
                seen_step_pairs.add(pair)
                adj[edge.src_step].append(edge.dst_step)
                indegree[edge.dst_step] += 1

        ready_heap: list[tuple[int, str]] = [
            (decl_order[sid], sid) for sid in all_step_ids if indegree[sid] == 0
        ]
        heapq.heapify(ready_heap)
        topo_order: list[str] = []
        while ready_heap:
            _, sid = heapq.heappop(ready_heap)
            topo_order.append(sid)
            for nxt in adj[sid]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    heapq.heappush(ready_heap, (decl_order[nxt], nxt))

        if len(topo_order) != len(all_step_ids):
            remaining = [sid for sid in all_step_ids if sid not in set(topo_order)]
            sub_adj = {sid: [dst for dst in adj[sid] if dst in set(remaining)] for sid in remaining}
            raise CycleDetectedError(_find_cycle_path(remaining, sub_adj))

        for edge in recipe.edges:
            dst_key = (edge.dst_step, edge.dst_port)
            if dst_key in wired_dst_ports:
                raise RecipeValidationError(
                    f"Input port {edge.dst_step}.{edge.dst_port} is wired by multiple upstream edges.",
                    code="duplicate_input_wiring",
                    diagnostics=[{"dst_step": edge.dst_step, "dst_port": edge.dst_port}],
                )
            wired_dst_ports.add(dst_key)

        declared_external: set[tuple[str, str]] = set()
        for ext in recipe.external_inputs:
            sid, sep, pname = ext.partition(".")
            if not sep or sid not in steps_by_id:
                raise RecipeValidationError(
                    f"Invalid external_inputs entry {ext!r}; expected '<step_id>.<port_name>'.",
                    code="invalid_external_input",
                )
            in_map = {p.name: p for p in nodes_by_step[sid].inputs}
            if pname not in in_map:
                raise PortNotFoundError(
                    step_id=sid,
                    node_id=nodes_by_step[sid].node_id,
                    direction="input",
                    port_name=pname,
                    available_ports=list(in_map.keys()),
                    suggestion=_close_match(pname, list(in_map.keys())),
                )
            if (sid, pname) in wired_dst_ports:
                raise RecipeValidationError(
                    f"Port {ext!r} cannot be both wired by an edge and listed in external_inputs.",
                    code="conflicting_external_input",
                )
            declared_external.add((sid, pname))

        # Entry inputs vs. missing internal required wiring
        entry_inputs_by_step: dict[str, list[PortSpec]] = {sid: [] for sid in all_step_ids}
        graph_entry_inputs: list[GraphEntryInput] = []
        topo_pos = {sid: idx for idx, sid in enumerate(topo_order)}

        for sid in topo_order:
            node = nodes_by_step[sid]
            is_root = len(incoming_by_step[sid]) == 0
            for port in node.inputs:
                if (sid, port.name) in wired_dst_ports:
                    continue
                if is_root or (sid, port.name) in declared_external:
                    entry_inputs_by_step[sid].append(port)
                    graph_entry_inputs.append(
                        GraphEntryInput(
                            step_id=sid,
                            port_name=port.name,
                            port_type=port.port_type,
                            required=port.required,
                            description=port.description,
                        )
                    )
                elif port.required:
                    compatible_sources = [
                        f"{cand}.{out.name}"
                        for cand in topo_order[: topo_pos[sid]]
                        for out in nodes_by_step[cand].outputs
                        if out.port_type == port.port_type
                    ]
                    hint = (
                        f" Compatible upstream outputs: {', '.join(compatible_sources)}."
                        if compatible_sources
                        else ""
                    )
                    raise RecipeValidationError(
                        f"Required input port {sid}.{port.name} (type {port.port_type!r}) on internal step "
                        f"{sid!r} ({node.node_id}) is unwired.{hint}",
                        code="missing_required_input",
                        diagnostics=[
                            {
                                "step_id": sid,
                                "node_id": node.node_id,
                                "port": port.name,
                                "port_type": port.port_type,
                                "compatible_sources": compatible_sources,
                            }
                        ],
                    )

        # Static dead/isolated step warnings
        warnings: list[CompilerWarning] = []
        if len(all_step_ids) > 1:
            for sid in topo_order:
                node = nodes_by_step[sid]
                no_in = len(incoming_by_step[sid]) == 0
                no_out = len(outgoing_by_step[sid]) == 0
                if no_in and no_out:
                    warnings.append(
                        CompilerWarning(
                            code="isolated_step",
                            step_id=sid,
                            message=(
                                f"Step {sid!r} ({node.node_id}) is disconnected from the rest of the DAG."
                            ),
                        )
                    )
                elif no_out and node.category in TRANSFORM_CATEGORIES:
                    warnings.append(
                        CompilerWarning(
                            code="dangling_transform",
                            step_id=sid,
                            message=(
                                f"Transform step {sid!r} ({node.node_id}) has no downstream consumers."
                            ),
                        )
                    )

        # Merkle upstream sub-DAG fingerprints
        fingerprints: dict[str, str] = {}
        compiled_steps: list[CompiledStep] = []
        node_digests: list[str] = []
        for sid in topo_order:
            node = nodes_by_step[sid]
            resolved_params = params_by_step[sid]
            sorted_in = sorted(incoming_by_step[sid], key=lambda e: e.dst_port)
            entry_ports = entry_inputs_by_step[sid]
            fp_payload = {
                "node_id": node.node_id,
                "code_sha256": node.code_sha256,
                "params": resolved_params,
                "wired_inputs": [
                    {
                        "dst_port": edge.dst_port,
                        "src_fingerprint": fingerprints[edge.src_step],
                        "src_port": edge.src_port,
                    }
                    for edge in sorted_in
                ],
                "entry_ports": [p.name for p in entry_ports],
            }
            fp = sha256_hex(canonical_json(fp_payload))
            fingerprints[sid] = fp
            node_digests.append(f"{sid}:{node.node_id}@{node.code_sha256}")
            compiled_steps.append(
                CompiledStep(
                    step_id=sid,
                    node_id=node.node_id,
                    version=node.version,
                    function_name=node.function_name,
                    code_sha256=node.code_sha256,
                    resolved_params=resolved_params,
                    incoming_edges=sorted_in,
                    entry_inputs=entry_ports,
                    outputs=node.outputs,
                    subgraph_fingerprint=fp,
                )
            )

        terminal_outputs: list[TerminalOutputSpec] = []
        for sid in topo_order:
            for out_port in nodes_by_step[sid].outputs:
                if (sid, out_port.name) not in consumed_src_ports:
                    terminal_outputs.append(
                        TerminalOutputSpec(
                            step_id=sid,
                            port_name=out_port.name,
                            port_type=out_port.port_type,
                        )
                    )

        recipe_sha = recipe.canonical_sha256()
        plan_payload = {
            "recipe_id": recipe.recipe_id,
            "recipe_sha256": recipe_sha,
            "topological_order": topo_order,
            "steps": [s.model_dump(mode="json") for s in compiled_steps],
            "edges": [e.model_dump(mode="json") for e in recipe.edges],
            "entry_inputs": [g.model_dump(mode="json") for g in graph_entry_inputs],
            "terminal_outputs": [t.model_dump(mode="json") for t in terminal_outputs],
            "node_digests": node_digests,
        }
        plan_sha = sha256_hex(canonical_json(plan_payload))

        return CompiledPlan(
            recipe_id=recipe.recipe_id,
            title=recipe.title,
            goal=recipe.goal,
            recipe_sha256=recipe_sha,
            topological_order=topo_order,
            steps=compiled_steps,
            edges=list(recipe.edges),
            entry_inputs=graph_entry_inputs,
            terminal_outputs=terminal_outputs,
            node_digests=node_digests,
            warnings=warnings,
            plan_sha256=plan_sha,
        )

    def validated_plan_nodes(self, plan: CompiledPlan) -> dict[str, PrewrittenNode]:
        """Snapshot current verified nodes and reject plans whose source or policy changed."""
        payload = plan.model_dump(mode="json", exclude={"title", "goal", "warnings", "plan_sha256"})
        if sha256_hex(canonical_json(payload)) != plan.plan_sha256:
            raise RecipeValidationError(
                "Compiled plan digest mismatch; recompile the recipe.",
                code="plan_integrity_mismatch",
            )
        nodes: dict[str, PrewrittenNode] = {}
        for step in plan.steps:
            node = self.db.get_node(step.node_id)
            _enforce_governance_lens(RecipeStep(step_id=step.step_id, node_id=step.node_id), node)
            expected_digest = f"{step.step_id}:{node.node_id}@{node.code_sha256}"
            if (
                node.version != step.version
                or node.code_sha256 != step.code_sha256
                or node.function_name != step.function_name
                or node.outputs != step.outputs
                or expected_digest not in plan.node_digests
            ):
                raise NodeGovernanceError(
                    node.node_id,
                    "Compiled node revision changed; recompile the recipe.",
                    step_id=step.step_id,
                )
            nodes[node.node_id] = node
        return nodes

    def emit_python_from_plan(self, plan: CompiledPlan) -> str:
        """Emit a standalone, zero-dependency Python 3.12 pipeline module from a CompiledPlan."""
        verified_nodes = self.validated_plan_nodes(plan)
        unique_node_ids: list[str] = []
        for step in plan.steps:
            if step.node_id not in unique_node_ids:
                unique_node_ids.append(step.node_id)

        port_counts: dict[str, int] = {}
        for entry in plan.entry_inputs:
            port_counts[entry.port_name] = port_counts.get(entry.port_name, 0) + 1
        ambiguous_ports = sorted(name for name, count in port_counts.items() if count > 1)

        module_doc = (
            f"Standalone deterministic pipeline compiled for recipe {plan.recipe_id!r}.\n\n"
            f"Title: {plan.title}\nRecipe SHA-256: {plan.recipe_sha256}\n"
            f"Plan SHA-256: {plan.plan_sha256}\nLLM tokens at runtime: 0"
        )
        lines: list[str] = [
            repr(module_doc),
            "",
            "from __future__ import annotations",
            "",
            "import copy",
            "import math",
            "from typing import Any",
            "",
            f"RECIPE_ID = {plan.recipe_id!r}",
            f"RECIPE_SHA256 = {plan.recipe_sha256!r}",
            f"PLAN_SHA256 = {plan.plan_sha256!r}",
            f"TOPOLOGICAL_ORDER = {plan.topological_order!r}",
            f"NODE_DIGESTS = {plan.node_digests!r}",
            f"_AMBIGUOUS_ENTRY_PORTS = set({ambiguous_ports!r})",
            "",
        ]

        lines.extend([inspect.getsource(port_value_matches).rstrip(), ""])
        for node_id in unique_node_ids:
            node = verified_nodes[node_id]
            lines.append(
                f"# --- Prewritten Verified Node: {node.node_id} @ sha256:{node.code_sha256} ---"
            )
            lines.append(node.source_code.rstrip())
            lines.append("")

        lines.extend(
            [
                "def _resolve_entry_input(",
                "    initial_inputs: dict[str, Any],",
                "    step_id: str,",
                "    port_name: str,",
                "    required: bool,",
                ") -> tuple[bool, Any]:",
                '    qualified = f"{step_id}.{port_name}"',
                "    if qualified in initial_inputs:",
                "        return True, copy.deepcopy(initial_inputs[qualified])",
                "    if port_name in initial_inputs:",
                "        if port_name in _AMBIGUOUS_ENTRY_PORTS:",
                "            raise ValueError(",
                '                f"Ambiguous entry port {port_name!r}; qualify as {qualified!r}."',
                "            )",
                "        return True, copy.deepcopy(initial_inputs[port_name])",
                "    if required:",
                "        raise ValueError(",
                '            f"Missing required entry input {qualified!r} (or {port_name!r})."',
                "        )",
                "    return False, None",
                "",
                "",
                "def run_pipeline(initial_inputs: dict[str, Any]) -> dict[str, Any]:",
                '    """Execute compiled DAG in deterministic topological order with zero LLM calls."""',
                "    step_outputs: dict[str, dict[str, Any]] = {}",
            ]
        )

        for step in plan.steps:
            lines.append("")
            lines.append(
                f"    # Step {step.step_id!r}: {step.node_id} (subgraph_fp={step.subgraph_fingerprint[:12]}...)"
            )
            in_var = f"_in_{step.step_id}"
            lines.append(f"    {in_var}: dict[str, Any] = {{}}")
            for entry_port in step.entry_inputs:
                lines.append(
                    f"    _present, _val = _resolve_entry_input("
                    f"initial_inputs, {step.step_id!r}, {entry_port.name!r}, {entry_port.required!r})"
                )
                lines.append("    if _present:")
                lines.append(f"        if not port_value_matches({entry_port.port_type!r}, _val):")
                error_message = (
                    f"Entry input {step.step_id}.{entry_port.name}: expected {entry_port.port_type}"
                )
                lines.append(f"            raise ValueError({error_message!r})")
                lines.append(f"        {in_var}[{entry_port.name!r}] = _val")
            for edge in step.incoming_edges:
                lines.append(
                    f"    {in_var}[{edge.dst_port!r}] = copy.deepcopy("
                    f"step_outputs[{edge.src_step!r}][{edge.src_port!r}])"
                )
            formatted_params = pprint.pformat(step.resolved_params, width=88, sort_dicts=True)
            param_lines = formatted_params.splitlines()
            if len(param_lines) == 1:
                lines.append(f"    _params_{step.step_id}: dict[str, Any] = {param_lines[0]}")
            else:
                lines.append(f"    _params_{step.step_id}: dict[str, Any] = (")
                for pline in param_lines:
                    lines.append(f"        {pline}")
                lines.append("    )")
            lines.append(
                f"    step_outputs[{step.step_id!r}] = {step.function_name}({in_var}, _params_{step.step_id})"
            )
            for port in step.outputs:
                lines.append(f"    _out = step_outputs[{step.step_id!r}]")
                lines.append(
                    f"    if not isinstance(_out, dict) or {port.name!r} not in _out or not port_value_matches({port.port_type!r}, _out[{port.name!r}]):"
                )
                error_message = f"Output {step.step_id}.{port.name}: expected {port.port_type}"
                lines.append(f"        raise ValueError({error_message!r})")

        lines.append("")
        lines.append("    terminal_outputs: dict[str, dict[str, Any]] = {}")
        for term in plan.terminal_outputs:
            lines.append(
                f"    terminal_outputs.setdefault({term.step_id!r}, {{}})[{term.port_name!r}] = "
                f"step_outputs[{term.step_id!r}][{term.port_name!r}]"
            )
        lines.append(
            '    return {"step_outputs": step_outputs, "terminal_outputs": terminal_outputs}'
        )
        lines.append("")
        return "\n".join(lines)

    def compile_to_python(self, recipe: RecipeSpec) -> str:
        """Compile a RecipeSpec and emit its standalone verified Python module."""
        plan = self.compile(recipe)
        return self.emit_python_from_plan(plan)


DAGCompiler = DeterministicCompiler
