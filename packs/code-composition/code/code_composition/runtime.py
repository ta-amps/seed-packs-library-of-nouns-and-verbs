"""Deterministic DAG execution engine, sub-DAG memoizer, receipt minter, and Python equivalence prover."""

from __future__ import annotations

import copy
import types
from typing import Any

from code_composition.compiler import DeterministicCompiler
from code_composition.errors import CodeCompositionError, ExecutionInputError, NodeVerificationError
from code_composition.public_limits import check_public_step, check_public_value
from code_composition.registry import NodeDatabase, load_node_callable, verify_node_outputs
from code_composition.schemas import (
    CompiledPlan,
    ExecutionReceipt,
    ExecutionResult,
    PortType,
    RecipeSpec,
    canonical_json,
    port_value_matches,
    sha256_hex,
)


def _check_runtime_port_type(label: str, port_type: PortType, value: Any) -> None:
    """Validate runtime entry payload shape against declared PortType."""
    if not port_value_matches(port_type, value):
        raise ExecutionInputError(
            f"Entry input {label!r} expected PortType {port_type!r}, got {type(value).__name__}."
        )


def execute_emitted_python(python_source: str, initial_inputs: dict[str, Any]) -> dict[str, Any]:
    """Run trusted emitted Python in a separate in-process module, not a security sandbox."""
    mod = types.ModuleType("_emitted_pipeline")
    compiled = compile(python_source, "<emitted_pipeline>", "exec")
    exec(compiled, mod.__dict__)
    run_fn = mod.__dict__.get("run_pipeline")
    if not callable(run_fn):
        raise RuntimeError("Emitted Python module did not define callable run_pipeline().")
    output: dict[str, Any] = run_fn(copy.deepcopy(initial_inputs))
    return output


class DeterministicRuntime:
    """Executes a CompiledPlan with zero LLM calls, SQLite sub-DAG caching, and SHA-256 receipts."""

    def __init__(
        self,
        db: NodeDatabase,
        compiler: DeterministicCompiler | None = None,
    ) -> None:
        self.db = db
        self.compiler = compiler or DeterministicCompiler(db)

    def _resolve_all_entry_inputs(
        self, plan: CompiledPlan, initial_inputs: dict[str, Any]
    ) -> dict[tuple[str, str], Any]:
        port_counts: dict[str, int] = {}
        for entry in plan.entry_inputs:
            port_counts[entry.port_name] = port_counts.get(entry.port_name, 0) + 1
        ambiguous = {name for name, count in port_counts.items() if count > 1}

        resolved: dict[tuple[str, str], Any] = {}
        for entry in plan.entry_inputs:
            qualified = f"{entry.step_id}.{entry.port_name}"
            if qualified in initial_inputs:
                val = copy.deepcopy(initial_inputs[qualified])
                _check_runtime_port_type(qualified, entry.port_type, val)
                resolved[(entry.step_id, entry.port_name)] = val
            elif entry.port_name in initial_inputs:
                if entry.port_name in ambiguous:
                    raise ExecutionInputError(
                        f"Ambiguous entry port {entry.port_name!r} appears on multiple root steps; "
                        f"pass qualified key {qualified!r}.",
                        diagnostics=[{"step_id": entry.step_id, "port": entry.port_name}],
                    )
                val = copy.deepcopy(initial_inputs[entry.port_name])
                _check_runtime_port_type(qualified, entry.port_type, val)
                resolved[(entry.step_id, entry.port_name)] = val
            elif entry.required:
                raise ExecutionInputError(
                    f"Missing required entry input {qualified!r} (PortType {entry.port_type!r}).",
                    diagnostics=[
                        {
                            "step_id": entry.step_id,
                            "port": entry.port_name,
                            "port_type": entry.port_type,
                        }
                    ],
                )
        return resolved

    def execute(
        self,
        recipe_or_plan: RecipeSpec | CompiledPlan,
        initial_inputs: dict[str, Any],
        *,
        use_memo_cache: bool = True,
        verify_emitted_python: bool = False,
        persist_receipt: bool = True,
        public_preview: bool = False,
    ) -> ExecutionResult:
        """Execute a RecipeSpec or CompiledPlan deterministically and record an ExecutionReceipt."""
        plan = (
            self.compiler.compile(recipe_or_plan)
            if isinstance(recipe_or_plan, RecipeSpec)
            else recipe_or_plan
        )
        if public_preview:
            check_public_value(initial_inputs)
        verified_nodes = self.compiler.validated_plan_nodes(plan)
        entry_values = self._resolve_all_entry_inputs(plan, initial_inputs)

        normalized_input_map = {
            f"{sid}.{pname}": val for (sid, pname), val in sorted(entry_values.items())
        }
        overall_input_sha = sha256_hex(canonical_json(normalized_input_map))

        step_outputs: dict[str, dict[str, Any]] = {}
        step_input_digests: dict[str, str] = {}
        memo_hits: list[str] = []
        executed_steps: list[str] = []

        for step in plan.steps:
            self_entry_dict: dict[str, Any] = {}
            step_call_inputs: dict[str, Any] = {}
            for port in step.entry_inputs:
                if (step.step_id, port.name) in entry_values:
                    val = copy.deepcopy(entry_values[(step.step_id, port.name)])
                    self_entry_dict[port.name] = val
                    step_call_inputs[port.name] = val

            for edge in step.incoming_edges:
                step_call_inputs[edge.dst_port] = copy.deepcopy(
                    step_outputs[edge.src_step][edge.src_port]
                )

            in_digest_payload = {
                "self_inputs": self_entry_dict,
                "wired_inputs": [
                    {
                        "dst_port": edge.dst_port,
                        "src_input_sha256": step_input_digests[edge.src_step],
                        "src_port": edge.src_port,
                    }
                    for edge in step.incoming_edges
                ],
            }
            sub_input_sha = sha256_hex(canonical_json(in_digest_payload))
            step_input_digests[step.step_id] = sub_input_sha

            if public_preview:
                check_public_step(step.node_id, step_call_inputs, step.resolved_params)
            cached = (
                self.db.get_cached_subgraph(step.subgraph_fingerprint, sub_input_sha)
                if use_memo_cache
                else None
            )
            if cached is not None:
                verify_node_outputs(step.node_id, step.outputs, cached, context="Cache read")
                if public_preview:
                    check_public_value(cached)
                    if len(canonical_json(cached).encode("utf-8")) > 262144:
                        raise ExecutionInputError("Public step output exceeds 256 KiB.")
                step_outputs[step.step_id] = cached
                memo_hits.append(step.step_id)
                continue

            node = verified_nodes[step.node_id]
            fn = load_node_callable(node)
            try:
                out = fn(step_call_inputs, copy.deepcopy(step.resolved_params))
            except CodeCompositionError:
                raise
            except Exception as exc:
                raise ExecutionInputError(
                    f"Step {step.step_id!r} ({step.node_id}) execution error: {exc}",
                    diagnostics=[{"step_id": step.step_id, "node_id": step.node_id}],
                ) from exc

            if public_preview:
                check_public_value(out)
                if len(canonical_json(out).encode("utf-8")) > 262144:
                    raise ExecutionInputError("Public step output exceeds 256 KiB.")
            verify_node_outputs(step.node_id, step.outputs, out, context=f"Step {step.step_id}")

            step_outputs[step.step_id] = out
            executed_steps.append(step.step_id)
            if use_memo_cache:
                self.db.put_cached_subgraph(
                    step.subgraph_fingerprint,
                    sub_input_sha,
                    step.node_id,
                    out,
                )

        terminal_outputs: dict[str, dict[str, Any]] = {}
        for term in plan.terminal_outputs:
            terminal_outputs.setdefault(term.step_id, {})[term.port_name] = step_outputs[
                term.step_id
            ][term.port_name]

        output_sha = sha256_hex(canonical_json(terminal_outputs))
        receipt_core = {
            "recipe_id": plan.recipe_id,
            "recipe_sha256": plan.recipe_sha256,
            "plan_sha256": plan.plan_sha256,
            "node_digests": plan.node_digests,
            "input_sha256": overall_input_sha,
            "output_sha256": output_sha,
            "memo_hits": memo_hits,
            "executed_steps": executed_steps,
            "llm_tokens_at_runtime": 0,
        }
        receipt_sha = sha256_hex(canonical_json(receipt_core))
        receipt = ExecutionReceipt(
            receipt_id=f"rcpt_{receipt_sha[:16]}",
            recipe_id=plan.recipe_id,
            recipe_sha256=plan.recipe_sha256,
            plan_sha256=plan.plan_sha256,
            node_digests=plan.node_digests,
            input_sha256=overall_input_sha,
            output_sha256=output_sha,
            memo_hits=memo_hits,
            executed_steps=executed_steps,
            llm_tokens_at_runtime=0,
            receipt_sha256=receipt_sha,
        )
        if persist_receipt:
            self.db.record_receipt(receipt)

        verified_equiv = False
        if verify_emitted_python:
            verified_equiv = self.verify_python_equivalence(
                plan, initial_inputs, step_outputs, terminal_outputs
            )

        return ExecutionResult(
            plan=plan,
            step_outputs=step_outputs,
            terminal_outputs=terminal_outputs,
            receipt=receipt,
            python_equivalence_verified=verified_equiv,
        )

    def verify_python_equivalence(
        self,
        plan: CompiledPlan,
        initial_inputs: dict[str, Any],
        expected_step_outputs: dict[str, dict[str, Any]] | None = None,
        expected_terminal_outputs: dict[str, dict[str, Any]] | None = None,
    ) -> bool:
        """Prove that running compiler-emitted standalone Python yields byte-identical outputs."""
        python_source = self.compiler.emit_python_from_plan(plan)
        emitted = execute_emitted_python(python_source, initial_inputs)
        if expected_step_outputs is None or expected_terminal_outputs is None:
            ref = self.execute(
                plan, initial_inputs, use_memo_cache=False, verify_emitted_python=False
            )
            expected_step_outputs = ref.step_outputs
            expected_terminal_outputs = ref.terminal_outputs

        if canonical_json(emitted["step_outputs"]) != canonical_json(expected_step_outputs):
            raise NodeVerificationError(
                plan.recipe_id,
                "Emitted standalone Python step_outputs diverged from in-memory DAG runtime.",
            )
        if canonical_json(emitted["terminal_outputs"]) != canonical_json(expected_terminal_outputs):
            raise NodeVerificationError(
                plan.recipe_id,
                "Emitted standalone Python terminal_outputs diverged from in-memory DAG runtime.",
            )
        return True
