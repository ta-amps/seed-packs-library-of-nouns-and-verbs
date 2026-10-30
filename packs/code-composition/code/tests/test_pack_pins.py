"""The seed pack's pins match this code: modules, nodes, recipes, runs and the worked example.

The library keeps this code in the code-composition pack. Its build pins the folder digest; these
tests check every other digest the pack records. They skip outside the library, and fail instead
with CODE_COMPOSITION_REQUIRE_PACK=1, as CI sets it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from code_composition.compiler import DeterministicCompiler
from code_composition.recipe_catalog import load_catalog_recipes, sample_inputs_for_recipe
from code_composition.registry import NodeDatabase
from code_composition.runtime import DeterministicRuntime
from code_composition.schemas import ExecutionResult, RecipeSpec, canonical_json, sha256_hex
from code_composition.seed_nodes import build_seed_nodes
from code_composition.seed_pack import REPOSITORY_PATH, canonical_value, runtime_module_digests

ROOT = Path(__file__).resolve().parents[1]
NOUNS = ROOT.parent / "nouns.json"


def pack_values() -> list[dict[str, Any]]:
    if not NOUNS.is_file():
        if os.environ.get("CODE_COMPOSITION_REQUIRE_PACK") == "1":
            pytest.fail(f"The pack's nouns.json is missing at {NOUNS}.")
        pytest.skip("Runs inside the seed pack library, next to the pack's nouns.json.")
    records = json.loads(NOUNS.read_text(encoding="utf-8"))["records"]
    return [record["value"] for record in records]


def by_role(values: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    return [value for value in values if value["role"] == role]


def run(db: NodeDatabase, recipe: dict[str, Any], inputs: dict[str, Any]) -> ExecutionResult:
    compiler = DeterministicCompiler(db)
    plan = compiler.compile(RecipeSpec.model_validate(recipe))
    return DeterministicRuntime(db, compiler).execute(plan, inputs, verify_emitted_python=True)


def test_tool_card_runtime_and_node_pins_match_this_code() -> None:
    values = pack_values()
    (card,) = by_role(values, "tool_card")
    assert card["pin"]["folder"]["path"] == REPOSITORY_PATH
    (runtime,) = by_role(values, "runtime_manifest")
    local = {Path(name).name: digest for name, digest in runtime_module_digests().items()}
    assert runtime["module_sha256"] == local
    nodes = {value["node_id"]: value for value in by_role(values, "prewritten_node")}
    packaged = {node.node_id: node for node in build_seed_nodes()}
    assert set(nodes) == set(packaged)
    for node_id, noun in nodes.items():
        assert noun["code"]["code_sha256"] == packaged[node_id].code_sha256, node_id
        assert noun["function_name"] == packaged[node_id].function_name, node_id


def test_recipe_and_run_pins_match_this_code() -> None:
    recipes = {value["recipe"]["recipe_id"]: value for value in by_role(pack_values(), "recipe")}
    authored = {spec.recipe_id: (path, spec) for path, spec in load_catalog_recipes()}
    assert set(recipes) == set(authored)
    for recipe_id, noun in recipes.items():
        path, spec = authored[recipe_id]
        in_folder = noun["as_in_the_code_folder"]
        assert in_folder["path"] == f"{REPOSITORY_PATH}/{path}"
        data = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == in_folder["file_sha256"], recipe_id
        stored = RecipeSpec.model_validate(noun["recipe"])
        assert canonical_value(stored.model_dump(mode="json")) == canonical_value(
            spec.model_dump(mode="json")
        )
        inputs = canonical_value(sample_inputs_for_recipe(recipe_id))
        assert noun["sample_inputs"] == inputs
        assert sha256_hex(canonical_json(inputs)) == noun["sample_inputs_sha256"]
        db = NodeDatabase(":memory:")
        try:
            compiler = DeterministicCompiler(db)
            from_file = compiler.compile(spec)
            assert from_file.recipe_sha256 == in_folder["recipe_sha256"], recipe_id
            assert from_file.plan_sha256 == in_folder["plan_sha256"], recipe_id
            plan = compiler.compile(stored)
            here = noun["as_stored_here"]
            assert plan.recipe_sha256 == here["recipe_sha256"], recipe_id
            assert plan.plan_sha256 == here["plan_sha256"], recipe_id
            emitted = compiler.emit_python_from_plan(plan)
            assert sha256_hex(emitted) == here["emitted_python_sha256"], recipe_id
            result = DeterministicRuntime(db, compiler).execute(
                plan, inputs, verify_emitted_python=True
            )
        finally:
            db.close()
        expected, receipt = noun["expected_run"], result.receipt
        assert receipt.input_sha256 == expected["input_sha256"], recipe_id
        assert receipt.output_sha256 == expected["output_sha256"], recipe_id
        assert receipt.receipt_sha256 == expected["receipt_sha256"], recipe_id
        assert len(receipt.executed_steps) == expected["executed_steps"]
        assert len(receipt.memo_hits) == expected["memo_hits"]
        assert result.python_equivalence_verified is expected["python_equivalence_verified"]
        assert receipt.llm_tokens_at_runtime == expected["llm_tokens_at_runtime"] == 0


def test_worked_example_matches_this_code() -> None:
    values = pack_values()
    (example,) = by_role(values, "example")
    (card,) = by_role(values, "tool_card")
    instance = example["instance"]
    assert instance["tool_code"] == card["pin"]["folder"]
    base = next(
        v
        for v in by_role(values, "recipe")
        if v["recipe"]["recipe_id"] == instance["baseline_ref"].rsplit(".", 1)[-1]
    )
    variant = copy.deepcopy(base["recipe"])
    for step in variant["steps"]:
        if step["step_id"] == "score_arm_b":
            step["params"].update(weights_csv="11.5,0.012", bias=-2.5)
    db = NodeDatabase(":memory:")
    try:
        first = run(db, base["recipe"], base["sample_inputs"])
        second = run(db, variant, base["sample_inputs"])
    finally:
        db.close()
    assert first.receipt.output_sha256 == instance["baseline_output_sha256"]
    assert second.receipt.output_sha256 == instance["variant_output_sha256"]
    assert second.receipt.memo_hits == instance["variant_memo_hits"]
    assert second.receipt.executed_steps == instance["variant_executed"]
    assert first.python_equivalence_verified and second.python_equivalence_verified
