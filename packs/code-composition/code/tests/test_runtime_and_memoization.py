"""Tests for DeterministicRuntime, standalone Python equivalence, sub-DAG cache, and receipts."""

from __future__ import annotations

from pathlib import Path

import pytest

from code_composition.compiler import DeterministicCompiler
from code_composition.composer import load_example_recipes, sample_inputs_for_recipe
from code_composition.errors import ExecutionInputError
from code_composition.registry import NodeDatabase
from code_composition.runtime import DeterministicRuntime, execute_emitted_python
from code_composition.schemas import RecipeEdge, RecipeSpec, RecipeStep, canonical_json


def test_all_example_recipes_execute_and_match_emitted_python_byte_for_byte(
    tmp_path: Path,
) -> None:
    db = NodeDatabase(tmp_path / "exec.db")
    compiler = DeterministicCompiler(db)
    runtime = DeterministicRuntime(db, compiler)
    try:
        recipes = load_example_recipes()
        assert len(recipes) == 3

        for recipe in recipes:
            inputs = sample_inputs_for_recipe(recipe.recipe_id)
            result = runtime.execute(recipe, inputs, verify_emitted_python=True)
            assert result.python_equivalence_verified is True
            assert result.receipt.llm_tokens_at_runtime == 0
            assert result.receipt.memo_hits == []
            assert len(result.receipt.executed_steps) == len(recipe.steps)
            assert len(result.receipt.receipt_sha256) == 64

            py_source = compiler.compile_to_python(recipe)
            standalone_out = execute_emitted_python(py_source, inputs)
            assert canonical_json(standalone_out["terminal_outputs"]) == canonical_json(
                result.terminal_outputs
            )
    finally:
        db.close()


def test_warm_prefix_memoization_across_challenger_recipes(tmp_path: Path) -> None:
    db = NodeDatabase(tmp_path / "memo.db")
    compiler = DeterministicCompiler(db)
    runtime = DeterministicRuntime(db, compiler)
    try:
        base = next(r for r in load_example_recipes() if r.recipe_id == "ab-candidate-selection")
        inputs = sample_inputs_for_recipe("ab-candidate-selection")

        cold = runtime.execute(base, inputs, verify_emitted_python=True)
        assert len(cold.receipt.memo_hits) == 0
        assert len(cold.receipt.executed_steps) == 12

        # Identical second run hits 12/12 steps from SQLite subgraph_cache
        full_warm = runtime.execute(base, inputs, verify_emitted_python=False)
        assert len(full_warm.receipt.memo_hits) == 12
        assert full_warm.receipt.executed_steps == []
        assert full_warm.receipt.output_sha256 == cold.receipt.output_sha256

        # Challenger recipe mutating score_arm_b reuses 7/12 upstream & sibling steps
        challenger_raw = base.model_dump(mode="json")
        challenger_raw["recipe_id"] = "ab-candidate-selection-v2"
        for step in challenger_raw["steps"]:
            if step["step_id"] == "score_arm_b":
                step["params"]["weights_csv"] = "12.0,0.015"
        challenger = RecipeSpec.model_validate(challenger_raw)

        partial_warm = runtime.execute(challenger, inputs, verify_emitted_python=True)
        assert partial_warm.receipt.memo_hits == [
            "ingest_labeled",
            "dedupe_rows",
            "impute_features",
            "error_ratio",
            "holdout_partition",
            "score_arm_a",
            "eval_arm_a",
        ]
        assert partial_warm.receipt.executed_steps == [
            "score_arm_b",
            "eval_arm_b",
            "select_winner",
            "cohort_summary",
            "decision_report",
        ]
        assert partial_warm.receipt.llm_tokens_at_runtime == 0
    finally:
        db.close()


def test_asymmetric_join_inputs_do_not_collide_in_subgraph_cache() -> None:
    db = NodeDatabase(":memory:")
    runtime = DeterministicRuntime(db)
    try:
        join_recipe = RecipeSpec(
            recipe_id="asym-join",
            title="Asymmetric Join",
            goal="Ensure swapping left and right CSVs never collides in subgraph_cache.",
            steps=[
                RecipeStep(step_id="left_csv", node_id="ingest.csv_rows"),
                RecipeStep(step_id="right_csv", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="joined",
                    node_id="join.keyed_enrich",
                    params={"key_field": "id", "how": "inner"},
                ),
            ],
            edges=[
                RecipeEdge(
                    src_step="left_csv",
                    src_port="rows",
                    dst_step="joined",
                    dst_port="left_rows",
                ),
                RecipeEdge(
                    src_step="right_csv",
                    src_port="rows",
                    dst_step="joined",
                    dst_port="right_rows",
                ),
            ],
        )
        csv_a = "id,role\nu1,primary\nu2,primary\n"
        csv_b = "id,team\nu1,infra\n"

        run1 = runtime.execute(
            join_recipe,
            {"left_csv.raw_csv": csv_a, "right_csv.raw_csv": csv_b},
        )
        run2 = runtime.execute(
            join_recipe,
            {"left_csv.raw_csv": csv_b, "right_csv.raw_csv": csv_a},
        )
        # In run2, both root CSV parses hit cache (same CSV strings seen in run1),
        # while the asymmetric join MUST execute fresh because left_rows/right_rows swapped!
        assert set(run2.receipt.memo_hits) == {"left_csv", "right_csv"}
        assert run2.receipt.executed_steps == ["joined"]
        assert run1.step_outputs["joined"]["join_stats"]["left_count"] == 2
        assert run2.step_outputs["joined"]["join_stats"]["left_count"] == 1
    finally:
        db.close()


def test_ambiguous_or_wrong_type_runtime_entry_inputs_rejected() -> None:
    db = NodeDatabase(":memory:")
    runtime = DeterministicRuntime(db)
    try:
        triage = next(r for r in load_example_recipes() if r.recipe_id == "tabular-anomaly-triage")
        with pytest.raises(ExecutionInputError, match="Ambiguous entry port"):
            runtime.execute(triage, {"raw_csv": "event_id,service\n1,a\n"})

        digest = next(r for r in load_example_recipes() if r.recipe_id == "document-signal-digest")
        with pytest.raises(ExecutionInputError, match="expected PortType 'text'"):
            runtime.execute(digest, {"raw_text": 12345})
    finally:
        db.close()
