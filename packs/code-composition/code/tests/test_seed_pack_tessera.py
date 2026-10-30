"""Exported nouns and seeds against Tessera's real models and in-process HTTP lifecycle.

Needs a Tessera checkout's environment (see docs/seed-packs.md). With
CODE_COMPOSITION_REQUIRE_TESSERA=1, a missing or broken Tessera fails these tests instead of
skipping.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from code_composition.registry import NodeDatabase
from code_composition.seed_pack import build_seed_pack
from code_composition.seed_worker import execute_seed_task

NS = "conformance-seeds"
# Packs are not surfaces: the importing team writes with its own surface-bound key, and Tessera
# attributes the records exported with `surface:tessera` to that key's surface.
TEAM_SURFACE = "surface:example-team"
OUTPUT_STORE = "code-composition.outputs"


def _require(name: str) -> ModuleType:
    if os.environ.get("CODE_COMPOSITION_REQUIRE_TESSERA") == "1":
        return importlib.import_module(name)
    return pytest.importorskip(
        name, reason="Run with a Tessera checkout's environment for integration."
    )


def _research_seed_module(tessera: ModuleType) -> ModuleType:
    """Tessera's own NounRef lives in its research seed tool, loaded from the checkout."""
    path = Path(str(tessera.__file__)).resolve().parents[2] / "tools" / "research_seed.py"
    spec = importlib.util.spec_from_file_location("tessera_tools_research_seed", path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _export() -> dict[str, Any]:
    db = NodeDatabase(":memory:")
    try:
        return build_seed_pack(db, namespace=NS, queue=NS)
    finally:
        db.close()


def test_exported_records_and_tasks_validate_against_tessera_models() -> None:
    tessera = _require("tessera")
    ontology = _require("tessera.ontology")
    noun_ref_model = _research_seed_module(tessera).NounRef
    pack = _export()
    keys = {record["key"] for record in pack["records"]}
    for record in pack["records"]:
        tessera.RecordWrite.model_validate(record)
        value = record["value"]
        result = ontology.validate_category_payload(
            value["category_id"], value["dimensions"], value["relations"], record["tags"]
        )
        assert result.valid, (record["key"], result.errors)
        assert result.errors == () and result.warnings == (), (record["key"], result.warnings)
        assert len(result.validated_relations) == len(value["relations"])
        for edge in value["relations"]:
            assert ontology.RelationEdge.model_validate(edge).model_dump() == edge
            assert edge["target_id"] in keys
    for task in pack["tasks"]:
        spec = tessera.TaskSpec.model_validate(task)
        assert spec.kind in ontology.VERB_CATEGORIES and spec.brief["category_id"] == spec.kind
        brief = spec.brief
        for ref in [brief["recipe_ref"], brief["runtime_ref"], *brief["input_refs"]]:
            assert noun_ref_model.model_validate(ref).model_dump() == ref
            assert ref["key"] in keys


def test_real_tessera_models_claim_output_submit_and_cross_tenant_denial(
    tmp_path: Path, offline_guard: list[str]
) -> None:
    tessera = _require("tessera")
    access = _require("tessera.access")
    service = _require("tessera.service")
    receipts = _require("tessera.receipts")
    test_client = _require("fastapi.testclient").TestClient  # Tessera's own service dependency
    pack = _export()
    for record in pack["records"]:
        tessera.RecordWrite.model_validate(record)
    for task in pack["tasks"]:
        tessera.TaskSpec.model_validate(task)
    store = tessera.Store(tmp_path / "fabric.db")
    owner, grant = store.issue_key(
        "seed-worker",
        queues=[NS],
        scopes=["store", f"namespace:{NS}", TEAM_SURFACE],
    )
    outsider, _ = store.issue_key(
        "other-worker",
        queues=[NS],
        scopes=["store", "namespace:other-tenant"],
    )
    peer, _ = store.issue_key(
        "same-tenant-peer",
        queues=[NS],
        scopes=["store", f"namespace:{NS}", TEAM_SURFACE],
    )
    with store.scope_context(namespace=NS, key_id=grant.key_id):
        store.define_queue(tessera.QueueConfig(name=NS))
    headers = {"Authorization": "Bearer " + owner}
    denied_headers = {"Authorization": "Bearer " + outsider}
    peer_headers = {"Authorization": "Bearer " + peer}
    base = f"/ns/{NS}/v1"
    try:
        with test_client(
            service.create_app(store, access.ServiceSettings(reaper_seconds=86400))
        ) as client:
            write = client.post(
                base + "/stores/batch", json={"writes": pack["records"]}, headers=headers
            )
            assert write.status_code == 200, write.text
            assert all(record["version"] == 1 for record in write.json()["records"])
            first = pack["records"][0]
            url = base + f"/stores/{first['store']}/records/{first['key']}"
            assert client.get(url, headers=denied_headers).status_code == 403
            assert client.get(url, headers=peer_headers).status_code == 404
            assert (
                client.post(
                    base + "/tasks/claim",
                    json={"queue": NS, "worker": "other"},
                    headers=denied_headers,
                ).status_code
                == 403
            )
            # Create-only writes must not overwrite an existing version.
            assert (
                client.post(
                    base + "/stores/batch", json={"writes": [first]}, headers=headers
                ).status_code
                == 409
            )
            for task in pack["tasks"]:
                queued = client.post(base + "/tasks", json=task, headers=headers)
                assert queued.status_code == 201, queued.text
                assert (
                    client.post(base + "/tasks", json=task, headers=headers).json() == queued.json()
                )
            assert (
                client.post(
                    base + "/tasks/claim",
                    json={"queue": NS, "worker": "same-tenant-peer"},
                    headers=peer_headers,
                ).status_code
                == 204
            )
            for _ in pack["tasks"]:
                claimed = client.post(
                    base + "/tasks/claim",
                    json={"queue": NS, "worker": "seed-worker"},
                    headers=headers,
                )
                assert claimed.status_code == 200, claimed.text
                lease = claimed.json()
                fetched_records: dict[str, dict[str, Any]] = {}
                for pin in lease["brief"]["input_refs"]:
                    fetched = client.get(
                        base + f"/stores/{pin['store']}/records/{pin['key']}",
                        params={"version": pin["version"]},
                        headers=headers,
                    )
                    assert fetched.status_code == 200, fetched.text
                    record = fetched.json()
                    digest = hashlib.sha256(
                        receipts.canonical_json(record["value"]).encode()
                    ).hexdigest()
                    assert record["version"] == pin["version"]
                    assert digest == pin["value_sha256"]
                    assert record["producer_surface"] == TEAM_SURFACE
                    fetched_records[pin["key"]] = record
                # The worker path rechecks runtime pins, node bodies and the compiled plan.
                artifact = execute_seed_task(lease["brief"], fetched_records).model_dump(
                    mode="json"
                )
                artifact_key = (
                    "output."
                    + hashlib.sha256(receipts.canonical_json(artifact).encode()).hexdigest()
                )
                output_url = base + f"/stores/{OUTPUT_STORE}/records/" + artifact_key
                saved = client.post(
                    output_url,
                    json={"value": artifact, "expected_version": 0, "visibility_scope": "private"},
                    headers=headers,
                )
                assert saved.status_code == 200, saved.text
                assert client.get(output_url, headers=denied_headers).status_code == 403
                result = {
                    "artifact_refs": [
                        {
                            "store": OUTPUT_STORE,
                            "key": artifact_key,
                            "version": saved.json()["version"],
                        }
                    ],
                    "execution_receipt": artifact["receipt"],
                    "python_equivalence_verified": artifact["python_equivalence_verified"],
                }
                submit = {
                    "task_id": lease["task_id"],
                    "fencing_token": lease["fencing_token"],
                    "output": result,
                }
                submit_headers = {**headers, "Idempotency-Key": "result-" + lease["task_id"]}
                stale = {**submit, "fencing_token": lease["fencing_token"] + 1}
                assert (
                    client.post(
                        base + "/tasks/submit", json=stale, headers=submit_headers
                    ).status_code
                    == 409
                )
                accepted = client.post(base + "/tasks/submit", json=submit, headers=submit_headers)
                assert accepted.status_code == 200, accepted.text
                assert accepted.json()["receipt_hash"]
                replay = client.post(base + "/tasks/submit", json=submit, headers=submit_headers)
                assert (
                    replay.status_code == 200
                    and replay.json()["receipt_hash"] == accepted.json()["receipt_hash"]
                )
                assert (
                    client.get(base + "/tasks/" + lease["task_id"], headers=headers).json()["state"]
                    == "done"
                )
            assert (
                client.post(
                    base + "/tasks/claim",
                    json={"queue": NS, "worker": "seed-worker"},
                    headers=headers,
                ).status_code
                == 204
            )
    finally:
        store.close()
    assert offline_guard == []
