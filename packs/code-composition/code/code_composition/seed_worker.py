"""Worker-side checks and execution for one claimed compile/execute seed.

A deterministic helper that runs inside a claimed `verb.compile_dag`; it is not a task,
scheduler or loop. It receives the records the worker already read from Tessera, verifies
every pin against the local verified installation (the packaged catalog unless the worker
passes its own node database) and executes only that installation's code. It makes no network,
subprocess, model, enqueue or publication call. Source code copied from a noun is compared,
never executed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from code_composition.compiler import DeterministicCompiler
from code_composition.errors import SeedVerificationError
from code_composition.registry import NodeDatabase, verify_node_self_tests
from code_composition.runtime import DeterministicRuntime
from code_composition.schemas import ExecutionResult, RecipeSpec
from code_composition.seed_pack import (
    TASK_CONTRACT,
    node_body,
    runtime_module_digests,
    value_sha256,
)


def verify_pinned_records(
    brief: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Check each `input_refs` pin against the record read back for it; return values by key.

    `records` maps record keys to Tessera record JSON with at least `version` and `value`.
    """
    if brief.get("contract") != TASK_CONTRACT:
        raise SeedVerificationError(
            f"Unsupported seed contract {brief.get('contract')!r}.", code="seed_contract_unknown"
        )
    values: dict[str, Any] = {}
    for ref in brief["input_refs"]:
        record = records.get(ref["key"])
        if record is None:
            raise SeedVerificationError(
                f"Pinned input {ref['key']} was not read.", code="seed_input_missing"
            )
        if (
            record.get("store", ref["store"]) != ref["store"]
            or record.get("version") != ref["version"]
        ):
            raise SeedVerificationError(
                f"Pinned input {ref['key']} was read from a different store or version.",
                code="seed_input_changed",
            )
        if value_sha256(record.get("value")) != ref["value_sha256"]:
            raise SeedVerificationError(
                f"Pinned input {ref['key']} value digest differs from its pin.",
                code="seed_input_changed",
            )
        values[ref["key"]] = record["value"]
    for name in ("recipe_ref", "runtime_ref"):
        if brief[name] not in brief["input_refs"]:
            raise SeedVerificationError(f"{name} is not pinned in input_refs.")
    return values


def _check_runtime(runtime_value: Mapping[str, Any]) -> None:
    expected = runtime_value.get("tool", {}).get("module_sha256")
    actual = runtime_module_digests()
    if expected != actual:
        changed = sorted(
            name
            for name in set(actual) | set(expected or {})
            if (expected or {}).get(name) != actual.get(name)
        )
        raise SeedVerificationError(
            f"Local compiler/runtime modules differ from the pinned runtime noun: {changed}.",
            code="seed_runtime_mismatch",
        )


def execute_seed_task(
    brief: Mapping[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    db: NodeDatabase | None = None,
) -> ExecutionResult:
    """Verify every pin, recompile, require the pinned plan digest and execute deterministically.

    Without `db`, a fresh in-memory packaged catalog is used; its registration reruns every
    node's integrity and built-in tests. Any mismatch raises `SeedVerificationError`, which a
    worker reports as a `blocked` outcome.
    """
    values = verify_pinned_records(brief, records)
    recipe_key = brief["recipe_ref"]["key"]
    runtime_key = brief["runtime_ref"]["key"]
    recipe_value = values[recipe_key]
    _check_runtime(values[runtime_key])

    pinned_keys = {ref["key"] for ref in brief["input_refs"]}
    for edge in recipe_value.get("relations", []):
        if edge.get("relation") == "requires_noun" and edge.get("target_id") not in pinned_keys:
            raise SeedVerificationError(
                f"Recipe requires {edge.get('target_id')}, which the task does not pin."
            )
    node_docs: list[Mapping[str, Any]] = []
    for key in sorted(pinned_keys - {recipe_key, runtime_key}):
        document = values[key].get("node") if isinstance(values[key], Mapping) else None
        if not isinstance(document, Mapping):
            raise SeedVerificationError(f"Pinned input {key} is not a prewritten node tool noun.")
        node_docs.append(document)

    local = NodeDatabase(":memory:") if db is None else db
    try:
        pinned_ids: set[str] = set()
        for document in node_docs:
            node = local.get_node(str(document["node_id"]))
            if node_body(node) != document:
                raise SeedVerificationError(
                    f"Local node {node.node_id} differs from its pinned tool noun.",
                    code="seed_node_mismatch",
                )
            verify_node_self_tests(node)
            pinned_ids.add(node.node_id)
        recipe = RecipeSpec.model_validate(recipe_value["recipe"])
        unpinned = sorted({step.node_id for step in recipe.steps} - pinned_ids)
        if unpinned:
            raise SeedVerificationError(f"Recipe steps use unpinned nodes {unpinned}.")
        compiler = DeterministicCompiler(local)
        plan = compiler.compile(recipe)
        expected_plan = recipe_value["local_checks"]["compiled_plan_sha256"]
        if plan.plan_sha256 != expected_plan:
            raise SeedVerificationError(
                f"Recompiled plan {plan.plan_sha256} differs from pinned {expected_plan}.",
                code="seed_plan_mismatch",
            )
        result = DeterministicRuntime(local, compiler).execute(
            plan, recipe_value["sample_inputs"], verify_emitted_python=True
        )
        if (
            not result.python_equivalence_verified
            or result.receipt.plan_sha256 != expected_plan
            or result.receipt.llm_tokens_at_runtime != 0
        ):
            raise SeedVerificationError("Execution evidence does not match the pinned plan.")
        return result
    finally:
        if db is None:
            local.close()
