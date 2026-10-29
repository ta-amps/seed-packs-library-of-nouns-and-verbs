#!/usr/bin/env python3
"""Offline checks for the seed-pack library; Python standard library only.

This checks the generated packs against packs/tessera-contract.json, a snapshot
derived from Tessera's own code by scripts/validate_against_tessera.py. It also
runs the packs' deterministic worked examples. It never calls a service, invokes
a model, writes a record, enqueues a task or runs content from a pack.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_packs as bp  # noqa: E402

GOVERNANCE_FIELDS = ("producer_surface", "visibility_scope", "allowed_surfaces", "target_cohorts", "tags")
RECORD_FIELDS = {"store", "key", "expected_version", "value", *GOVERNANCE_FIELDS}
TASK_FIELDS = {"queue", "kind", "effect_class", "priority", "idempotency_key", "depends_on", "brief", *GOVERNANCE_FIELDS}
BRIEF_FIELDS = {
    "category_id", "contract", "pack", "pack_version", "template_id", "title", "plain_summary", "outcome",
    "claimant", "inputs", "slot_specs", "param_specs", "input_schema", "output_contract", "output_schema",
    "permitted_outcomes", "outcome_meanings", "outcome_requirements", "acceptance_checks", "guidance",
    "required_capabilities", "bounds", "execution", "review", "instantiation", "execution_report",
    "dimensions", "dimension_basis", "relations",
}
BRIEF_OPTIONAL = {"follows_templates", "notes"}
SCHEMA_KEYWORDS = {
    "type", "enum", "const", "properties", "required", "additionalProperties", "items", "minItems",
    "maxItems", "minLength", "maxLength", "pattern", "minimum", "maximum", "description",
}
MAX_PAYLOAD_BYTES = 32768
MAX_README_LINES = 90


def require(ok: bool, message: str) -> None:
    if not ok:
        raise bp.PackError(message)


def load_contract(root: Path = ROOT) -> dict[str, Any]:
    contract = bp.load_json(root / "packs" / "tessera-contract.json")
    require(contract.get("format") == "ta-amps.tessera-contract-snapshot.v1", "unexpected contract snapshot format")
    return contract


# ---------------------------------------------------------------------------
# JSON Schema subset (documented keywords only)
# ---------------------------------------------------------------------------

TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: type(v) is int,
    "number": lambda v: type(v) in (int, float) and math.isfinite(v),
    "boolean": lambda v: type(v) is bool,
    "null": lambda v: v is None,
}


def check_schema(schema: Any, where: str) -> None:
    """A schema may use only the keywords this validator actually enforces."""
    require(isinstance(schema, dict), f"{where}: schema must be an object")
    unknown = set(schema) - SCHEMA_KEYWORDS
    require(not unknown, f"{where}: unsupported schema keywords {sorted(unknown)}")
    kinds = schema.get("type")
    if kinds is not None:
        for kind in kinds if isinstance(kinds, list) else [kinds]:
            require(kind in TYPES, f"{where}: unknown type {kind!r}")
    if "pattern" in schema:
        re.compile(schema["pattern"])
    for name, sub in schema.get("properties", {}).items():
        check_schema(sub, f"{where}.{name}")
    if "items" in schema:
        check_schema(schema["items"], f"{where}[]")
    if "additionalProperties" in schema:
        require(type(schema["additionalProperties"]) is bool, f"{where}: additionalProperties must be a boolean")
    for name in schema.get("required", []):
        require(name in schema.get("properties", {}), f"{where}: required {name!r} has no property schema")


def schema_errors(schema: dict[str, Any], value: Any, where: str = "$") -> list[str]:
    errors: list[str] = []
    kinds = schema.get("type")
    if kinds is not None:
        options = kinds if isinstance(kinds, list) else [kinds]
        if not any(TYPES[kind](value) for kind in options):
            return [f"{where}: expected {options}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: not one of {schema['enum']}")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{where}: must equal {schema['const']!r}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", math.inf):
            errors.append(f"{where}: length out of bounds")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: does not match pattern")
    if type(value) in (int, float) and not isinstance(value, bool):
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            errors.append(f"{where}: out of range")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", math.inf):
            errors.append(f"{where}: item count out of bounds")
        if "items" in schema:
            for i, item in enumerate(value):
                errors += schema_errors(schema["items"], item, f"{where}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{where}: missing {name}")
        if schema.get("additionalProperties") is False:
            for name in sorted(set(value) - set(props)):
                errors.append(f"{where}: unexpected {name}")
        for name, sub in props.items():
            if name in value:
                errors += schema_errors(sub, value[name], f"{where}.{name}")
    return errors


# ---------------------------------------------------------------------------
# Tessera contract emulation
# ---------------------------------------------------------------------------


def category_from_tag(tag: str) -> str | None:
    clean = tag.strip().lower()
    if clean.startswith(("category:", "cat:", "noun.", "verb.")):
        for prefix in ("category:", "cat:"):
            if clean.startswith(prefix):
                clean = clean[len(prefix):].strip()
                break
        return clean or None
    return None


def payload_categories(value: dict[str, Any], contract: dict[str, Any]) -> set[str]:
    """Category declarations Tessera's store derives from a value (extract_payload_tags)."""
    found: set[str] = set()
    for name in contract["payload_tag_fields"]:
        item = value.get(name)
        if isinstance(item, str) and item.strip():
            cat = category_from_tag(item)
            if name in ("category", "category_id"):
                cat = category_from_tag("category:" + item)
            if cat:
                found.add(cat)
    tags = value.get("tags")
    items = [str(tag) for tag in tags] if isinstance(tags, list) else []
    if isinstance(tags, dict):
        items = [f"{k}:{v}" for k, v in tags.items()]
    meta = value.get("metadata_tags")
    if isinstance(meta, dict):
        items += [f"{k}:{v}" for k, v in meta.items()]
    found |= {cat for tag in items if (cat := category_from_tag(tag))}
    return found


def check_dimensions(category: str, dimensions: Any, contract: dict[str, Any], where: str) -> None:
    spec = contract["categories"][category]["dimensions"]
    require(dimensions == bp.FLOOR_DIMENSIONS, f"{where}: dimensions must stay at the unmeasured floor")
    for name, dim in spec.items():
        if dim["required"]:
            require(name in dimensions, f"{where}: missing required dimension {name}")
        if name not in dimensions:
            continue
        raw = dimensions[name]
        if dim["dtype"] == "categorical":
            require(raw in dim["allowed_values"], f"{where}: {name} not an allowed value")
        else:
            require(type(raw) in (int, float) and dim["min_val"] <= raw <= dim["max_val"], f"{where}: {name} out of bounds")
    unknown = set(dimensions) - set(spec) - set(contract["categories"][category]["domain_dimensions"])
    require(not unknown, f"{where}: unrecognized dimensions {sorted(unknown)}")


def check_relations(category: str, relations: Any, contract: dict[str, Any], targets: dict[str, str], where: str) -> None:
    require(isinstance(relations, list), f"{where}: relations must be a list")
    allowed = set(contract["categories"][category]["allowed_relations"])
    seen = set()
    for i, rel in enumerate(relations):
        here = f"{where}.relations[{i}]"
        require(set(rel) == {"relation", "target_id", "target_category", "note"}, f"{here}: typed relation fields")
        require(rel["relation"] in contract["relation_types"], f"{here}: unknown relation type")
        require(rel["relation"] in allowed, f"{here}: {rel['relation']} not permitted for {category}")
        require(rel["target_id"] in targets, f"{here}: target is not a noun in this library")
        require(rel["target_category"] == targets[rel["target_id"]], f"{here}: target category mismatch")
        require((rel["relation"], rel["target_id"]) not in seen, f"{here}: duplicate relation")
        seen.add((rel["relation"], rel["target_id"]))


def check_governance(doc: dict[str, Any], category: str, where: str) -> None:
    require(doc["producer_surface"] == bp.PRODUCER, f"{where}: producer surface")
    require(doc["visibility_scope"] == "private", f"{where}: pack payloads stay private")
    require(doc["allowed_surfaces"] == [], f"{where}: no cross-surface grants")
    require(doc["target_cohorts"] == ["all"], f"{where}: unexpected cohort")
    tags = doc["tags"]
    require(isinstance(tags, list) and all(isinstance(t, str) and ":" in t and t == t.strip() for t in tags), f"{where}: facet tags")
    require(len(tags) == len(set(tags)), f"{where}: duplicate tags")
    cats = [category_from_tag(t) for t in tags if category_from_tag(t)]
    require(cats == [category], f"{where}: exactly one category tag must match {category}")
    require("status:quarantined" in tags and "status:verified" not in tags, f"{where}: quarantined, never self-verified")


def size_ok(doc: Any, where: str) -> None:
    require(len(bp.canonical_json(doc).encode()) <= MAX_PAYLOAD_BYTES, f"{where}: payload exceeds {MAX_PAYLOAD_BYTES} bytes")


def check_record(record: dict[str, Any], pack_id: str, contract: dict[str, Any], targets: dict[str, str]) -> None:
    where = f"{pack_id}/{record.get('key')}"
    require(set(record) == RECORD_FIELDS, f"{where}: RecordWrite fields")
    require(re.fullmatch(contract["patterns"]["name"], record["store"]) is not None, f"{where}: store name")
    require(record["store"] == f"seedpack.{pack_id}", f"{where}: pack store")
    require(re.fullmatch(contract["patterns"]["record_key"], record["key"]) is not None, f"{where}: record key")
    require(record["key"].startswith(pack_id + "."), f"{where}: key prefix")
    require(type(record["expected_version"]) is int and record["expected_version"] == 0, f"{where}: create-only")
    value = record["value"]
    require(isinstance(value, dict), f"{where}: value must be an object")
    category = value.get("category_id")
    require(category in contract["categories"] and contract["categories"][category]["kind"] == "noun", f"{where}: registered noun category")
    require(not contract["categories"][category]["human_sensitive"], f"{where}: human-sensitive noun categories are out of scope")
    check_governance(record, category, where)
    require(payload_categories(value, contract) <= {category}, f"{where}: value fields declare a conflicting category")
    for name, expected in (("pack", pack_id), ("status", "proposal"), ("admission", "not_admitted"), ("license", "MIT")):
        require(value.get(name) == expected, f"{where}: {name} must be {expected!r}")
    require(value.get("content_kind") in {"authored_guidance", "synthetic_example"}, f"{where}: content kind")
    synthetic = value["content_kind"] == "synthetic_example"
    require(("synthetic:true" in record["tags"]) == synthetic, f"{where}: synthetic tag")
    require(value.get("provenance") == bp.PROVENANCE, f"{where}: provenance")
    require(value.get("dimension_basis") == bp.DIMENSION_BASIS, f"{where}: unmeasured basis")
    check_dimensions(category, value.get("dimensions"), contract, where)
    check_relations(category, value.get("relations"), contract, targets, where)
    require(isinstance(value.get("title"), str) and value["title"].strip(), f"{where}: title")
    for name in ("trials", "successes"):
        require(value.get(name) is None, f"{where}: {name} stays null until uses are recorded with receipts")
    if value["role"] == "template":
        require(isinstance(value.get("describes"), str) and value["describes"].strip(), f"{where}: template says what it describes")
        check_schema(value.get("schema"), f"{where}.schema")
        if "example" in value:
            problems = schema_errors(value["schema"], value["example"])
            require(not problems, f"{where}: example does not match its schema: {problems[:3]}")
    size_ok(record, where)


def check_report(report: dict[str, Any], contract: dict[str, Any], where: str) -> None:
    spec = contract["report"]
    require(isinstance(report, dict) and set(report) <= set(spec["root_fields"]), f"{where}: report root fields")
    require(report.get("version") == 1, f"{where}: report version")
    require(set(report.get("summaries", {})) <= set(spec["summary_fields"]), f"{where}: summary fields")
    require(set(report.get("contract", {})) <= set(spec["contract_fields"]), f"{where}: contract fields")
    for block in report.get("blocks", []):
        require(set(block) == {"kind", "text"} and block["kind"] in spec["block_kinds"], f"{where}: block kind")
    usage = report.get("usage", {})
    require(set(usage) <= set(spec["token_fields"]) | {"source", "reason"}, f"{where}: usage fields")
    for name in set(spec["token_fields"]) & set(usage):
        require(usage[name] is None and bool(usage.get("reason")), f"{where}: template usage stays unknown with a reason")
    for ref in report.get("artifact_refs", []):
        require(set(ref) == {"store", "key", "version"}, f"{where}: artifact ref fields")
    require(len(bp.canonical_json(report).encode()) <= contract["limits"]["max_report_bytes"], f"{where}: report too large")


def check_task(task: dict[str, Any], pack_id: str, contract: dict[str, Any], pins: dict[tuple[str, str], str],
               targets: dict[str, str], templates: set[str]) -> None:
    brief = task.get("brief", {})
    where = f"{pack_id}/{brief.get('template_id')}"
    require(set(task) == TASK_FIELDS, f"{where}: TaskSpec fields")
    kind = task["kind"]
    require(kind in contract["categories"] and contract["categories"][kind]["kind"] == "verb", f"{where}: registered verb category")
    require(re.fullmatch(contract["patterns"]["name"], task["queue"]) is not None and task["queue"] == bp.QUEUE_PLACEHOLDER, f"{where}: placeholder queue")
    require(re.fullmatch(contract["patterns"]["name"], kind) is not None, f"{where}: kind pattern")
    require(task["effect_class"] == "write-internal", f"{where}: effect class")
    require(type(task["priority"]) is int and 0 <= task["priority"] <= 100, f"{where}: priority")
    require(task["depends_on"] == [], f"{where}: templates cannot invent task ids")
    check_governance(task, kind, where)
    for tag in (f"pack:{pack_id}", f"claimant:{brief.get('claimant')}", f"template:{str(brief.get('template_id', '')).split('.', 1)[-1]}"):
        require(tag in task["tags"], f"{where}: missing tag {tag}")
    require(isinstance(brief, dict) and set(brief) - BRIEF_OPTIONAL == BRIEF_FIELDS, f"{where}: brief fields")
    require(brief["category_id"] == kind and brief["contract"] == bp.VERB_CONTRACT and brief["pack"] == pack_id, f"{where}: brief identity")
    slug = str(brief.get("template_id", "")).split(".", 1)[-1]
    expected_key = bp.template_idempotency_key(pack_id, slug, task["queue"], kind, brief)
    require(task["idempotency_key"] == expected_key and len(expected_key) <= contract["limits"]["idempotency_key_max_length"], f"{where}: idempotency key")
    human_sensitive = contract["categories"][kind]["human_sensitive"]
    require(not human_sensitive or brief["claimant"] == "human", f"{where}: human-sensitive verbs need a human claimant")
    # Inputs: exact pins, unfilled slots
    inputs = brief["inputs"]
    require(set(inputs) == {"pinned", "slots", "params"}, f"{where}: inputs")
    for pin in inputs["pinned"] + [item["template"] for item in brief["output_contract"]["produces"]]:
        require(set(pin) == set(contract["fields"]["NounRef"]), f"{where}: NounRef fields")
        require(pin["version"] == 1 and pins.get((pin["store"], pin["key"])) == pin["value_sha256"], f"{where}: pin {pin['key']} digest")
    require(inputs["slots"] == {n: [] if s["many"] else None for n, s in brief["slot_specs"].items()}, f"{where}: template slots stay unfilled")
    for name, spec in brief["slot_specs"].items():
        require(spec["category"] in contract["categories"] and contract["categories"][spec["category"]]["kind"] == "noun", f"{where}: slot {name} category")
    require(set(inputs["params"]) == set(brief["param_specs"]), f"{where}: params")
    for name, spec in brief["param_specs"].items():
        check_schema(spec["schema"], f"{where}.param_specs.{name}")
        if "default" in spec:
            require(not schema_errors(spec["schema"], spec["default"]), f"{where}: default for {name}")
    check_schema(brief["input_schema"], f"{where}.input_schema")
    check_schema(brief["output_schema"], f"{where}.output_schema")
    # Outcomes
    outcomes = brief["permitted_outcomes"]
    require(len(outcomes) == 4 and outcomes[1:] == list(bp.STANDARD_OUTCOMES), f"{where}: explicit no_change, unknown and blocked outcomes")
    require(brief["output_schema"]["properties"]["outcome"]["enum"] == outcomes, f"{where}: outcome enum")
    require(set(brief["outcome_requirements"]) == set(outcomes) and set(brief["outcome_meanings"]) == set(outcomes), f"{where}: every outcome is defined")
    for fields in brief["outcome_requirements"].values():
        for field in fields:
            require(field in brief["output_schema"]["properties"], f"{where}: outcome requirement {field} is not an output field")
    checks = brief["acceptance_checks"]
    require(checks and len({c["id"] for c in checks}) == len(checks), f"{where}: acceptance checks")
    require(any(c["method"] == "deterministic" for c in checks), f"{where}: at least one deterministic check")
    require(brief["guidance"]["required"], f"{where}: required guidance")
    # Authority
    execution = brief["execution"]
    require(execution["server_fallback"] is False and execution["maximum_automatically_enqueued_children"] == 0, f"{where}: no server fallback or automatic children")
    require(execution["external_effects"] == "none" and execution["inference_allowance"] == bp.INFERENCE_ALLOWANCE, f"{where}: no external effects or spending")
    require(execution["model_use"] in bp.MODEL_USE, f"{where}: model use")
    if brief["claimant"] == "human":
        require(execution["model_use"] == "none" and execution["reasoning"] == "human", f"{where}: human verbs use no model")
    review = brief["review"]
    require(review["required"] in bp.REVIEW_RULES, f"{where}: review rule")
    require(not review["self_approval_permitted"] and not review["publication_permitted"] and not review["admission_permitted"], f"{where}: no self-approval, publication or admission")
    for name, bound in brief["bounds"].items():
        require(type(bound) is int and bound >= 0, f"{where}: bound {name}")
    oc = brief["output_contract"]
    require(oc["visibility_scope"] == "private" and oc["allowed_surfaces"] == [], f"{where}: outputs stay private")
    if oc["write_mode"] == "create_only":
        require(oc["expected_version"] == 0, f"{where}: create-only writes use expected version 0")
    else:
        require(oc["write_mode"] == "compare_and_set" and set(oc["expected_version"]) == {"from_slot"}, f"{where}: write mode")
        slot = oc["expected_version"]["from_slot"]
        require(slot in brief["slot_specs"] and not brief["slot_specs"][slot]["many"], f"{where}: compare-and-set names one pinned slot")
    require(brief["instantiation"]["status"] == "template", f"{where}: template status")
    for item in brief.get("follows_templates", []):
        require(item in templates, f"{where}: follows unknown template {item}")
    # Report and fingerprint
    report = brief["execution_report"]
    require(report["optional"] is True, f"{where}: report is optional")
    check_report(report["template"], contract, where)
    require(report["template"]["contract"] == {"input_schema": brief["input_schema"], "output_schema": brief["output_schema"]}, f"{where}: report contract copies the typed schemas")
    require(report["shape_sha256"] == bp.shape_sha256(brief["input_schema"], brief["output_schema"]), f"{where}: shape fingerprint")
    # Category payload
    check_dimensions(kind, brief["dimensions"], contract, where)
    require(brief["dimension_basis"] == bp.DIMENSION_BASIS, f"{where}: unmeasured basis")
    check_relations(kind, brief["relations"], contract, targets, where)
    pinned_targets = {f"{p['store']}/{p['key']}" for p in inputs["pinned"]}
    produced_targets = {f"{p['template']['store']}/{p['template']['key']}" for p in oc["produces"]}
    require({r["target_id"] for r in brief["relations"] if r["relation"] == "requires_noun"} == pinned_targets, f"{where}: requires_noun mirrors pins")
    require({r["target_id"] for r in brief["relations"] if r["relation"] == "produces_noun"} == produced_targets, f"{where}: produces_noun mirrors outputs")
    size_ok(task, where)


# ---------------------------------------------------------------------------
# Deterministic worked examples
# ---------------------------------------------------------------------------


def get_path(doc: Any, path: str) -> Any:
    if path == "$":
        return doc
    current = doc
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def strings_under(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in strings_under(item)]
    if isinstance(value, list):
        return [s for item in value for s in strings_under(item)]
    return []


def filled(value: Any) -> bool:
    return value not in (None, "", [], {})


def rule_passes(rule: dict[str, Any], doc: Any) -> bool:
    kind = rule["rule"]
    if kind == "when":
        condition = rule["if"]
        actual = get_path(doc, condition["path"])
        applies = actual in condition["in"] if "in" in condition else actual == condition["equals"]
        return rule_passes(rule["then"], doc) if applies else True
    value = get_path(doc, rule["path"])
    if kind == "present":
        return filled(value)
    if kind == "enum":
        return value in rule["values"]
    if kind == "min_items":
        return isinstance(value, list) and len(value) >= rule["min"]
    if kind == "each_has":
        items = value if isinstance(value, list) else []
        return len(items) >= rule.get("min", 0) and all(
            isinstance(item, dict) and all(filled(item.get(f)) for f in rule["fields"]) for item in items
        )
    if kind == "pattern_absent":
        return not any(re.search(rule["pattern"], s) for s in strings_under(value))
    if kind == "pattern_present":
        return any(re.search(rule["pattern"], s) for s in strings_under(value))
    raise bp.PackError(f"unknown rule type {kind!r}")


def failing_checks(checks: list[dict[str, Any]], doc: Any) -> list[str]:
    return [check["id"] for check in checks if not rule_passes(check["rule"], doc)]


def set_path(doc: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = doc
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def mutate(doc: Any, operator: dict[str, Any]) -> Any:
    out = json.loads(json.dumps(doc))
    op, path = operator["op"], operator["path"]
    parent_path, _, leaf = path.rpartition(".")
    parent = get_path(out, parent_path) if parent_path else out
    if op == "delete":
        parent.pop(leaf, None)
    elif op == "clear":
        current = get_path(out, path)
        set_path(out, path, [] if isinstance(current, list) else ({} if isinstance(current, dict) else ""))
    elif op == "set":
        set_path(out, path, operator["value"])
    elif op == "append_text":
        set_path(out, path, str(get_path(out, path) or "") + operator["text"])
    elif op == "delete_item_field":
        for item in get_path(out, path) or []:
            item.pop(operator["field"], None)
    else:
        raise bp.PackError(f"unknown mutation operator {op!r}")
    return out


def run_finding_checks(value: dict[str, Any]) -> dict[str, Any]:
    checks = value["deterministic_checks"]
    results = {}
    for fixture in value["golden_fixtures"]:
        failed = failing_checks(checks, fixture["finding"])
        results[fixture["id"]] = {"verdict": "pass" if not failed else "fail", "failed_checks": failed}
    return results


def run_check_validation(value: dict[str, Any]) -> dict[str, Any]:
    """Apply the checks-of-checks trust rule to a check suite and its examples."""
    checks = value["check_suite"]
    goods = {item["id"]: item["example"] for item in value["known_good"]}
    summary = {check["id"]: {"passes_good": 0, "kills": 0} for check in checks}
    for doc in goods.values():
        for check in checks:
            if rule_passes(check["rule"], doc):
                summary[check["id"]]["passes_good"] += 1
    rejected = {cid for cid, row in summary.items() if row["passes_good"] < len(goods)}
    failures: dict[str, list[str]] = {}
    missed: list[str] = []
    for mutation in value["mutations"]:
        for good_id in mutation["applies_to"]:
            name = f"{mutation['id']}@{good_id}"
            failures[name] = failing_checks(checks, mutate(goods[good_id], mutation["operator"]))
            missed += [f"{name}:{target}" for target in mutation["targets"] if target not in failures[name]]
    for bad in value["known_bad"]:
        failures[bad["id"]] = failing_checks(checks, bad["example"])
    for failed in failures.values():
        for check_id in failed:
            summary[check_id]["kills"] += 1
    weak = {entry.rsplit(":", 1)[1] for entry in missed}
    verdicts = {}
    for check in checks:
        row = summary[check["id"]]
        if check["id"] in rejected:
            verdicts[check["id"]] = "reject"
        elif row["kills"] == 0 or check["id"] in weak:
            verdicts[check["id"]] = "revise"
        else:
            verdicts[check["id"]] = "trusted"
    caught = {name: any(c not in rejected for c in failed) for name, failed in sorted(failures.items())}
    return {"summary": summary, "caught": caught, "targeted_missed": sorted(missed), "verdicts": verdicts}


def run_evaluation_arithmetic(value: dict[str, Any]) -> dict[str, Any]:
    labels = {case["case_id"]: case["label"] for case in value["cases"]}
    positives = [cid for cid, label in labels.items() if label == value["positive_label"]]
    twins = [cid for cid, label in labels.items() if label != value["positive_label"]]
    metrics: dict[str, Any] = {}
    for run in value["runs"]:
        preds = run["predictions"]
        recall = sum(preds.get(cid) == labels[cid] for cid in positives) / len(positives)
        fp = sum(preds.get(cid) == value["positive_label"] for cid in twins) / len(twins)
        costs = [run["cost_usd"].get(cid) for cid in labels]
        cost_per_case = None if any(c is None for c in costs) else round(sum(costs) / len(costs), 6)
        metrics[run["run_id"]] = {
            "arm": run["arm"],
            "recall_points": round(100 * recall, 3),
            "twin_fp_points": round(100 * fp, 3),
            "net_points": round(100 * (recall - fp), 3),
            "errors": sum(preds.get(cid) is None for cid in labels),
            "cost_per_case_usd": cost_per_case,
        }
    by_arm: dict[str, list[dict[str, Any]]] = {}
    for run in value["runs"]:
        by_arm.setdefault(run["arm"], []).append(metrics[run["run_id"]])
    for arm, runs in by_arm.items():
        require(len(runs) == value["runs_per_arm"], f"arm {arm} needs {value['runs_per_arm']} runs")
    marks = {}
    for mark in value["pass_marks"]:
        cand, base = by_arm[mark["arm"]], by_arm.get(mark.get("baseline", ""), [])
        if mark["metric"] == "net_gain_points":
            verdict = all(c["net_points"] - b["net_points"] >= mark["threshold"] for c, b in zip(cand, base))
        elif mark["metric"] == "twin_fp_not_higher":
            verdict = all(c["twin_fp_points"] <= b["twin_fp_points"] for c, b in zip(cand, base))
        elif mark["metric"] == "recall_at_least":
            verdict = all(c["recall_points"] >= mark["threshold"] for c in cand)
        elif mark["metric"] == "spread_points_below":
            verdict = abs(cand[0]["net_points"] - cand[1]["net_points"]) < mark["threshold"]
        elif mark["metric"] == "cost_per_case_at_most":
            known = [c["cost_per_case_usd"] for c in cand]
            verdict = None if any(c is None for c in known) else all(c <= mark["threshold"] for c in known)
        else:
            raise bp.PackError(f"unknown pass-mark metric {mark['metric']!r}")
        marks[mark["id"]] = "unknown" if verdict is None else ("met" if verdict else "missed")
    return {"metrics": metrics, "marks": marks}


FIXTURES = {
    "finding_checks": run_finding_checks,
    "check_validation": run_check_validation,
    "evaluation_arithmetic": run_evaluation_arithmetic,
}


def check_fixtures(records: list[dict[str, Any]]) -> int:
    count = 0
    for record in records:
        value = record["value"]
        kind = value.get("fixture_kind")
        if kind is None:
            continue
        require(kind in FIXTURES, f"{record['key']}: unknown fixture kind")
        for check in value.get("deterministic_checks", []) + value.get("check_suite", []):
            require(set(check) >= {"id", "rule"}, f"{record['key']}: check needs id and rule")
        computed = FIXTURES[kind](value)
        require(computed == value["expected"], f"{record['key']}: worked example result differs from its recorded expectation: {computed}")
        count += 1
    return count


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def check_readme(text: str, title: str, where: str) -> None:
    lines = text.splitlines()
    require(lines and lines[0] == f"# {title}", f"{where}: README starts with the pack title")
    headings = [line for line in lines if line.startswith("## ")]
    require(headings and headings[0] == "## What this pack lets workers do", f"{where}: first section is 'What this pack lets workers do'")
    for heading in ("## Nouns", "## Verbs", "## Limits"):
        require(heading in headings, f"{where}: README needs {heading}")
    require(len(lines) <= MAX_README_LINES, f"{where}: README is longer than {MAX_README_LINES} lines")


def check_receipt(root: Path, built: dict[str, dict[str, bytes]]) -> dict[str, Any]:
    receipt = bp.load_json(root / "packs" / "VALIDATION.json")
    contract_bytes = (root / "packs" / "tessera-contract.json").read_bytes()
    require(receipt.get("format") == "ta-amps.seed-pack-validation.v1", "unexpected validation receipt")
    require(receipt["contract_snapshot_sha256"] == hashlib.sha256(contract_bytes).hexdigest(), "contract snapshot changed after the Tessera validation; rerun it")
    require(not receipt["errors"] and all(v == "rejected" for v in receipt["negative_probes"].values()), "Tessera validation recorded errors")
    require(set(receipt["packs"]) == set(built), "Tessera validation does not cover every pack; rerun it")
    for pack_id, files in built.items():
        entry = receipt["packs"][pack_id]
        require(entry["nouns_sha256"] == hashlib.sha256(files["nouns.json"]).hexdigest()
                and entry["verbs_sha256"] == hashlib.sha256(files["verbs.json"]).hexdigest(),
                f"{pack_id}: payloads changed after the Tessera validation; rerun scripts/validate_against_tessera.py")
    return receipt


class Index:
    """Everything a check needs: the contract snapshot and the freshly built library."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.contract = load_contract(root)
        self.lib = bp.load_library(root / "packs")
        self.built = bp.build_library(self.lib)
        self.docs = {pack: {name: json.loads(data) for name, data in files.items()} for pack, files in self.built.items()}
        self.pins: dict[tuple[str, str], str] = {}
        self.targets: dict[str, str] = {}
        for files in self.docs.values():
            for record in files["nouns.json"]["records"]:
                ident = (record["store"], record["key"])
                require(ident not in self.pins, f"duplicate noun {ident}")
                self.pins[ident] = bp.value_sha256(record["value"])
                self.targets[f"{record['store']}/{record['key']}"] = record["value"]["category_id"]
        self.templates = {t["brief"]["template_id"] for d in self.docs.values() for t in d["verbs.json"]["tasks"]}


def check_manifest(manifest: dict[str, Any], pack_dir: Path, pack_id: str) -> None:
    require(manifest["format"] == bp.MANIFEST_FORMAT and manifest["status"] == "proposal_only", f"{pack_id}: manifest stays a proposal")
    require(manifest["pack_id"] == pack_id, f"{pack_id}: manifest names its pack")
    require(manifest["importer"] is None and manifest["activation"]["automatic"] is False, f"{pack_id}: no importer or activation")
    require(manifest["override_policy"] == {"automatic_merge": False, "on_conflict": "stop_and_clarify"}, f"{pack_id}: no implicit merges")
    require(manifest["evaluation"]["result"] is None, f"{pack_id}: no evaluation result is claimed")
    require([entry["path"] for entry in manifest["files"]] == ["README.md", "source.json", "nouns.json", "verbs.json"], f"{pack_id}: manifest file list")
    for entry in manifest["files"]:
        require(entry["sha256"] == hashlib.sha256((pack_dir / entry["path"]).read_bytes()).hexdigest(), f"{pack_id}: manifest digest for {entry['path']}")


def validate_library(root: Path = ROOT) -> dict[str, Any]:
    idx = Index(root)
    packs_dir = root / "packs"
    totals = {"packs": 0, "nouns": 0, "verbs": 0, "worked_examples": 0}
    for pack_id, files in idx.docs.items():
        directory = packs_dir / pack_id
        present = sorted(p.name for p in directory.iterdir())
        require(present == sorted(bp.PACK_FILES), f"{pack_id}: pack directory holds exactly {sorted(bp.PACK_FILES)}")
        for name, data in idx.built[pack_id].items():
            require((directory / name).read_bytes() == data, f"{pack_id}/{name} is stale; run python3 scripts/build_packs.py")
        check_manifest(files["manifest.json"], directory, pack_id)
        check_readme((directory / "README.md").read_text(encoding="utf-8"), idx.lib.sources[pack_id]["title"], pack_id)
        records = files["nouns.json"]["records"]
        require("pack" in {record["value"]["role"] for record in records}, f"{pack_id}: descriptor noun")
        for record in records:
            check_record(record, pack_id, idx.contract, idx.targets)
        for task in files["verbs.json"]["tasks"]:
            check_task(task, pack_id, idx.contract, idx.pins, idx.targets, idx.templates)
        totals["packs"] += 1
        totals["nouns"] += len(records)
        totals["verbs"] += len(files["verbs.json"]["tasks"])
        totals["worked_examples"] += check_fixtures(records)
    receipt = check_receipt(root, idx.built)
    return {
        **totals,
        "tessera_commit": receipt["tessera"]["commit"],
        "offline_only": True,
        "live_evaluation": None,
        "reason": "Validates pack payload shapes, categories, pins and worked examples, not deployed behavior or usefulness.",
    }


if __name__ == "__main__":
    try:
        print(json.dumps(validate_library(), sort_keys=True))
    except bp.PackError as exc:
        print(f"validate_packs: {exc}", file=sys.stderr)
        sys.exit(1)
