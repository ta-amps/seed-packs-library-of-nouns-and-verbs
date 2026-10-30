"""Tests for RecipeComposer, contributor-tier refusal, Tessera reflex use and the CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from code_composition.cli import main as cli_main
from code_composition.composer import RecipeComposer, load_example_recipes, public_fabric_item
from code_composition.errors import ContributorTierRefusedError
from code_composition.registry import NodeDatabase


def test_contributor_tier_models_deterministically_refused() -> None:
    db = NodeDatabase(":memory:")
    try:
        with pytest.raises(ContributorTierRefusedError):
            RecipeComposer(db, model="llama-4-maverick-contributor")

        composer = RecipeComposer(db, model="llama-4-maverick")
        with pytest.raises(ContributorTierRefusedError):
            composer.compose("Build an anomaly digest", model="custom-agent-contributor")
    finally:
        db.close()


def test_live_llm_composer_mock_and_compiler_diagnostic_repair() -> None:
    db = NodeDatabase(":memory:")
    valid_recipe = load_example_recipes()[1].model_dump(mode="json")
    broken_recipe = json.loads(json.dumps(valid_recipe))
    broken_recipe["edges"][0]["src_port"] = "clean_txt"

    seen_requests: list[dict[str, Any]] = []
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        payload = json.loads(request.content.decode("utf-8"))
        seen_requests.append(payload)
        chosen = broken_recipe if call_count == 1 else valid_recipe
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(chosen)}}]},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        composer = RecipeComposer(
            db,
            base_url="https://llm.example.test",
            api_key="test-placeholder",
            model="llama-4-maverick",
            http_client=mock_client,
        )
        recipe, plan = composer.compose("Digest incident logs", max_repair_turns=1)
        assert call_count == 2
        assert recipe.recipe_id == "document-signal-digest"
        assert len(plan.steps) == 7

        # Verify first prompt sent compact signatures only, zero Python function definitions
        sys_msg = seen_requests[0]["messages"][0]["content"]
        assert "text.normalize_whitespace(" in sys_msg
        assert "def node_" not in sys_msg

        # Verify second turn fed exact deterministic compiler port diagnostic back to LLM
        repair_msg = seen_requests[1]["messages"][-1]["content"]
        assert "port_not_found" in repair_msg
        assert "clean_text" in repair_msg
    finally:
        mock_client.close()
        db.close()


def test_cli_commands_and_demo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = str(tmp_path / "cli.db")
    out_py = tmp_path / "wired_pipeline.py"

    assert cli_main(["init", "--db", db_path]) == 0
    assert cli_main(["verify-nodes", "--db", db_path]) == 0
    assert cli_main(["nodes", "--db", db_path, "--signatures"]) == 0
    assert (
        cli_main(
            [
                "compile",
                "document-signal-digest",
                "--db",
                db_path,
                "--emit-python",
                "--out",
                str(out_py),
            ]
        )
        == 0
    )
    assert out_py.is_file()
    assert "def run_pipeline" in out_py.read_text(encoding="utf-8")

    assert cli_main(["run", "document-signal-digest", "--db", db_path, "--verify-python"]) == 0
    assert (
        cli_main(
            [
                "compose",
                "Select A/B candidate risk model with holdout shrinkage",
                "--db",
                db_path,
                "--offline",
            ]
        )
        == 0
    )
    assert cli_main(["demo", "--db", str(tmp_path / "demo.db")]) == 0
    captured = capsys.readouterr().out
    assert "memo_hits=7/12" in captured


def test_responses_protocol_and_offline_threshold_extraction() -> None:
    db = NodeDatabase(":memory:")
    valid_recipe = load_example_recipes()[2].model_dump(mode="json")

    def responses_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        return httpx.Response(200, json={"output_text": json.dumps(valid_recipe)})

    mock_client = httpx.Client(transport=httpx.MockTransport(responses_handler))
    try:
        composer = RecipeComposer(
            db,
            base_url="https://llm.example.test",
            model="llama-4-maverick",
            protocol="responses",
            http_client=mock_client,
        )
        recipe, plan = composer.compose("Run telemetry triage")
        assert recipe.recipe_id == "tabular-anomaly-triage"
        assert len(plan.steps) == 13

        offline_recipe, _ = composer.compose(
            "Digest incident logs with threshold 0.75",
            force_offline=True,
        )
        gate_step = next(s for s in offline_recipe.steps if s.node_id == "filter.threshold_gate")
        assert gate_step.params["threshold"] == 0.75
    finally:
        mock_client.close()
        db.close()


def test_tessera_reflex_match_and_negative_knowledge_dead_ends() -> None:
    from code_composition.composer import OneShotComposer

    recipes = [r.model_dump(mode="json") for r in load_example_recipes()]
    reflex_recipe = recipes[1]  # document-signal-digest

    llm_calls = 0
    seen_llm_prompts: list[str] = []

    def reflex_short_circuit_handler(request: httpx.Request) -> httpx.Response:
        # These tools claim no surface; Tessera derives one from the caller's key.
        assert "x-surface-id" not in request.headers
        assert request.headers.get("authorization") == "Bearer tok-rx"
        if request.url.path == "/v1/reflexes/match":
            return httpx.Response(
                200,
                json={
                    "recommended_tier": "0_call_reflex",
                    "hits": [
                        {
                            "governance": {
                                "namespace": "main",
                                "producer_surface": "surface:tessera",
                                "visibility_scope": "public_commons",
                                "allowed_surfaces": [],
                                "target_cohorts": ["all"],
                                "tags": ["status:verified"],
                            },
                            "reflex_id": "rx-doc-signal-01",
                            "score": 0.96,
                            "l0_summary": "Verified incident log signal digest",
                            "recipe": reflex_recipe,
                        }
                    ],
                    "dead_ends": [
                        {
                            "governance": {
                                "namespace": "main",
                                "producer_surface": "surface:tessera",
                                "visibility_scope": "public_commons",
                                "allowed_surfaces": [],
                                "target_cohorts": ["all"],
                                "tags": ["status:verified"],
                            },
                            "key": "de-unbounded-regex",
                            "title": "Catastrophic backtracking on text.regex_extract",
                            "l0_summary": "Anchor line patterns with ^ and $ on extract_entries.",
                            "tags": ["node:text.regex_extract"],
                        }
                    ],
                },
            )
        return httpx.Response(404, json={"code": "not_found"})

    def llm_handler_fail_if_called(_request: httpx.Request) -> httpx.Response:
        nonlocal llm_calls
        llm_calls += 1
        return httpx.Response(500, json={"error": "should_not_be_called"})

    tessera_mock_1 = httpx.Client(transport=httpx.MockTransport(reflex_short_circuit_handler))
    llm_never_mock = httpx.Client(transport=httpx.MockTransport(llm_handler_fail_if_called))
    db = NodeDatabase(":memory:")
    try:
        composer = OneShotComposer(
            db,
            base_url="https://llm.example.test",
            model="llama-4-maverick",
            http_client=llm_never_mock,
            tessera_url="https://tessera.example.test",
            tessera_token="tok-rx",
            tessera_http_client=tessera_mock_1,
        )
        comp = composer.compose_detailed("Digest incident logs into a channel summary")
        assert comp.composer_mode == "tessera_0_call_reflex"
        assert comp.llm_tokens_used == 0
        assert llm_calls == 0
        assert comp.recipe.recipe_id == "document-signal-digest"
        assert any(w.code == "dead_end_avoided" for w in comp.plan.warnings)
        assert comp.dead_ends_avoided[0]["key"] == "de-unbounded-regex"
        assert comp.dead_ends_avoided[0]["step_id"] == "extract_entries"
    finally:
        tessera_mock_1.close()
        llm_never_mock.close()
        db.close()

    # Now verify negative.knowledge dead_ends flow into the LLM prompt constraints
    def tier2_tessera_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/reflexes/match":
            return httpx.Response(
                200,
                json={
                    "recommended_tier": "2_call_solve_verify",
                    "hits": [],
                    "dead_ends": [
                        {
                            "governance": {
                                "namespace": "main",
                                "producer_surface": "surface:tessera",
                                "visibility_scope": "public_commons",
                                "allowed_surfaces": [],
                                "target_cohorts": ["all"],
                                "tags": ["status:verified"],
                            },
                            "key": "de-mean-impute-skew",
                            "title": "Mean imputation distorts skewed telemetry",
                            "l0_summary": "Prefer median strategy on clean.impute_numeric.",
                            "tags": ["clean.impute_numeric"],
                        }
                    ],
                },
            )
        return httpx.Response(404, json={"code": "not_found"})

    def llm_ok_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        seen_llm_prompts.append(payload["messages"][0]["content"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(recipes[2])}}],
                "usage": {"total_tokens": 312},
            },
        )

    tessera_mock_2 = httpx.Client(transport=httpx.MockTransport(tier2_tessera_handler))
    llm_ok_mock = httpx.Client(transport=httpx.MockTransport(llm_ok_handler))
    db2 = NodeDatabase(":memory:")
    try:
        composer2 = OneShotComposer(
            db2,
            base_url="https://llm.example.test",
            model="llama-4-maverick",
            http_client=llm_ok_mock,
            tessera_url="https://tessera.example.test",
            tessera_token="tok-rx",
            tessera_http_client=tessera_mock_2,
        )
        comp2 = composer2.compose_detailed("Triage telemetry anomalies")
        assert comp2.composer_mode == "llm"
        assert comp2.llm_tokens_used == 312
        assert "de-mean-impute-skew" in seen_llm_prompts[0]
        assert any(w.code == "dead_end_avoided" for w in comp2.plan.warnings)
    finally:
        tessera_mock_2.close()
        llm_ok_mock.close()
        db2.close()


def test_reflex_records_must_be_verified_public_commons() -> None:
    """The composer has no surface of its own, so only verified public-commons records qualify."""
    public = {
        "namespace": "main",
        "producer_surface": "surface:tessera",
        "visibility_scope": "public_commons",
        "allowed_surfaces": [],
        "target_cohorts": ["all"],
        "tags": ["status:verified"],
    }
    assert public_fabric_item({"governance": public})
    assert public_fabric_item({"governance": {**public, "producer_surface": "surface:eranos"}})
    assert public_fabric_item(public), "governance fields may also sit on the item itself"
    refused: list[dict[str, Any]] = [
        {"visibility_scope": "allowlist_surfaces", "allowed_surfaces": ["surface:tessera"]},
        {"visibility_scope": "surface_only"},
        {"visibility_scope": "private"},
        {"producer_surface": "surface:other"},
        {"tags": ["status:verified", "status:quarantined"]},
        {"tags": []},
        {"target_cohorts": ["cohort:restricted"]},
        {"namespace": ""},
        {"allowed_surfaces": "surface:tessera"},
    ]
    for change in refused:
        assert not public_fabric_item({"governance": {**public, **change}}), change
    assert not public_fabric_item({"governance": {k: v for k, v in public.items() if k != "tags"}})
    assert not public_fabric_item("not a record")
