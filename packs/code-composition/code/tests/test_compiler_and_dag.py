"""Tests for DeterministicCompiler: static port types, parameter bounds, cycles, and Merkle fingerprints."""

from __future__ import annotations

import pytest

from code_composition.compiler import DeterministicCompiler
from code_composition.errors import (
    CycleDetectedError,
    ParameterConstraintError,
    PortNotFoundError,
    PortTypeMismatchError,
    RecipeValidationError,
)
from code_composition.registry import NodeDatabase
from code_composition.schemas import RecipeEdge, RecipeSpec, RecipeStep


def test_static_port_type_mismatch_and_port_typo_suggestions() -> None:
    db = NodeDatabase(":memory:")
    compiler = DeterministicCompiler(db)
    try:
        typo_recipe = RecipeSpec(
            recipe_id="typo-check",
            title="Typo Check",
            goal="Detect mistyped output port.",
            steps=[
                RecipeStep(step_id="s1", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="s2",
                    node_id="clean.dedupe_by_key",
                    params={"key_field": "id"},
                ),
            ],
            edges=[RecipeEdge(src_step="s1", src_port="rowz", dst_step="s2", dst_port="rows")],
        )
        with pytest.raises(PortNotFoundError) as typo_exc:
            compiler.compile(typo_recipe)
        assert "Did you mean port 'rows'?" in typo_exc.value.detail

        mismatch_recipe = RecipeSpec(
            recipe_id="type-mismatch",
            title="Mismatch Check",
            goal="Reject wiring metrics output into records input.",
            steps=[
                RecipeStep(step_id="s1", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="s2",
                    node_id="clean.dedupe_by_key",
                    params={"key_field": "id"},
                ),
            ],
            edges=[
                RecipeEdge(
                    src_step="s1",
                    src_port="ingest_stats",
                    dst_step="s2",
                    dst_port="rows",
                )
            ],
        )
        with pytest.raises(PortTypeMismatchError) as mm_exc:
            compiler.compile(mismatch_recipe)
        assert "'metrics'" in mm_exc.value.detail
        assert "'records'" in mm_exc.value.detail
    finally:
        db.close()


def test_parameter_constraints_types_bounds_and_choices() -> None:
    db = NodeDatabase(":memory:")
    compiler = DeterministicCompiler(db)
    try:
        # bool must not pass int validation even though isinstance(True, int) in Python
        bool_as_int = RecipeSpec(
            recipe_id="bool-int",
            title="Bool as Int",
            goal="Reject bool on int window parameter.",
            steps=[
                RecipeStep(
                    step_id="z1",
                    node_id="feature.rolling_zscore",
                    params={"field": "x", "window": True},
                )
            ],
        )
        with pytest.raises(ParameterConstraintError, match="expected int"):
            compiler.compile(bool_as_int)

        # out-of-range float quantile
        out_of_bounds = RecipeSpec(
            recipe_id="bounds-fail",
            title="Bounds Fail",
            goal="Reject lower_q above 0.49.",
            steps=[
                RecipeStep(
                    step_id="w1",
                    node_id="clean.winsorize_outliers",
                    params={"field": "x", "lower_q": 0.8},
                )
            ],
        )
        with pytest.raises(ParameterConstraintError, match="exceeds max_value"):
            compiler.compile(out_of_bounds)

        # disallowed str choice
        bad_choice = RecipeSpec(
            recipe_id="choice-fail",
            title="Choice Fail",
            goal="Reject invalid dedupe keep mode.",
            steps=[
                RecipeStep(
                    step_id="d1",
                    node_id="clean.dedupe_by_key",
                    params={"key_field": "id", "keep": "middle"},
                )
            ],
        )
        with pytest.raises(ParameterConstraintError, match="allowed choices"):
            compiler.compile(bad_choice)

        # unknown parameter suggests close match
        unknown_param = RecipeSpec(
            recipe_id="param-typo",
            title="Param Typo",
            goal="Suggest key_field.",
            steps=[
                RecipeStep(
                    step_id="d1",
                    node_id="clean.dedupe_by_key",
                    params={"key_feild": "id"},
                )
            ],
        )
        with pytest.raises(ParameterConstraintError, match="key_field"):
            compiler.compile(unknown_param)
    finally:
        db.close()


def test_cycle_detection_reports_exact_cycle_path() -> None:
    db = NodeDatabase(":memory:")
    compiler = DeterministicCompiler(db)
    try:
        cyclic = RecipeSpec(
            recipe_id="cyclic-dag",
            title="Cyclic Graph",
            goal="Reject 3-step cycle with exact path.",
            steps=[
                RecipeStep(step_id="root", node_id="ingest.csv_rows"),
                RecipeStep(step_id="a", node_id="clean.dedupe_by_key", params={"key_field": "id"}),
                RecipeStep(step_id="b", node_id="clean.impute_numeric", params={"fields": ["x"]}),
                RecipeStep(step_id="c", node_id="clean.winsorize_outliers", params={"field": "x"}),
            ],
            edges=[
                RecipeEdge(src_step="root", src_port="rows", dst_step="a", dst_port="rows"),
                RecipeEdge(src_step="a", src_port="rows", dst_step="b", dst_port="rows"),
                RecipeEdge(src_step="b", src_port="rows", dst_step="c", dst_port="rows"),
                RecipeEdge(src_step="c", src_port="rows", dst_step="a", dst_port="rows"),
            ],
        )
        with pytest.raises(CycleDetectedError) as cyc_exc:
            compiler.compile(cyclic)
        assert cyc_exc.value.cycle_path == ["a", "b", "c", "a"]
        assert "a -> b -> c -> a" in cyc_exc.value.detail
    finally:
        db.close()


def test_entry_inputs_vs_missing_internal_wiring_and_warnings() -> None:
    db = NodeDatabase(":memory:")
    compiler = DeterministicCompiler(db)
    try:
        # Missing right_rows on internal join.keyed_enrich step
        unwired_join = RecipeSpec(
            recipe_id="unwired-join",
            title="Unwired Join",
            goal="Fail when internal required input port is forgotten.",
            steps=[
                RecipeStep(step_id="ingest", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="enrich",
                    node_id="join.keyed_enrich",
                    params={"key_field": "id"},
                ),
            ],
            edges=[
                RecipeEdge(
                    src_step="ingest",
                    src_port="rows",
                    dst_step="enrich",
                    dst_port="left_rows",
                )
            ],
        )
        with pytest.raises(RecipeValidationError) as uw_exc:
            compiler.compile(unwired_join)
        assert uw_exc.value.code == "missing_required_input"
        assert "enrich.right_rows" in uw_exc.value.detail

        # Isolated step + dangling transform emit static warnings
        warn_recipe = RecipeSpec(
            recipe_id="warn-check",
            title="Warn Check",
            goal="Surface isolated and dangling transform steps.",
            steps=[
                RecipeStep(step_id="ingest", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="dangling_clean",
                    node_id="clean.dedupe_by_key",
                    params={"key_field": "id"},
                ),
                RecipeStep(
                    step_id="orphan",
                    node_id="filter.threshold_gate",
                    params={"field": "x"},
                ),
            ],
            edges=[
                RecipeEdge(
                    src_step="ingest",
                    src_port="rows",
                    dst_step="dangling_clean",
                    dst_port="rows",
                )
            ],
        )
        plan = compiler.compile(warn_recipe)
        warning_codes = {(w.step_id, w.code) for w in plan.warnings}
        assert ("orphan", "isolated_step") in warning_codes
        assert ("dangling_clean", "dangling_transform") in warning_codes

        # Duplicate incoming edges on the same input port in an acyclic graph must fail
        dup_in_recipe = RecipeSpec(
            recipe_id="dup-in",
            title="Duplicate Input",
            goal="Reject two upstream edges feeding the same dst_port.",
            steps=[
                RecipeStep(step_id="r1", node_id="ingest.csv_rows"),
                RecipeStep(step_id="r2", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="d1",
                    node_id="clean.dedupe_by_key",
                    params={"key_field": "id"},
                ),
            ],
            edges=[
                RecipeEdge(src_step="r1", src_port="rows", dst_step="d1", dst_port="rows"),
                RecipeEdge(src_step="r2", src_port="rows", dst_step="d1", dst_port="rows"),
            ],
        )
        with pytest.raises(RecipeValidationError) as dup_exc:
            compiler.compile(dup_in_recipe)
        assert dup_exc.value.code == "duplicate_input_wiring"
    finally:
        db.close()


def test_merkle_subgraph_fingerprint_alpha_invariance_and_sensitivity() -> None:
    db = NodeDatabase(":memory:")
    compiler = DeterministicCompiler(db)
    try:
        r1 = RecipeSpec(
            recipe_id="r1",
            title="R1",
            goal="First naming.",
            steps=[
                RecipeStep(step_id="load_a", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="dedupe_a",
                    node_id="clean.dedupe_by_key",
                    params={"key_field": "id", "keep": "first"},
                ),
            ],
            edges=[
                RecipeEdge(src_step="load_a", src_port="rows", dst_step="dedupe_a", dst_port="rows")
            ],
        )
        r2 = RecipeSpec(
            recipe_id="r2",
            title="R2",
            goal="Alpha-renamed step IDs.",
            steps=[
                RecipeStep(step_id="csv_source", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="unique_filter",
                    node_id="clean.dedupe_by_key",
                    params={"key_field": "id", "keep": "first"},
                ),
            ],
            edges=[
                RecipeEdge(
                    src_step="csv_source",
                    src_port="rows",
                    dst_step="unique_filter",
                    dst_port="rows",
                )
            ],
        )
        r3 = RecipeSpec(
            recipe_id="r3",
            title="R3",
            goal="Modified upstream keep param.",
            steps=[
                RecipeStep(step_id="csv_source", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="unique_filter",
                    node_id="clean.dedupe_by_key",
                    params={"key_field": "id", "keep": "last"},
                ),
            ],
            edges=[
                RecipeEdge(
                    src_step="csv_source",
                    src_port="rows",
                    dst_step="unique_filter",
                    dst_port="rows",
                )
            ],
        )
        p1 = compiler.compile(r1)
        p2 = compiler.compile(r2)
        p3 = compiler.compile(r3)

        assert p1.steps[0].subgraph_fingerprint == p2.steps[0].subgraph_fingerprint
        assert p1.steps[1].subgraph_fingerprint == p2.steps[1].subgraph_fingerprint
        assert p2.steps[0].subgraph_fingerprint == p3.steps[0].subgraph_fingerprint
        assert p2.steps[1].subgraph_fingerprint != p3.steps[1].subgraph_fingerprint
    finally:
        db.close()
