"""Security regressions for immutable compilation: plan digests, node revisions and emitted titles."""

from __future__ import annotations

import pytest

from code_composition.compiler import DeterministicCompiler
from code_composition.errors import CodeCompositionError
from code_composition.registry import NodeDatabase
from code_composition.runtime import DeterministicRuntime, execute_emitted_python
from code_composition.schemas import PrewrittenNode, RecipeSpec, RecipeStep


def constant_node(value: int, tags: list[str] | None = None) -> PrewrittenNode:
    return PrewrittenNode(
        node_id="test.constant",
        category="test",
        summary="Made-up constant",
        inputs=[],
        outputs=[{"name": "data", "port_type": "json", "description": "Made-up"}],
        function_name="constant",
        source_code=f'def constant(inputs, params):\n    return {{"data": {{"value": {value}}}}}\n',
        test_cases=[{"name": "constant", "expected": {"data": {"value": value}}}],
        governance_tags=tags or ["status:verified"],
    )


def test_plan_hash_current_revision_and_revocation_checked_before_cache() -> None:
    db = NodeDatabase(":memory:", auto_seed=False)
    db.register_node(constant_node(1))
    compiler = DeterministicCompiler(db)
    runtime = DeterministicRuntime(db, compiler)
    recipe = RecipeSpec(
        recipe_id="stable",
        title="Stable plan",
        goal="Constant",
        steps=[RecipeStep(step_id="one", node_id="test.constant")],
    )
    plan = compiler.compile(recipe)
    runtime.execute(plan, {})
    changed = plan.model_copy(deep=True)
    changed.steps[0].resolved_params["unreviewed"] = True
    with pytest.raises(CodeCompositionError, match="digest mismatch"):
        runtime.execute(changed, {})
    db.register_node(constant_node(2), expected_revision=1)
    with pytest.raises(CodeCompositionError, match="revision changed"):
        runtime.execute(plan, {})
    with pytest.raises(CodeCompositionError, match="revision changed"):
        compiler.emit_python_from_plan(plan)
    fresh = compiler.compile(recipe)
    runtime.execute(fresh, {})
    db.register_node(constant_node(2, ["status:quarantined"]), expected_revision=2)
    with pytest.raises(CodeCompositionError):
        runtime.execute(fresh, {})
    db.close()


def test_arbitrary_title_is_data_in_emitted_python() -> None:
    db = NodeDatabase(":memory:", auto_seed=False)
    db.register_node(constant_node(1))
    recipe = RecipeSpec(
        recipe_id="quoted",
        title='Title """\nraise RuntimeError("title executed")\n""" \\ end',
        goal="Data",
        steps=[RecipeStep(step_id="one", node_id="test.constant")],
    )
    source = DeterministicCompiler(db).compile_to_python(recipe)
    assert execute_emitted_python(source, {})["terminal_outputs"] == {"one": {"data": {"value": 1}}}
    db.close()
