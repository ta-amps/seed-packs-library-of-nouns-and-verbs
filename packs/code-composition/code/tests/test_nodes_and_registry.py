"""Tests for the 18 prewritten verified nodes, SHA-256 integrity, and SQLite NodeDatabase."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from code_composition.errors import NodeNotFoundError, NodeVerificationError
from code_composition.registry import NodeDatabase, load_node_callable
from code_composition.schemas import PortSpec, PrewrittenNode
from code_composition.seed_nodes import HOLDOUT_SPLIT_DEFAULT_SALT, build_seed_nodes

EXPECTED_NODE_IDS = {
    "ingest.csv_rows",
    "clean.dedupe_by_key",
    "clean.impute_numeric",
    "clean.winsorize_outliers",
    "feature.ratio_column",
    "feature.rolling_zscore",
    "text.normalize_whitespace",
    "text.regex_extract",
    "filter.threshold_gate",
    "join.keyed_enrich",
    "model.linear_risk_score",
    "model.keyword_weighted_score",
    "validate.schema_contract",
    "validate.holdout_split",
    "eval.binary_metrics",
    "eval.shrinkage_select",
    "agg.group_summary",
    "format.markdown_report",
}


def test_seed_catalog_verifies_all_18_prewritten_nodes(tmp_path: Path) -> None:
    db_file = tmp_path / "nodes.db"
    db = NodeDatabase(db_file)
    try:
        assert set(db.list_node_ids()) == EXPECTED_NODE_IDS
        report = db.verify_all()
        assert len(report) == 18
        assert all(int(meta["tests_passed"]) >= 1 for meta in report.values())

        stats = db.catalog_token_stats()
        assert stats["node_count"] == 18
        assert stats["signature_tokens_est"] < stats["raw_code_tokens_est"] * 0.30

        sig_prompt = db.catalog_signature_prompt()
        assert "def node_" not in sig_prompt
        for node_id in EXPECTED_NODE_IDS:
            assert node_id in sig_prompt
    finally:
        db.close()


def test_tampered_code_sha256_and_failing_selftest_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="code_sha256 mismatch"):
        PrewrittenNode(
            node_id="custom.bad_hash",
            category="clean",
            summary="Mismatched hash.",
            inputs=[PortSpec(name="rows", port_type="records", description="in")],
            outputs=[PortSpec(name="rows", port_type="records", description="out")],
            function_name="fn_ok",
            source_code="def fn_ok(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:\n    return {'rows': []}\n",
            code_sha256="0" * 64,
            test_cases=[{"name": "t1", "inputs": {"rows": []}}],
        )

    db = NodeDatabase(tmp_path / "tamper.db")
    try:
        no_tests_node = PrewrittenNode(
            node_id="custom.no_tests",
            category="clean",
            summary="Missing test cases.",
            inputs=[PortSpec(name="rows", port_type="records", description="in")],
            outputs=[PortSpec(name="rows", port_type="records", description="out")],
            function_name="fn_untested",
            source_code="def fn_untested(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:\n    return {'rows': []}\n",
            test_cases=[],
        )
        with pytest.raises(NodeVerificationError, match="test_case"):
            db.register_node(no_tests_node)

        wrong_assertion_node = PrewrittenNode(
            node_id="custom.wrong_out",
            category="clean",
            summary="Fails expected output check.",
            inputs=[PortSpec(name="rows", port_type="records", description="in")],
            outputs=[PortSpec(name="rows", port_type="records", description="out")],
            function_name="fn_wrong",
            source_code="def fn_wrong(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:\n    return {'rows': [{'x': 1}]}\n",
            test_cases=[{"name": "bad", "inputs": {"rows": []}, "expected": {"rows": [{"x": 2}]}}],
        )
        with pytest.raises(NodeVerificationError, match="mismatch"):
            db.register_node(wrong_assertion_node)

        # Simulate out-of-band SQLite row digest tampering
        db._conn.execute(
            "UPDATE nodes SET code_sha256 = ? WHERE node_id = ?",
            ("f" * 64, "clean.dedupe_by_key"),
        )
        db._conn.commit()
        with pytest.raises(NodeVerificationError, match="disagrees"):
            db.get_node("clean.dedupe_by_key")
    finally:
        db.close()


def test_unknown_node_suggests_close_match() -> None:
    db = NodeDatabase(":memory:")
    try:
        with pytest.raises(NodeNotFoundError) as exc_info:
            db.get_node("clean.dedup_by_key")
        assert "clean.dedupe_by_key" in exc_info.value.detail
        assert exc_info.value.status_code == 404
    finally:
        db.close()


def test_fanout_immutability_across_nodes() -> None:
    nodes = {n.node_id: n for n in build_seed_nodes()}
    ratio_fn = load_node_callable(nodes["feature.ratio_column"])
    original = [{"a": 4, "b": 10}]
    snapshot = copy.deepcopy(original)
    out = ratio_fn({"rows": original}, {"numerator": "a", "denominator": "b", "output_field": "r"})
    assert original == snapshot
    assert out["rows"][0]["r"] == 0.4


def test_custom_registered_node_compiles_and_executes_end_to_end(tmp_path: Path) -> None:
    from code_composition.compiler import DeterministicCompiler
    from code_composition.runtime import DeterministicRuntime
    from code_composition.schemas import ParamSpec, RecipeEdge, RecipeSpec, RecipeStep

    db = NodeDatabase(tmp_path / "custom.db")
    try:
        db.register_node(
            PrewrittenNode(
                node_id="custom.scale_metric",
                category="feature",
                summary="Scale a numeric field by a constant factor.",
                inputs=[PortSpec(name="rows", port_type="records", description="Input rows.")],
                outputs=[PortSpec(name="rows", port_type="records", description="Scaled rows.")],
                params=[
                    ParamSpec(name="field", param_type="str", required=True),
                    ParamSpec(name="factor", param_type="float", default=2.0),
                ],
                function_name="node_custom_scale_metric",
                source_code=(
                    "def node_custom_scale_metric(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:\n"
                    "    f = str(params['field'])\n"
                    "    k = float(params.get('factor', 2.0))\n"
                    "    return {'rows': [{**r, f: round(float(r.get(f) or 0.0) * k, 6)} for r in inputs['rows']]}\n"
                ),
                test_cases=[
                    {
                        "name": "scales_x",
                        "inputs": {"rows": [{"x": 3}]},
                        "params": {"field": "x", "factor": 4.0},
                        "expected": {"rows": [{"x": 12.0}]},
                    }
                ],
            )
        )
        recipe = RecipeSpec(
            recipe_id="custom-pipeline",
            title="Custom Pipeline",
            goal="Parse CSV and scale x.",
            steps=[
                RecipeStep(step_id="parse", node_id="ingest.csv_rows"),
                RecipeStep(
                    step_id="scale",
                    node_id="custom.scale_metric",
                    params={"field": "x", "factor": 3.0},
                ),
            ],
            edges=[
                RecipeEdge(src_step="parse", src_port="rows", dst_step="scale", dst_port="rows")
            ],
        )
        compiler = DeterministicCompiler(db)
        runtime = DeterministicRuntime(db, compiler)
        res = runtime.execute(recipe, {"raw_csv": "id,x\na,5\nb,7\n"}, verify_emitted_python=True)
        assert res.python_equivalence_verified is True
        assert res.terminal_outputs["scale"]["rows"] == [
            {"id": "a", "x": 15.0},
            {"id": "b", "x": 21.0},
        ]
    finally:
        db.close()


def test_atomic_cas_revisions_and_layer1_governance_lens(tmp_path: Path) -> None:
    from code_composition.compiler import DAGCompiler
    from code_composition.errors import NodeGovernanceError, NodeRevisionConflictError
    from code_composition.schemas import RecipeSpec, RecipeStep

    repo_root = Path(__file__).resolve().parent.parent
    registry_src = (repo_root / "code_composition" / "registry.py").read_text(encoding="utf-8")
    assert "INSERT OR REPLACE" not in registry_src

    db = NodeDatabase(tmp_path / "cas_gov.db")
    try:
        for seeded in db.list_nodes():
            assert seeded.spdx_license == "MIT"
            assert "status:verified" in seeded.governance_tags
            assert seeded.revision == 1

        node_v1 = PrewrittenNode(
            node_id="custom.cas_probe",
            category="feature",
            spdx_license="Apache-2.0",
            governance_tags=["status:verified", "tier:core"],
            summary="Atomic CAS test node v1.",
            inputs=[PortSpec(name="rows", port_type="records", description="in")],
            outputs=[PortSpec(name="rows", port_type="records", description="out")],
            function_name="node_custom_cas_probe",
            source_code=(
                "def node_custom_cas_probe(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:\n"
                "    return {'rows': [{'v': 1} for _ in inputs['rows']]}\n"
            ),
            test_cases=[{"name": "t1", "inputs": {"rows": [{}]}, "expected": {"rows": [{"v": 1}]}}],
        )

        # Create-once CAS (expected_revision=0)
        created = db.register_node(node_v1, expected_revision=0)
        assert created.revision == 1
        assert created.spdx_license == "Apache-2.0"

        # Duplicate create-once must fail 409
        with pytest.raises(NodeRevisionConflictError) as dup_exc:
            db.register_node(node_v1, expected_revision=0)
        assert dup_exc.value.status_code == 409

        # Idempotent bootstrap (expected_revision=None) succeeds when code_sha256 matches
        idem = db.register_node(node_v1, expected_revision=None)
        assert idem.revision == 1

        node_v2 = PrewrittenNode(
            node_id="custom.cas_probe",
            category="feature",
            spdx_license="BSD-3-Clause",
            governance_tags=["status:verified"],
            summary="Atomic CAS test node v2.",
            inputs=[PortSpec(name="rows", port_type="records", description="in")],
            outputs=[PortSpec(name="rows", port_type="records", description="out")],
            function_name="node_custom_cas_probe",
            source_code=(
                "def node_custom_cas_probe(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:\n"
                "    return {'rows': [{'v': 2} for _ in inputs['rows']]}\n"
            ),
            test_cases=[{"name": "t2", "inputs": {"rows": [{}]}, "expected": {"rows": [{"v": 2}]}}],
        )

        # Unqualified overwrite with changed code_sha256 without expected_revision must fail 409
        with pytest.raises(NodeRevisionConflictError):
            db.register_node(node_v2, expected_revision=None)

        # Stale expected_revision=99 must fail 409 without mutating stored row
        with pytest.raises(NodeRevisionConflictError):
            db.register_node(node_v2, expected_revision=99)
        assert db.get_node("custom.cas_probe").revision == 1

        # Matching expected_revision=1 atomically advances revision -> 2
        updated = db.register_node(node_v2, expected_revision=1)
        assert updated.revision == 2
        assert db.get_node("custom.cas_probe").spdx_license == "BSD-3-Clause"

        # Layer-1 Governance Lens checks in DAGCompiler.compile_recipe
        compiler = DAGCompiler(db)
        probe_recipe = RecipeSpec(
            recipe_id="gov-probe",
            title="Governance Probe",
            goal="Verify Layer-1 Governance Lens.",
            steps=[RecipeStep(step_id="s1", node_id="custom.cas_probe")],
        )
        ok_plan = compiler.compile_recipe(probe_recipe)
        assert ok_plan.topological_order == ["s1"]

        # 1) Quarantined node refused at compile time
        db._conn.execute(
            "UPDATE nodes SET governance_tags_json = ? WHERE node_id = ?",
            ('["status:verified","status:quarantined"]', "custom.cas_probe"),
        )
        db._conn.commit()
        with pytest.raises(NodeGovernanceError, match="quarantined") as q_exc:
            compiler.compile_recipe(probe_recipe)
        assert q_exc.value.status_code == 422

        # 2) Node lacking status:verified refused at compile time
        db._conn.execute(
            "UPDATE nodes SET governance_tags_json = ? WHERE node_id = ?",
            ('["tier:experimental"]', "custom.cas_probe"),
        )
        db._conn.commit()
        with pytest.raises(NodeGovernanceError, match="status:verified"):
            compiler.compile_recipe(probe_recipe)

        # 3) Disallowed SPDX license refused (simulated via bypassed lookup)
        bad_spdx_node = PrewrittenNode.model_construct(
            node_id="custom.cas_probe",
            version="1.0.0",
            spdx_license="GPL-3.0-only",
            governance_tags=["status:verified"],
            revision=2,
            category="feature",
            summary="Disallowed SPDX.",
            inputs=[PortSpec(name="rows", port_type="records", description="in")],
            outputs=[PortSpec(name="rows", port_type="records", description="out")],
            params=[],
            function_name="node_custom_cas_probe",
            source_code=updated.source_code,
            code_sha256=updated.code_sha256,
            test_cases=[],
        )

        class _StubCatalog:
            def get_node(self, _node_id: str) -> PrewrittenNode:
                return bad_spdx_node

        with pytest.raises(NodeGovernanceError, match="spdx_license"):
            DAGCompiler(_StubCatalog()).compile_recipe(probe_recipe)  # type: ignore[arg-type]

        # 4) Tampered code_sha256 refused by Layer-1 Governance Lens
        bad_hash_node = PrewrittenNode.model_construct(
            **{**bad_spdx_node.__dict__, "spdx_license": "MIT", "code_sha256": "a" * 64}
        )

        class _StubTamperedCatalog:
            def get_node(self, _node_id: str) -> PrewrittenNode:
                return bad_hash_node

        with pytest.raises(NodeGovernanceError, match="code_sha256"):
            DAGCompiler(_StubTamperedCatalog()).compile_recipe(probe_recipe)  # type: ignore[arg-type]
    finally:
        db.close()


def test_holdout_split_default_salt_and_partitions_are_unchanged() -> None:
    """The default salt decides every default partition; renaming the package must not move it."""
    node = next(n for n in build_seed_nodes() if n.node_id == "validate.holdout_split")
    salt = next(p for p in node.params if p.name == "salt")
    assert salt.default == HOLDOUT_SPLIT_DEFAULT_SALT
    assert f'params.get("salt", "{HOLDOUT_SPLIT_DEFAULT_SALT}")' in node.source_code
    # The stored source is byte-identical to the first release, so pinned digests still hold.
    assert node.code_sha256 == "6f2e82304825ed01c41e0bf676f053cee928c1e8ea7085b99c6cd64362e5e7e2"
    split = load_node_callable(node)
    rows = [{"id": f"k{i}"} for i in range(20)]
    implicit = split({"rows": rows}, {"key_field": "id"})
    explicit = split({"rows": rows}, {"key_field": "id", "salt": HOLDOUT_SPLIT_DEFAULT_SALT})
    assert implicit == explicit
    # Measured with the first release's code: the same records land in the holdout partition.
    assert [r["id"] for r in implicit["holdout_rows"]] == ["k6", "k11", "k14", "k16", "k18", "k19"]
