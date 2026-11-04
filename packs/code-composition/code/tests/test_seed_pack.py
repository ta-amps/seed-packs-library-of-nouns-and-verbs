"""Seed exports: checked nouns, typed links, pinned runtime, provenance and offline behavior."""

from __future__ import annotations

import collections
import copy
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

import code_composition
from code_composition import registry, seed_pack, seed_worker
from code_composition.cli import main
from code_composition.composer import RecipeComposer
from code_composition.errors import (
    NodeDatabaseAccessError,
    NodeVerificationError,
    RecipeCatalogError,
    SeedPackError,
    SeedVerificationError,
)
from code_composition.recipe_catalog import load_example_recipes
from code_composition.registry import NodeDatabase
from code_composition.schemas import (
    ALLOWED_SPDX_LICENSES,
    ParamSpec,
    PortSpec,
    PrewrittenNode,
    RecipeSpec,
)
from code_composition.seed_nodes import build_seed_nodes
from code_composition.seed_pack import (
    RUNTIME_MODULES,
    build_seed_pack,
    checkout_commit,
    noun_ref,
    resolve_source_commit,
    value_sha256,
)
from code_composition.seed_worker import execute_seed_task

ROOT = Path(__file__).resolve().parents[1]
NS = "conformance-seeds"
REQUIRED_DIMENSIONS = ("determinism", "evidence_grounding", "token_efficiency", "safety_compliance")
CUSTOM_SOURCE = """
def node_custom_scale_column(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    field = str(params["field"])
    factor = float(params.get("factor", 1.0))
    return {"rows": [{**r, field: round(float(r.get(field) or 0.0) * factor, 6)} for r in inputs["rows"]]}
"""


def export(**kwargs: Any) -> dict[str, Any]:
    db = NodeDatabase(":memory:")
    try:
        return build_seed_pack(db, namespace=NS, queue=NS, **kwargs)
    finally:
        db.close()


def readback(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Records as a worker reads them back from Tessera at their pinned versions."""
    return {
        record["key"]: {"store": record["store"], "version": 1, "value": record["value"]}
        for record in pack["records"]
    }


def cli_export(capsys: pytest.CaptureFixture[str], *extra: str) -> str:
    assert main(["seed-pack", "--namespace", NS, "--queue", NS, *extra]) == 0
    return capsys.readouterr().out


def custom_node(**overrides: Any) -> PrewrittenNode:
    fields: dict[str, Any] = {
        "node_id": "custom.scale_column",
        "category": "feature",
        "summary": "Multiply a numeric field by a constant factor.",
        "inputs": [PortSpec(name="rows", port_type="records", description="Input rows.")],
        "outputs": [PortSpec(name="rows", port_type="records", description="Scaled rows.")],
        "params": [
            ParamSpec(name="field", param_type="str", required=True),
            ParamSpec(name="factor", param_type="float", default=1.0),
        ],
        "function_name": "node_custom_scale_column",
        "source_code": CUSTOM_SOURCE,
        "test_cases": [
            {
                "name": "doubles_field",
                "inputs": {"rows": [{"x": 3.5}]},
                "params": {"field": "x", "factor": 2.0},
                "expected": {"rows": [{"x": 7.0}]},
            }
        ],
    }
    fields.update(overrides)
    return PrewrittenNode(**fields)


def snapshot(folder: Path) -> dict[str, tuple[str, int, int]]:
    return {
        path.name: (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
            path.stat().st_size,
        )
        for path in sorted(folder.iterdir())
    }


def repin(
    brief: dict[str, Any],
    store: dict[str, dict[str, Any]],
    key: str,
    mutate: Callable[[dict[str, Any]], object],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Change one noun and update every pin to it consistently, as a forged pack would."""
    brief, store = copy.deepcopy(brief), copy.deepcopy(store)
    mutate(store[key]["value"])
    for ref in [brief["recipe_ref"], brief["runtime_ref"], *brief["input_refs"]]:
        if ref["key"] == key:
            ref["value_sha256"] = value_sha256(store[key]["value"])
    return brief, store


def test_noun_hash_normalizes_numbers_and_rejects_lossy_values() -> None:
    assert value_sha256({"number": 1.0}) == value_sha256({"number": 1})
    assert value_sha256({"number": 10**16}) == value_sha256({"number": 1e16})
    with pytest.raises(ValueError, match="round-trip"):
        value_sha256({"number": 2**53 + 1})
    with pytest.raises(ValueError, match="JSON"):
        value_sha256({"number": float("nan")})


def test_offline_guard_blocks_sockets_dns_and_processes(offline_guard: list[str]) -> None:
    with pytest.raises(AssertionError, match="blocked"):
        socket.create_connection(("127.0.0.1", 9), timeout=1)
    with socket.socket() as raw, pytest.raises(AssertionError, match="blocked"):
        raw.connect(("127.0.0.1", 9))
    with pytest.raises(AssertionError, match="blocked"):
        socket.getaddrinfo("seed.invalid", 443)
    with pytest.raises(AssertionError, match="blocked"):
        httpx.get("http://127.0.0.1:9/")
    with pytest.raises(AssertionError, match="blocked"):
        subprocess.run(["true"], check=False)
    left, right = socket.socketpair()  # in-process event loops still work
    left.close()
    right.close()
    assert {
        "socket.create_connection",
        "socket.connect",
        "socket.getaddrinfo",
        "subprocess.Popen",
    } <= set(offline_guard)


def test_seed_cli_is_offline_private_and_worker_executable(
    offline_guard: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("Seed export and deterministic execution must not call a model or network.")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(RecipeComposer, "compose", forbidden)
    first = cli_export(capsys)
    assert cli_export(capsys) == first, "exports must be byte-identical across runs"
    pack = json.loads(first)
    assert pack["format"] == "code-composition.seed-pack.preview.v2"
    assert pack["status"] == "offline_candidate" and pack["importer"] is None
    records = {record["key"]: record for record in pack["records"]}
    assert len(records) == len(pack["records"]) == 23
    assert all(record["expected_version"] == 0 for record in records.values())
    assert all(record["visibility_scope"] == "private" for record in records.values())
    assert all("status:quarantined" in record["tags"] for record in records.values())
    # Packs are not surfaces: Tessera attributes these writes to the writing key's surface.
    assert all(record["producer_surface"] == "surface:tessera" for record in records.values())
    assert all(task["producer_surface"] == "surface:tessera" for task in pack["tasks"])
    assert len(pack["tasks"]) == 3
    store = readback(pack)
    for task in pack["tasks"]:
        brief = task["brief"]
        assert task["visibility_scope"] == "private"
        assert brief["execution"]["model_calls"] == 0
        assert brief["execution"]["server_fallback"] is False
        for ref in brief["input_refs"]:
            assert set(ref) == {"store", "key", "version", "value_sha256"}
            assert ref == noun_ref(ref["store"], ref["key"], records[ref["key"]]["value"])
        result = execute_seed_task(brief, store)
        assert result.python_equivalence_verified
        assert result.receipt.llm_tokens_at_runtime == 0
        recipe = records[brief["recipe_ref"]["key"]]["value"]
        assert result.plan.plan_sha256 == recipe["local_checks"]["compiled_plan_sha256"]
    assert pack == export()
    assert offline_guard == []


def test_nouns_use_registered_categories_typed_relations_and_provenance() -> None:
    pack = export()
    values = {record["key"]: record["value"] for record in pack["records"]}
    assert collections.Counter((v["category_id"], v["role"]) for v in values.values()) == {
        ("noun.code_node", "tool"): 19,
        ("noun.skill_pack", "recipe"): 3,
        ("noun.skill_pack", "project"): 1,
    }
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert pack["source"]["package_version"] == code_composition.__version__ == version["version"]
    commit = pack["source"]["commit"]
    for record in pack["records"]:
        value = record["value"]
        assert "requires_nouns" not in value and value["category_id"] != "noun.reflex_procedure"
        assert f"category:{value['category_id']}" in record["tags"]
        assert record["key"] == f"{value['role']}.{value_sha256(value)}"
        assert all(0 <= value["dimensions"][axis] <= 1 for axis in REQUIRED_DIMENSIONS)
        assert set(value["dimension_basis"]) == set(REQUIRED_DIMENSIONS)
        assert value["spdx_license"] in ALLOWED_SPDX_LICENSES
        provenance = value["provenance"]
        assert (
            provenance["repository"]
            == "https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs"
        )
        assert provenance["path"] == "packs/code-composition/code"
        assert provenance["commit"] == commit
        assert provenance["package_version"] == code_composition.__version__
        assert all((ROOT / path).is_file() for path in provenance["source_paths"])
        for edge in value["relations"]:
            assert set(edge) == {"relation", "target_id", "target_category", "note"}
            assert edge["relation"] == "requires_noun"
            assert values[edge["target_id"]]["category_id"] == edge["target_category"]
    (runtime_key,) = [key for key, value in values.items() if "tool" in value]
    runtime = values[runtime_key]["tool"]
    assert set(runtime["module_sha256"]) == {f"code_composition/{name}" for name in RUNTIME_MODULES}
    for path, digest in runtime["module_sha256"].items():
        data = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == digest
    recipes = [value for value in values.values() if value["role"] == "recipe"]
    for recipe in recipes:
        targets = {edge["target_id"] for edge in recipe["relations"]}
        steps = {step["node_id"] for step in recipe["recipe"]["steps"]}
        assert runtime_key in targets
        assert {values[key]["node"]["node_id"] for key in targets - {runtime_key}} == steps
        assert recipe["provenance"]["source_paths"][0].startswith("examples/recipes/")
    (index_key,) = [key for key, value in values.items() if value["role"] == "project"]
    assert {edge["target_id"] for edge in values[index_key]["relations"]} == set(values) - {
        index_key
    }
    nodes = {v["node"]["node_id"]: v for v in values.values() if "node" in v}
    holdout = nodes["validate.holdout_split"]["dimensions"]
    assert holdout["evidence_grounding"] == 0, "shape-only tests earn no exact-value credit"


def test_provenance_commit_matches_git_and_rejects_wrong_declarations() -> None:
    git = shutil.which("git")
    found = (
        None
        if git is None
        else subprocess.run(
            [git, "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        )
    )
    if found is None or found.returncode != 0:
        pytest.skip("Requires a Git checkout and the git command.")
    head = found.stdout.strip()
    assert checkout_commit() == head
    assert resolve_source_commit() == (head, "checkout_head")
    assert resolve_source_commit(head) == (head, "declared")
    with pytest.raises(SeedPackError, match="hexadecimal"):
        resolve_source_commit("HEAD")
    with pytest.raises(SeedPackError, match="differs"):
        resolve_source_commit("0" * 40)


def test_a_source_tree_elsewhere_must_declare_its_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A copy outside the repository path it names gets no commit from an unrelated checkout."""
    monkeypatch.setattr(seed_pack, "REPOSITORY_PATH", "elsewhere/code")
    assert checkout_commit() is None
    with pytest.raises(SeedPackError) as unknown:
        resolve_source_commit()
    assert unknown.value.code == "seed_provenance_unknown"


def test_worker_rechecks_pins_runtime_nodes_and_compiled_plan(
    offline_guard: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = export()
    brief, store = pack["tasks"][0]["brief"], readback(pack)
    recipe_key, runtime_key = brief["recipe_ref"]["key"], brief["runtime_ref"]["key"]

    changed = copy.deepcopy(store)
    changed[recipe_key]["value"]["title"] = "changed after pinning"
    with pytest.raises(SeedVerificationError, match="digest differs"):
        execute_seed_task(brief, changed)
    with pytest.raises(SeedVerificationError, match="was not read"):
        execute_seed_task(brief, {k: v for k, v in store.items() if k != runtime_key})

    def wrong_plan(value: dict[str, Any]) -> None:
        value["local_checks"]["compiled_plan_sha256"] = "f" * 64

    forged_brief, forged_store = repin(brief, store, recipe_key, wrong_plan)
    with pytest.raises(SeedVerificationError) as plan_error:
        execute_seed_task(forged_brief, forged_store)
    assert plan_error.value.code == "seed_plan_mismatch"

    real = seed_pack.runtime_module_digests()
    monkeypatch.setattr(
        seed_worker,
        "runtime_module_digests",
        lambda: {**real, "code_composition/runtime.py": "0" * 64},
    )
    with pytest.raises(
        SeedVerificationError, match=r"code_composition/runtime\.py"
    ) as runtime_error:
        execute_seed_task(brief, store)
    assert runtime_error.value.code == "seed_runtime_mismatch"
    monkeypatch.setattr(seed_worker, "runtime_module_digests", seed_pack.runtime_module_digests)

    local = NodeDatabase(":memory:")
    try:
        steps = store[recipe_key]["value"]["recipe"]["steps"]
        node = local.get_node(min(step["node_id"] for step in steps))
        local.register_node(
            node.model_copy(update={"summary": node.summary + " Edited locally."}),
            expected_revision=node.revision,
        )
        with pytest.raises(SeedVerificationError) as node_error:
            execute_seed_task(brief, store, db=local)
        assert node_error.value.code == "seed_node_mismatch"
    finally:
        local.close()
    assert execute_seed_task(brief, store).python_equivalence_verified
    assert offline_guard == []


def test_seed_pack_db_is_read_only_and_never_executes_stored_code(
    tmp_path: Path,
    offline_guard: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    typo = tmp_path / "typo" / "nodes.db"
    assert main(["seed-pack", "--namespace", NS, "--queue", NS, "--db", str(typo)]) == 1
    assert "nothing was created" in capsys.readouterr().err
    assert not (tmp_path / "typo").exists()

    path = tmp_path / "nodes.db"
    db = NodeDatabase(path)
    db.register_node(custom_node())
    db.close()
    before = snapshot(tmp_path)

    loaded: list[str] = []
    real_loader = registry.load_node_callable

    def record_load(node: PrewrittenNode) -> registry.NodeCallable:
        loaded.append(node.node_id)
        return real_loader(node)

    monkeypatch.setattr(registry, "load_node_callable", record_load)
    monkeypatch.setattr(seed_pack, "load_node_callable", record_load)
    from_db = json.loads(cli_export(capsys, "--db", str(path)))
    assert snapshot(tmp_path) == before, "export must not change or add database files"
    packaged_ids = {node.node_id for node in build_seed_nodes()}
    assert loaded and set(loaded) <= packaged_ids, "only packaged code may run during export"

    custom = next(
        r["value"]
        for r in from_db["records"]
        if r["value"].get("node", {}).get("node_id") == "custom.scale_column"
    )
    assert custom["local_checks"]["self_tests"]["executed"] is False
    assert custom["dimensions"]["verification_tier"] == "unverified"
    assert custom["dimensions"]["determinism"] == 0
    assert custom["provenance"]["content_origin"] == "local_node_database"
    assert custom["provenance"]["source_paths"] == []

    default = json.loads(cli_export(capsys))
    default_keys = {record["key"] for record in default["records"]}
    db_keys = {record["key"] for record in from_db["records"]}
    assert len(default_keys - db_keys) == 1, "only the pack index differs"
    assert len(db_keys - default_keys) == 2, "the custom tool plus its index"
    assert default["tasks"] == from_db["tasks"]
    assert offline_guard == []


def test_seed_export_refuses_unlicensed_tampered_in_use_and_foreign_databases(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    unlicensed = tmp_path / "unlicensed.db"
    db = NodeDatabase(unlicensed)
    db.register_node(custom_node(spdx_license="GPL-3.0-only"))
    db.close()
    assert main(["seed-pack", "--namespace", NS, "--queue", NS, "--db", str(unlicensed)]) == 1
    assert "spdx_license_allowed" in capsys.readouterr().err

    tampered = tmp_path / "tampered.db"
    db = NodeDatabase(tampered)
    db._conn.execute(
        "UPDATE nodes SET code_sha256=? WHERE node_id=?", ("f" * 64, "clean.dedupe_by_key")
    )
    db._conn.commit()
    db.close()
    assert main(["seed-pack", "--namespace", NS, "--queue", NS, "--db", str(tampered)]) == 1
    assert "disagrees" in capsys.readouterr().err

    in_use = NodeDatabase(tmp_path / "in-use.db")
    try:
        with pytest.raises(NodeDatabaseAccessError, match="uncheckpointed"):
            NodeDatabase.open_existing_read_only(tmp_path / "in-use.db")
    finally:
        in_use.close()

    foreign = tmp_path / "foreign.db"
    foreign.write_text("not a database", encoding="utf-8")
    with pytest.raises(NodeDatabaseAccessError, match="not a readable"):
        NodeDatabase.open_existing_read_only(foreign)
    with pytest.raises(NodeDatabaseAccessError, match="nothing was created"):
        NodeDatabase.open_existing_read_only(tmp_path / "missing.db")
    assert not (tmp_path / "missing.db").exists()


def test_seed_export_rejects_tampered_code_missing_inputs_and_invalid_scope() -> None:
    db = NodeDatabase(":memory:")
    try:
        with pytest.raises(ValueError, match="Invalid namespace"):
            build_seed_pack(db, namespace="Uppercase", queue=NS)
        unknown = RecipeSpec.model_validate(
            {**load_example_recipes()[0].model_dump(mode="json"), "recipe_id": "unlisted-recipe"}
        )
        with pytest.raises(SeedPackError, match="no made-up sample inputs"):
            build_seed_pack(db, namespace=NS, queue=NS, recipes=[unknown])
        db._conn.execute(
            "UPDATE nodes SET code_sha256=? WHERE node_id=?", ("f" * 64, "clean.dedupe_by_key")
        )
        db._conn.commit()
        with pytest.raises(NodeVerificationError, match="disagrees"):
            build_seed_pack(db, namespace=NS, queue=NS)
    finally:
        db.close()


def test_recipe_catalog_never_substitutes_a_recipe(tmp_path: Path) -> None:
    with pytest.raises(RecipeCatalogError):
        load_example_recipes(tmp_path / "missing")
    (tmp_path / "empty").mkdir()
    with pytest.raises(RecipeCatalogError):
        load_example_recipes(tmp_path / "empty")
    authored = sorted((ROOT / "examples" / "recipes").glob("*.json"))
    assert [recipe.recipe_id for recipe in load_example_recipes()] == [p.stem for p in authored]


def test_installed_layout_export_matches_checkout_and_fails_loudly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit = checkout_commit()
    if commit is None:
        pytest.skip("Requires a Git checkout for the reference export.")
    site = tmp_path / "site"
    shutil.copytree(
        ROOT / "code_composition",
        site / "code_composition",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = meta["tool"]["hatch"]["build"]["targets"]["wheel"]
    for source, target in wheel["force-include"].items():  # the wheel's package data mapping
        shutil.copytree(ROOT / source, site / target)
    bootstrap = (
        "import sys; sys.path.insert(0, sys.argv[1]); import code_composition as package; "
        "assert package.__file__.startswith(sys.argv[1]), package.__file__; "
        "from code_composition.cli import main; raise SystemExit(main(sys.argv[2:]))"
    )

    def run(*extra: str) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, "-I", "-c", bootstrap, str(site), "seed-pack"]
        return subprocess.run(
            [*command, "--namespace", NS, "--queue", NS, *extra],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
            timeout=120,
        )

    installed = run("--source-commit", commit)
    assert installed.returncode == 0, installed.stderr
    assert installed.stdout == cli_export(capsys), "installed and checkout exports must match"
    unknown = run()
    assert unknown.returncode == 1 and "seed_provenance_unknown" in unknown.stderr
    shutil.rmtree(site / "code_composition" / "recipes")
    missing = run("--source-commit", commit)
    assert missing.returncode == 1 and "recipe_catalog_unavailable" in missing.stderr
    assert missing.stdout == ""


def test_seed_modules_import_no_network_client_or_composer() -> None:
    probe = (
        "import sys, code_composition.seed_pack, code_composition.seed_worker; "
        "banned = ('httpx', 'fastapi', 'uvicorn', 'code_composition.composer', "
        "'code_composition.cli'); "
        "print(','.join(sorted(name for name in banned if name in sys.modules)))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True, timeout=60
    )
    assert loaded.stdout.strip() == ""
