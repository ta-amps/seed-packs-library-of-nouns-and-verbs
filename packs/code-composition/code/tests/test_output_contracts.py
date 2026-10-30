"""Produced-value contracts: declared output ports are checked everywhere a value is produced."""

from __future__ import annotations

import pytest

from code_composition.compiler import DeterministicCompiler
from code_composition.errors import CodeCompositionError
from code_composition.registry import NodeDatabase
from code_composition.runtime import DeterministicRuntime, execute_emitted_python
from code_composition.schemas import (
    PrewrittenNode,
    RecipeSpec,
    RecipeStep,
    canonical_json,
    sha256_hex,
)


def variable_node() -> PrewrittenNode:
    return PrewrittenNode(
        node_id="test.typed_output",
        category="test",
        summary="Synthetic output validation",
        inputs=[{"name": "data", "port_type": "json", "description": "Switch fixture"}],
        outputs=[{"name": "values", "port_type": "series", "description": "Numbers"}],
        function_name="typed_output",
        source_code='def typed_output(inputs, params):\n    return {"values": "SYNTHETIC wrong" if inputs["data"].get("invalid") else [1, 2]}\n',
        test_cases=[{"inputs": {"data": {}}, "expected": {"values": [1, 2]}}],
    )


def test_output_types_checked_in_self_tests_runtime_cache_and_emitted_code() -> None:
    db = NodeDatabase(":memory:", auto_seed=False)
    try:
        node = variable_node()
        bad_test = node.model_copy(
            update={
                "test_cases": [
                    {"inputs": {"data": {"invalid": True}}, "expected_ports": ["values"]}
                ]
            }
        )
        with pytest.raises(CodeCompositionError, match="expected PortType 'series'"):
            db.register_node(bad_test)
        db.register_node(node)
        compiler = DeterministicCompiler(db)
        runtime = DeterministicRuntime(db, compiler)
        recipe = RecipeSpec(
            recipe_id="typed",
            title="Typed",
            goal="SYNTHETIC",
            steps=[RecipeStep(step_id="one", node_id=node.node_id)],
        )
        plan = compiler.compile(recipe)
        source = compiler.emit_python_from_plan(plan)
        with pytest.raises(CodeCompositionError, match="expected PortType 'series'"):
            runtime.execute(plan, {"data": {"invalid": True}})
        with pytest.raises(ValueError, match=r"Output one\.values: expected series"):
            execute_emitted_python(source, {"data": {"invalid": True}})
        with pytest.raises(ValueError, match=r"Entry input one\.data: expected json"):
            execute_emitted_python(source, {"data": "wrong"})
        with pytest.raises(CodeCompositionError, match=r"Cache write\.values"):
            db.put_cached_subgraph("synthetic", "input", node.node_id, {"values": "wrong"})
        runtime.execute(plan, {"data": {}})
        # A valid checksum alone cannot turn malformed cached output into typed data.
        bad_cache = canonical_json({"values": "wrong"})
        db._conn.execute(
            "UPDATE subgraph_cache SET outputs_json=?, output_sha256=?",
            (bad_cache, sha256_hex(bad_cache)),
        )
        db._conn.commit()
        with pytest.raises(CodeCompositionError, match=r"Cache read\.values"):
            runtime.execute(plan, {"data": {}})
        # Trusted SDK output can exceed public bounds, even if its outer type is valid.
        broad_cache = canonical_json({"values": list(range(600))})
        db._conn.execute(
            "UPDATE subgraph_cache SET outputs_json=?, output_sha256=?",
            (broad_cache, sha256_hex(broad_cache)),
        )
        db._conn.commit()
        with pytest.raises(CodeCompositionError, match="limited to 512"):
            runtime.execute(plan, {"data": {}}, public_preview=True)
    finally:
        db.close()
