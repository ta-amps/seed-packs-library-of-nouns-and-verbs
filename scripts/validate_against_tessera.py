#!/usr/bin/env python3
"""Validate every seed-pack noun and verb with Tessera's own models, offline.

    <tessera>/.venv/bin/python scripts/validate_against_tessera.py --tessera <tessera checkout>
    <tessera>/.venv/bin/python scripts/validate_against_tessera.py --tessera <checkout> --write

Run it with the Python environment of a local Tessera checkout (for example after
`uv sync --frozen` there). It imports Tessera's RecordWrite, TaskSpec, category
registry, validate_category_payload, canonical tags, NounRef and execution-report
checks, and validates the generated pack files against them. It also derives the
contract snapshot that `scripts/validate_packs.py` uses without Tessera installed.

It runs the checked-out Tessera's own code in-process. Beyond reading files, it
writes only a throwaway local Store database in a temporary directory for the
two-key lifecycle probe, and deletes it afterwards. It opens no network
connection, calls no model, and writes nothing to any real fabric. `--write`
updates packs/tessera-contract.json and packs/VALIDATION.json; the default mode
compares. It refuses `--write` when the Tessera files it uses are modified,
unless `--allow-dirty` is given, and records whether they were clean.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import typing
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "packs" / "tessera-contract.json"
RECEIPT_PATH = ROOT / "packs" / "VALIDATION.json"
TESSERA_FILES = (
    "src/tessera/models.py",
    "src/tessera/ontology/categories.py",
    "src/tessera/receipts.py",
    "src/tessera/execution_matching.py",
    "src/tessera/_storage.py",
    "tools/research_seed.py",
)
PAYLOAD_TAG_PROBE = (
    "area", "category", "category_id", "domain", "kind", "pack", "role", "stage",
    "status", "surface", "title", "topic", "track", "type",
)


def git_dirs(checkout: Path) -> tuple[Path, Path]:
    """The checkout's own git directory and the common directory, for clones and worktrees alike."""
    git = checkout / ".git"
    if git.is_file():
        line = git.read_text().strip()
        if not line.startswith("gitdir: "):
            raise ValueError("unrecognized .git file")
        git = (checkout / line[8:]).resolve()
    common = git
    if (git / "commondir").exists():
        common = (git / (git / "commondir").read_text().strip()).resolve()
    return git, common


def git_head(checkout: Path) -> str:
    """Read the checked-out commit from git files."""
    git, common = git_dirs(checkout)
    head = (git / "HEAD").read_text().strip()
    if not head.startswith("ref: "):
        return head
    ref = head[5:]
    for base in (git, common):
        if (base / ref).exists():
            return (base / ref).read_text().strip()
    packed = common / "packed-refs"
    if packed.exists():
        for line in packed.read_text().splitlines():
            if line.endswith(" " + ref):
                return line.split(" ", 1)[0]
    raise ValueError("cannot resolve the Tessera checkout's HEAD")


def files_clean(checkout: Path) -> bool:
    """Whether the Tessera files this check depends on match the checked-out commit (read-only git)."""
    result = subprocess.run(
        ["git", "-C", str(checkout), "status", "--porcelain", "--", *TESSERA_FILES],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip() == ""


def pattern_of(model: Any, field: str) -> str:
    for item in model.model_fields[field].metadata:
        if getattr(item, "pattern", None):
            return str(item.pattern)
    raise ValueError(f"{model.__name__}.{field} has no pattern")


def dumps(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


class Tessera:
    """The Tessera functions and models this validator relies on."""

    def __init__(self, checkout: Path) -> None:
        sys.path[:0] = [str(checkout / "src"), str(checkout / "tools")]
        from research_seed import NounRef  # noqa: PLC0415
        from tessera import _storage, execution_matching, models, receipts  # noqa: PLC0415
        from tessera.ontology import categories  # noqa: PLC0415

        self.checkout = checkout
        self.models, self.categories, self.receipts = models, categories, receipts
        self.reports, self.storage, self.NounRef = execution_matching, _storage, NounRef

    def value_sha256(self, value: Any) -> str:
        return hashlib.sha256(self.receipts.canonical_json(value).encode()).hexdigest()

    def contract(self) -> dict[str, Any]:
        m, c, r = self.models, self.categories, self.reports
        probe = {name: f"probe-{name}" for name in PAYLOAD_TAG_PROBE}
        extracted = set(self.storage.extract_payload_tags(probe))
        payload_fields = sorted(name for name in PAYLOAD_TAG_PROBE if f"probe-{name}" in extracted)
        categories = {}
        for cid, spec in sorted(c.CATEGORY_REGISTRY.items()):
            categories[cid] = {
                "kind": spec.kind,
                "title": spec.title,
                "summary": spec.summary,
                "human_sensitive": spec.human_sensitive,
                "allowed_relations": list(spec.allowed_relations),
                "canonical_tags": list(spec.canonical_tags),
                "domain_dimensions": list(spec.domain_dimensions),
                "dimensions": {
                    name: {
                        "dtype": d.dtype,
                        "min_val": d.min_val,
                        "max_val": d.max_val,
                        "allowed_values": list(d.allowed_values),
                        "direction": d.direction,
                        "required": d.required,
                    }
                    for name, d in spec.dimensions.items()
                },
            }
        return {
            "format": "ta-amps.tessera-contract-snapshot.v1",
            "purpose": (
                "Facts copied from Tessera's own code so the stdlib validator can check packs "
                "without Tessera installed. Regenerate with scripts/validate_against_tessera.py --write."
            ),
            "tessera": {
                "repository": "https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine",
                "commit": git_head(self.checkout),
                "files": {
                    path: hashlib.sha256((self.checkout / path).read_bytes()).hexdigest()
                    for path in TESSERA_FILES
                },
            },
            "patterns": {
                "name": m.NAME_PATTERN,
                "namespace": m.NAMESPACE_PATTERN,
                "record_key": pattern_of(m.RecordWrite, "key"),
                "task_id": pattern_of(m.TaskSpec, "task_id"),
                "noun_ref_key": pattern_of(self.NounRef, "key"),
            },
            "fields": {
                "RecordWrite": sorted(m.RecordWrite.model_fields),
                "TaskSpec": sorted(m.TaskSpec.model_fields),
                "NounRef": sorted(self.NounRef.model_fields),
                "governed": sorted(m._GovernedModel.model_fields),
            },
            "limits": {
                "task_priority": [0, 100],
                "idempotency_key_max_length": 256,
                "max_dependencies": m.MAX_DEPENDENCIES,
                "max_report_bytes": r.MAX_REPORT_BYTES,
            },
            "visibility_scopes": sorted(m.VISIBILITY_SCOPES),
            "effect_classes": list(typing.get_args(m.EffectClass)),
            "relation_types": list(c.ALLOWED_RELATION_TYPES),
            "verification_tiers": list(c.VERIFICATION_TIERS),
            "payload_tag_fields": payload_fields,
            "report": {
                "root_fields": sorted(r.ROOT_FIELDS),
                "summary_fields": ["input", "problem", "solution"],
                "contract_fields": sorted(r.CONTRACT_FIELDS),
                "block_kinds": sorted(r.BLOCK_KINDS),
                "token_fields": sorted(r.TOKEN_FIELDS),
                "shape_domain": "execution-shape-v1\\0",
            },
            "categories": categories,
        }


def load_packs() -> tuple[Any, dict[str, dict[str, bytes]]]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_packs  # noqa: PLC0415

    lib = build_packs.load_library()
    built = build_packs.build_library(lib)
    for pack_id, files in built.items():
        for name, data in files.items():
            if (ROOT / "packs" / pack_id / name).read_bytes() != data:
                raise SystemExit(f"{pack_id}/{name} is stale; run python3 scripts/build_packs.py first")
    return build_packs, built


def stand_in_instance(t: Any, build_packs: Any, task: dict[str, Any], records_by_ref: dict[Any, Any],
                      required_only: bool, queue: str | None = None) -> dict[str, Any]:
    """Fill a template with schema-valid stand-ins: any pack noun of each slot's category."""
    brief = task["brief"]
    slots: dict[str, Any] = {}
    for name, slot in brief["slot_specs"].items():
        if required_only and not slot["required"]:
            continue
        noun = next((r for r in records_by_ref.values() if r["value"]["category_id"] == slot["category"]), None)
        if noun is None:
            raise ValueError(f"no stand-in noun of category {slot['category']}")
        pin = {"store": noun["store"], "key": noun["key"], "version": 1, "value_sha256": t.value_sha256(noun["value"])}
        slots[name] = [pin] if slot["many"] else pin
    params = {name: param_stand_in(spec) for name, spec in brief["param_specs"].items()}
    return build_packs.instantiate(task, slots, params, queue)


def store_probe(t: Any, build_packs: Any, docs: dict[str, Any], records_by_ref: dict[Any, Any]) -> dict[str, Any]:
    """Exercise real Store visibility with distinct keys on a throwaway local database.

    An importer on a team surface writes every pack noun; a different worker key on the same surface
    reads each one back and claims every instantiated template; keys on another surface, or with no
    surface, see and claim nothing. Workers submit a blocked output with the template's execution
    report, write one surface-only output the requester can read, and update a success record by
    compare-and-set. The embedded Store applies visibility and ownership; HTTP grants are a separate layer.
    """
    from tessera import QueueConfig, RecordWrite, Store, TaskSpec  # noqa: PLC0415
    from tessera.errors import NotFound  # noqa: PLC0415

    team, other, queue = "seedpack-team", "other-team", "probe-queue"
    records = [r for files in docs.values() for r in files["nouns.json"]["records"]]
    tasks = [task for files in docs.values() for task in files["verbs.json"]["tasks"]]
    out: dict[str, Any] = {"records_written": 0, "records_read_by_second_key": 0, "records_hidden_from_other_surfaces": 0,
                           "instances_enqueued": 0, "claimed_by_second_key": 0, "claims_by_other_surfaces": 0,
                           "blocked_outputs_submitted": 0, "output_read_by_requester": False,
                           "output_hidden_from_other_surface": False, "cas_update_by_second_key": False}
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "probe.db")
        store.define_queue(QueueConfig(name=queue))
        with store.scope_context(key_id="importer", surface=team):
            store.put_records([RecordWrite.model_validate(r) for r in records])
            out["records_written"] = len(records)
        with store.scope_context(key_id="worker", surface=team):
            for r in records:
                got = store.get_record(r["store"], r["key"], 1)
                if t.value_sha256(got.value) == t.value_sha256(r["value"]) and got.producer_surface == f"surface:{team}":
                    out["records_read_by_second_key"] += 1
        hidden_counts = []
        for scope in ({"key_id": "outsider", "surface": other}, {"key_id": "outsider"}):
            hidden = 0
            with store.scope_context(**scope):
                for r in records:
                    try:
                        store.get_record(r["store"], r["key"], 1)
                    except NotFound:
                        hidden += 1
            hidden_counts.append(hidden)
        out["records_hidden_from_other_surfaces"] = min(hidden_counts)
        with store.scope_context(key_id="requester", surface=team):
            for task in tasks:
                store.enqueue(TaskSpec.model_validate(stand_in_instance(t, build_packs, task, records_by_ref, True, queue)))
                out["instances_enqueued"] += 1
        for scope in ({"key_id": "outsider", "surface": other}, {"key_id": "outsider"}):
            with store.scope_context(**scope):
                if store.claim(queue, "outsider-worker") is not None:
                    out["claims_by_other_surfaces"] += 1
        with store.scope_context(key_id="worker", surface=team):
            while (lease := store.claim(queue, "worker-1")) is not None:
                out["claimed_by_second_key"] += 1
                brief = lease.brief
                output = {"outcome": "blocked", "summary": "Store probe: lifecycle check only.", "artifacts": [],
                          "checks": [], "unknowns": [], "blocked_question": "This is a store probe; no work was attempted."}
                if build_packs.schema_errors(brief["output_schema"], output):
                    raise ValueError(f"{brief['template_id']}: probe output does not match the output schema")
                report = copy.deepcopy(brief["execution_report"]["template"])
                report["harness"] = {"name": "validate_against_tessera store probe", "version": "1"}
                report["model"] = {"name": "none"}
                store.submit(lease.task_id, lease.fencing_token, output, idempotency_key=f"probe:{lease.task_id}",
                             execution_report=report)
                out["blocked_outputs_submitted"] += 1
            output_noun = RecordWrite.model_validate({
                "store": "seedpack.probe.outputs", "key": "probe.output.1", "expected_version": 0,
                "visibility_scope": "surface_only", "value": {"category_id": "noun.eval_run", "note": "probe"},
                "tags": ["category:noun.eval_run", "status:quarantined"]})
            store.put_records([output_noun])
            success = next(r for r in records if r["value"]["role"] == "success_record")
            update = copy.deepcopy(success)
            update["expected_version"] = 1
            update["value"]["counts_reason"] = "probe update"
            store.put_records([RecordWrite.model_validate(update)])
            out["cas_update_by_second_key"] = store.get_record(success["store"], success["key"], 2).version == 2
        with store.scope_context(key_id="requester", surface=team):
            out["output_read_by_requester"] = store.get_record("seedpack.probe.outputs", "probe.output.1", 1).version == 1
        with store.scope_context(key_id="outsider", surface=other):
            try:
                store.get_record("seedpack.probe.outputs", "probe.output.1", 1)
            except NotFound:
                out["output_hidden_from_other_surface"] = True
    out["passed"] = (
        out["records_read_by_second_key"] == out["records_written"] == out["records_hidden_from_other_surfaces"]
        and out["claimed_by_second_key"] == out["instances_enqueued"] == len(tasks) == out["blocked_outputs_submitted"]
        and out["claims_by_other_surfaces"] == 0
        and out["output_read_by_requester"] and out["output_hidden_from_other_surface"] and out["cas_update_by_second_key"]
    )
    return out


def param_stand_in(spec: dict[str, Any]) -> Any:
    """A structurally valid parameter value: the default, the first enum value or a schema-shaped guess."""
    if "default" in spec:
        return spec["default"]
    schema = spec["schema"]
    if schema.get("enum"):
        return schema["enum"][0]
    kind = schema.get("type")
    if kind == "integer":
        return int(schema.get("minimum", 1))
    if kind == "boolean":
        return False
    if kind == "object":
        return {}
    if kind == "array":
        return []
    import re  # noqa: PLC0415

    for guess in ("a", "A", "en", "2026-10-29", "stand-in", "x"):
        if re.search(schema.get("pattern", ""), guess) and len(guess) >= schema.get("minLength", 0):
            return guess
    raise ValueError("no stand-in value fits the parameter schema")


def expect_rejection(action: Any) -> str:
    try:
        result = action()
    except Exception:  # noqa: BLE001 - any rejection counts; the probe records it
        return "rejected"
    if getattr(result, "valid", True) is False:
        return "rejected"
    return "ACCEPTED"


def validate(t: Tessera, build_packs: Any, built: dict[str, dict[str, bytes]]) -> dict[str, Any]:
    m, c = t.models, t.categories
    errors: list[str] = []
    counts = {name: 0 for name in (
        "RecordWrite", "canonical_category_tags_strict", "noun_validate_category_payload", "value_sha256",
        "TaskSpec", "verb_validate_category_payload", "NounRef_pins", "normalize_report", "shape_hash",
        "instantiated_TaskSpec",
    )}
    records_by_ref: dict[tuple[str, str], dict[str, Any]] = {}
    docs = {pack: {name: json.loads(data) for name, data in files.items()} for pack, files in built.items()}
    for pack_id, files in docs.items():
        for record in files["nouns.json"]["records"]:
            records_by_ref[(record["store"], record["key"])] = record
    packs_summary: dict[str, Any] = {}
    for pack_id, files in sorted(docs.items()):
        manifest = files["manifest.json"]
        noun_digests = {entry["key"]: entry["value_sha256"] for entry in manifest["nouns"]}
        shape_digests = {entry["template_id"]: entry["report_shape_sha256"] for entry in manifest["verbs"]}
        category_counts: dict[str, int] = {}
        for record in files["nouns.json"]["records"]:
            where = f"{pack_id}/{record['key']}"
            try:
                w = m.RecordWrite.model_validate(record)
                counts["RecordWrite"] += 1
                for field in ("store", "key", "producer_surface", "visibility_scope", "allowed_surfaces", "target_cohorts", "tags"):
                    if getattr(w, field) != record[field]:
                        errors.append(f"{where}: RecordWrite normalized {field}")
                if w.expected_version != 0:
                    errors.append(f"{where}: not create-only")
                cat = record["value"]["category_id"]
                category_counts[cat] = category_counts.get(cat, 0) + 1
                effective = m.canonical_category_tags(
                    w.value, [*w.tags, *t.storage.extract_payload_tags(w.value)], strict=True
                )
                if effective[0] != f"category:{cat}" or c.CATEGORY_REGISTRY[cat].kind != "noun":
                    errors.append(f"{where}: category tag projection {effective[:1]}")
                if set(effective) != set(m.normalize_tags(w.tags)):
                    errors.append(f"{where}: the store would add tags {sorted(set(effective) - set(w.tags))}")
                counts["canonical_category_tags_strict"] += 1
                result = c.validate_category_payload(cat, record["value"]["dimensions"], record["value"]["relations"], w.tags)
                if not result.valid or result.errors or result.warnings:
                    errors.append(f"{where}: {result.errors} {result.warnings}")
                else:
                    counts["noun_validate_category_payload"] += 1
                if t.value_sha256(w.value) != noun_digests[record["key"]]:
                    errors.append(f"{where}: value_sha256 differs from manifest")
                else:
                    counts["value_sha256"] += 1
            except Exception as exc:  # noqa: BLE001 - every failure is reported
                errors.append(f"{where}: {type(exc).__name__}: {exc}")
        for task in files["verbs.json"]["tasks"]:
            brief = task["brief"]
            where = f"{pack_id}/{brief['template_id']}"
            try:
                spec = m.TaskSpec.model_validate(task)
                counts["TaskSpec"] += 1
                for field in ("queue", "kind", "effect_class", "priority", "idempotency_key", "depends_on",
                              "producer_surface", "visibility_scope", "allowed_surfaces", "target_cohorts", "tags"):
                    if getattr(spec, field) != task[field]:
                        errors.append(f"{where}: TaskSpec normalized {field}")
                if c.CATEGORY_REGISTRY[task["kind"]].kind != "verb":
                    errors.append(f"{where}: kind is not a verb category")
                result = c.validate_category_payload(task["kind"], brief["dimensions"], brief["relations"], spec.tags)
                if not result.valid or result.errors or result.warnings:
                    errors.append(f"{where}: {result.errors} {result.warnings}")
                else:
                    counts["verb_validate_category_payload"] += 1
                pins = brief["inputs"]["pinned"] + [item["template"] for item in brief["output_contract"]["produces"]]
                for pin in pins:
                    ref = t.NounRef.model_validate(pin)
                    target = records_by_ref.get((ref.store, ref.key))
                    if target is None or t.value_sha256(target["value"]) != ref.value_sha256 or ref.version != 1:
                        errors.append(f"{where}: pin {ref.key} does not match its noun")
                    else:
                        counts["NounRef_pins"] += 1
                report = brief["execution_report"]["template"]
                t.reports.normalize_report(report)
                counts["normalize_report"] += 1
                shape = t.reports.fingerprints({}, report)["shape_hash"]
                if shape != brief["execution_report"]["shape_sha256"] or shape != shape_digests[brief["template_id"]]:
                    errors.append(f"{where}: execution shape fingerprint differs")
                else:
                    counts["shape_hash"] += 1
                for required_only in (True, False):
                    instance = stand_in_instance(t, build_packs, task, records_by_ref, required_only)
                    m.TaskSpec.model_validate(instance)
                counts["instantiated_TaskSpec"] += 1
            except Exception as exc:  # noqa: BLE001 - every failure is reported
                errors.append(f"{where}: {type(exc).__name__}: {exc}")
        packs_summary[pack_id] = {
            "nouns_sha256": hashlib.sha256(built[pack_id]["nouns.json"]).hexdigest(),
            "verbs_sha256": hashlib.sha256(built[pack_id]["verbs.json"]).hexdigest(),
            "records": len(files["nouns.json"]["records"]),
            "tasks": len(files["verbs.json"]["tasks"]),
            "noun_categories": dict(sorted(category_counts.items())),
            "verb_kinds": dict(sorted(
                (kind, sum(1 for tk in files["verbs.json"]["tasks"] if tk["kind"] == kind))
                for kind in {tk["kind"] for tk in files["verbs.json"]["tasks"]}
            )),
        }
    sample = next(iter(records_by_ref.values()))
    conflict = {"category_id": "noun.seed_hypothesis", "kind": "verb.solve_draft"}
    probes = {
        "unregistered_category": expect_rejection(lambda: c.validate_category_payload("noun.not_registered", sample["value"]["dimensions"])),
        "dimension_out_of_bounds": expect_rejection(lambda: c.validate_category_payload("noun.seed_hypothesis", {**sample["value"]["dimensions"], "determinism": 1.5})),
        "missing_required_dimension": expect_rejection(lambda: c.validate_category_payload("noun.seed_hypothesis", {"determinism": 0.0})),
        "relation_not_allowed_for_category": expect_rejection(lambda: c.validate_category_payload(
            "noun.feed_source", sample["value"]["dimensions"], [{"relation": "produces_noun", "target_id": "x/y"}])),
        "conflicting_payload_category": expect_rejection(lambda: m.canonical_category_tags(
            conflict, ["category:noun.seed_hypothesis", *t.storage.extract_payload_tags(conflict)], strict=True)),
        "noun_ref_with_namespace": expect_rejection(lambda: t.NounRef.model_validate(
            {"namespace": "main", "store": "a", "key": "b", "version": 1, "value_sha256": "0" * 64})),
        "noun_ref_bad_digest": expect_rejection(lambda: t.NounRef.model_validate(
            {"store": "a", "key": "b", "version": 1, "value_sha256": "not-a-digest"})),
        "report_unknown_root_field": expect_rejection(lambda: t.reports.normalize_report({"version": 1, "went_right": []})),
        "task_unknown_visibility": expect_rejection(lambda: m.TaskSpec.model_validate({"queue": "q", "brief": {}, "visibility_scope": "secret"})),
        "record_bad_key": expect_rejection(lambda: m.RecordWrite.model_validate({"store": "s", "key": "-bad", "value": {}})),
    }
    for name, outcome in probes.items():
        if outcome != "rejected":
            errors.append(f"negative probe {name} was accepted")
    try:
        probe = store_probe(t, build_packs, docs, records_by_ref)
    except Exception as exc:  # noqa: BLE001 - reported as an error, never hidden
        probe = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
    if not probe.get("passed"):
        errors.append(f"store probe failed: {probe}")
    return {"packs": packs_summary, "checks": counts, "negative_probes": probes, "store_probe": probe, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tessera", type=Path, required=True, help="path to a Tessera checkout")
    parser.add_argument("--write", action="store_true", help="write the contract snapshot and receipt")
    parser.add_argument("--allow-dirty", action="store_true", help="write even if the Tessera files are modified")
    args = parser.parse_args(argv)
    clean = files_clean(args.tessera.resolve())
    if args.write and not clean and not args.allow_dirty:
        parser.error("the Tessera files differ from their commit; use a clean checkout or --allow-dirty")
    t = Tessera(args.tessera.resolve())
    build_packs, built = load_packs()
    contract_bytes = dumps(t.contract())
    result = validate(t, build_packs, built)
    receipt = {
        "format": "ta-amps.seed-pack-validation.v1",
        "scope": (
            "Offline validation of every generated noun and verb with Tessera's own models and "
            "functions at the commit below, plus a two-key lifecycle probe on a throwaway local Store. "
            "Shape, category, relation, digest, report and visibility checks only; not admission, "
            "import into a real fabric, worker execution or deployment evidence."
        ),
        "tessera": {**json.loads(contract_bytes)["tessera"], "files_clean": clean},
        "contract_snapshot_sha256": hashlib.sha256(contract_bytes).hexdigest(),
        "packs": result["packs"],
        "checks": result["checks"],
        "negative_probes": result["negative_probes"],
        "errors": result["errors"],
        "local_store_probe": result["store_probe"],
        "network_requests": 0,
        "model_calls": 0,
        "fabric_records_written": 0,
        "fabric_tasks_enqueued": 0,
    }
    receipt_bytes = dumps(receipt)
    if result["errors"]:
        for line in result["errors"]:
            print("validate_against_tessera: " + line, file=sys.stderr)
        return 1
    if args.write:
        CONTRACT_PATH.write_bytes(contract_bytes)
        RECEIPT_PATH.write_bytes(receipt_bytes)
    else:
        stale = [p.name for p, b in ((CONTRACT_PATH, contract_bytes), (RECEIPT_PATH, receipt_bytes))
                 if not p.exists() or p.read_bytes() != b]
        if stale:
            print(f"validate_against_tessera: stale {stale}; rerun with --write", file=sys.stderr)
            return 1
    print(json.dumps({"checks": result["checks"], "negative_probes_rejected": len(result["negative_probes"]),
                      "packs": len(result["packs"]), "tessera_commit": receipt["tessera"]["commit"],
                      "written": args.write}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
