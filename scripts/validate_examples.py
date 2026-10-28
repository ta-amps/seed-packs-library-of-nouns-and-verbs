#!/usr/bin/env python3
"""Offline checks for this repository's narrow synthetic example profile.

This is not a JSON Schema engine, Tessera SDK, importer or execution validator.
It never calls a service, invokes a model or runs content from an example.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = {
    "producer_surface", "visibility_scope", "allowed_surfaces", "target_cohorts", "tags"
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def strict_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for name, value in pairs:
        require(name not in result, "duplicate JSON property")
        result[name] = value
    return result


def reject_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(), object_pairs_hook=strict_pairs,
                       parse_constant=reject_constant)
    require(isinstance(value, dict), "example root must be an object")
    return value


def integer(value: object, minimum: int = 0, maximum: int = 2**53 - 1) -> bool:
    return type(value) is int and minimum <= value <= maximum


def governance(value: dict, category: str) -> None:
    require(value.get("producer_surface") == "surface:tessera", "example producer mismatch")
    require(value.get("visibility_scope") == "private", "candidate examples must stay private")
    require(value.get("allowed_surfaces") == [], "examples do not grant cross-surface access")
    require(value.get("target_cohorts") == ["all"], "unexpected example cohort")
    tags = value.get("tags")
    require(isinstance(tags, list) and all(isinstance(tag, str) and ":" in tag for tag in tags), "invalid facet tags")
    require(len(tags) == len(set(tags)), "duplicate tags")
    categories = [tag.split(":", 1)[1] for tag in tags if tag.startswith(("category:", "cat:"))]
    require(categories == [category], "primary category and tag must agree")
    require("status:verified" not in tags, "example cannot self-verify")


def noun(value: dict) -> None:
    require(set(value) == {"expected_version", "value", *GOVERNANCE}, "unexpected noun body fields")
    require(integer(value.get("expected_version")) and value["expected_version"] == 0, "example CAS must be create-only integer")
    record = value.get("value")
    require(isinstance(record, dict), "noun value must be an object, not encoded JSON")
    require(record.get("category_id") == "noun.reflex_procedure", "unexpected example noun category")
    governance(value, record["category_id"])
    require(record.get("synthetic") is True and record.get("license") == "MIT", "synthetic/license marker required")
    require(isinstance(record.get("input_schema"), dict) and isinstance(record.get("output_schema"), dict), "schema objects required")
    require(isinstance(record.get("steps"), list) and bool(record["steps"]), "procedure steps required")
    checks = record.get("checks", [])
    require(any("expected" in check for check in checks) and any("expected_error" in check for check in checks), "positive and negative example checks required")
    measurements = record.get("measurements", {})
    require(measurements.get("latency_ms") is None and bool(measurements.get("reason")), "unknown example measurements need a reason")


def verb(value: dict) -> None:
    required = {"queue", "kind", "effect_class", "priority", "idempotency_key", "depends_on", "brief", *GOVERNANCE}
    require(set(value) == required, "unexpected TaskSpec example fields")
    require(value["queue"] == "conformance-pack-demo", "use only the illustrative contribution queue")
    require(value["kind"] == "verb.solve_draft" and value["effect_class"] == "write-internal", "unexpected kind or effect")
    require(integer(value["priority"], 0, 100), "priority must be an integer")
    require(isinstance(value["idempotency_key"], str) and bool(value["idempotency_key"]), "stable enqueue identity required")
    require(value["depends_on"] == [], "fixture must not pretend existing task dependencies")
    brief = value["brief"]
    require(isinstance(brief, dict) and brief.get("synthetic") is True, "synthetic brief required")
    require(brief.get("category_id") == value["kind"], "brief primary category mismatch")
    governance(value, brief["category_id"])
    require("status:quarantined" in value["tags"], "candidate seed must be quarantined")
    refs = brief.get("input_refs", [])
    require(len(refs) == 1 and refs[0] == {"store": "pack.candidates", "key": "SYNTHETIC-addition-v1", "version": 1}, "pin the example input record")
    require(brief.get("review", {}).get("publication_permitted") is False, "draft cannot publish")
    require(brief.get("review", {}).get("self_approval_permitted") is False, "draft cannot self-approve")
    require(brief.get("bounds") == {"max_attempts": 2, "max_elapsed_seconds": 300, "max_model_calls": 0}, "example bounds changed")


def submission(value: dict) -> None:
    require(set(value) == {"task_id", "fencing_token", "ok", "error", "output", "execution_report"}, "unexpected HTTP submit fields")
    require(isinstance(value["task_id"], str) and integer(value["fencing_token"], 1), "typed task and fence required")
    require(type(value["ok"]) is bool, "ok must be a JSON boolean")
    require(isinstance(value["output"], dict) and value["output"].get("synthetic") is True, "synthetic output object required")
    report = value["execution_report"]
    require(isinstance(report, dict) and type(report.get("version")) is int and report["version"] == 1, "report must be a version-1 object")
    require(set(report) == {"version", "harness", "summaries", "artifact_refs", "usage"}, "unexpected report example fields")
    require(isinstance(report["harness"], dict) and isinstance(report["summaries"], dict), "report metadata objects required")
    for ref in report["artifact_refs"]:
        require(set(ref) == {"store", "key", "version"} and integer(ref["version"], 1), "invalid pinned artifact reference")
    usage = report["usage"]
    require(isinstance(usage, dict) and bool(usage.get("source")), "usage source required")
    for name in ("input_tokens", "output_tokens"):
        require(usage.get(name) is None and bool(usage.get("reason")), "template usage must remain unknown with reason")


def mcp(value: dict) -> None:
    require(set(value) == {"jsonrpc", "id", "method", "params"}, "invalid JSON-RPC envelope")
    require(value["jsonrpc"] == "2.0" and isinstance(value["id"], str), "invalid JSON-RPC identity")
    require(isinstance(value["params"], dict), "MCP params must be an object")
    method, params = value["method"], value["params"]
    if method == "initialize":
        require(params.get("protocolVersion") == "2025-06-18" and params.get("capabilities") == {}, "unexpected initialize example")
    elif method == "tools/list":
        require(params == {}, "tools/list example has no arguments")
    else:
        require(method == "tools/call" and set(params) == {"name", "arguments"}, "unsupported MCP example operation")
        args = params["arguments"]
        require(isinstance(args, dict), "MCP arguments must be an object")
        if params["name"] == "put_record":
            require(args.get("store_name") == "demo.artifacts" and args.get("key") == "SYNTHETIC-addition-v1", "use only the demo example target")
            noun({key: item for key, item in args.items() if key not in {"store_name", "key"}})
        elif params["name"] == "submit":
            require(isinstance(args.get("idempotency_key"), str) and bool(args["idempotency_key"]), "MCP submit requires idempotency argument")
            submission({key: item for key, item in args.items() if key != "idempotency_key"})
        else:
            raise ValueError("unsupported MCP example tool")


def manifest(value: dict, examples: Path) -> None:
    require(value.get("format") == "ta-amps.pack-contribution.proposal.v1" and value.get("status") == "proposal_only", "manifest must stay proposed")
    require(value.get("synthetic") is True and value.get("license") == "MIT", "synthetic manifest required")
    require(value.get("importer") is None and bool(value.get("importer_reason")), "no importer may be claimed")
    require(value.get("override_policy") == {"automatic_merge": False, "on_conflict": "stop_and_clarify"}, "no implicit merges")
    paths = set()
    for entry in value.get("files", []):
        require(set(entry) == {"path", "sha256"} and isinstance(entry["path"], str), "invalid manifest reference")
        path = (examples / entry["path"]).resolve()
        require(path.is_relative_to(examples.resolve()) and path.is_file(), "manifest path must be a local example")
        require(entry["path"] not in paths, "duplicate manifest path")
        paths.add(entry["path"])
        require(entry["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest(), "manifest byte digest mismatch")
    require(paths == {"http/noun-put.json", "http/verb-enqueue.json"}, "manifest must name the two reviewed fixture files")


def meta_contract(value: dict) -> None:
    require(value.get("format") == "ta-amps.meta-pack.reference.v1" and value.get("status") == "reference_only", "meta-pack must stay reference-only")
    require(value.get("active") is False and value.get("importer") is None and bool(value.get("importer_reason")), "no active meta-pack or importer")
    require(value.get("controls_mutable_by_candidate") is False, "candidate cannot change its judging controls")
    require(set(value.get("protected_controls", [])) == {"evaluation_contract", "holdout_definition", "permission_policy", "budget_policy"}, "protected control missing")
    require(value.get("review", {}).get("candidate_may_approve_itself") is False and value.get("promotion", {}).get("automatic") is False, "no automatic self-approval")
    measurements = value.get("evaluation", {}).get("measurements", {})
    require(bool(measurements.get("reason")) and all(measurements.get(name) is None for name in ("paired_outcome_delta", "cost_usd", "latency_ms", "confidence_calibration")), "unmeasured outcomes must stay unknown")
    require(value.get("bounds") == {"max_candidates": 1, "max_attempts": 2, "max_elapsed_seconds": 600, "max_model_calls": 0, "cost_ceiling_usd": 0}, "reference bounds changed")
    require(value.get("negative_knowledge", {}).get("automatic_public_summary") is False, "failure evidence cannot automatically become public")


def validate_repository(root: Path = ROOT) -> dict:
    examples = root / "examples"
    parsed = {path.relative_to(examples).as_posix(): load(path) for path in examples.rglob("*.json")}
    require(set(parsed) == {
        "http/session.json", "http/claim.json", "http/demo-put.json", "http/noun-put.json",
        "http/verb-enqueue.json", "http/submit.json", "mcp/initialize.json", "mcp/tools-list.json",
        "mcp/put-record.json", "mcp/submit.json", "pack-manifest.proposed.json",
        "meta/self-improvement.reference.json",
    }, "new example needs an explicit validation profile")
    require(parsed["http/session.json"] == {"agent_label": "synthetic-pack-worker"}, "invalid session example")
    require(parsed["http/claim.json"] == {"queue": "demo.ping", "worker": "synthetic-pack-worker"}, "invalid claim example")
    noun(parsed["http/demo-put.json"])
    noun(parsed["http/noun-put.json"])
    require("status:quarantined" in parsed["http/noun-put.json"]["tags"], "keyed candidate quarantine required")
    verb(parsed["http/verb-enqueue.json"])
    submission(parsed["http/submit.json"])
    for name, value in parsed.items():
        if name.startswith("mcp/"):
            mcp(value)
    manifest(parsed["pack-manifest.proposed.json"], examples)
    meta_contract(parsed["meta/self-improvement.reference.json"])
    text_count = 0
    for path in root.rglob("*"):
        if not path.is_file() or any(part in {".git", "__pycache__", ".ruff_cache"} for part in path.relative_to(root).parts):
            continue
        text = path.read_text()
        require(chr(8212) not in text, "forbidden typography in " + path.relative_to(root).as_posix())
        text_count += 1
        if path.suffix == ".md":
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                if target.startswith(("https://", "http://", "#")):
                    continue
                local = (path.parent / target.split("#", 1)[0]).resolve()
                require(local.is_relative_to(root.resolve()) and local.exists(), "broken local documentation link")
    return {"json_examples": len(parsed), "text_files": text_count, "offline_only": True, "live_evaluation": None,
            "reason": "Validates this example profile, not deployed behavior or artifact correctness."}


if __name__ == "__main__":
    print(json.dumps(validate_repository(), sort_keys=True))
