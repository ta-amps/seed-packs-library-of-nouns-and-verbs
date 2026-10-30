"""Seed-pack library checks: determinism, offline builds, scope, authority limits and worked examples.

Standard library only. No network, model, service, record write or enqueue.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bp = load_module("build_packs")
vp = load_module("validate_packs")
IDX = vp.Index(ROOT)
PACKS = sorted(IDX.docs)


def key(pack: str, slug: str) -> str:
    return f"{pack}.v{IDX.lib.sources[pack]['version']}.{slug}"


def record(pack: str, slug: str) -> dict:
    wanted = key(pack, slug)
    for item in IDX.docs[pack]["nouns.json"]["records"]:
        if item["key"] == wanted:
            return copy.deepcopy(item)
    raise KeyError(wanted)


def task(template_id: str) -> dict:
    for files in IDX.docs.values():
        for item in files["verbs.json"]["tasks"]:
            if item["brief"]["template_id"] == template_id:
                return copy.deepcopy(item)
    raise KeyError(template_id)


def pin(pack: str, slug: str) -> dict:
    store = f"seedpack.{pack}"
    return {"store": store, "key": key(pack, slug), "version": 1, "value_sha256": IDX.pins[(store, key(pack, slug))]}


def check_record(item: dict) -> None:
    pack = item["value"]["pack"]
    vp.check_record(item, pack, IDX.contract, IDX.targets, IDX.values, IDX.lib.sources[pack]["version"])


def check_task(item: dict) -> None:
    vp.check_task(item, item["brief"]["pack"], IDX.contract, IDX.pins, IDX.targets, IDX.templates)


def rekey(item: dict) -> dict:
    """Recompute a template's idempotency key so a test isolates one other change."""
    slug = item["brief"]["template_id"].split(".", 1)[1]
    item["idempotency_key"] = bp.template_idempotency_key(item["brief"]["pack"], slug, item["queue"], item["kind"], item["brief"])
    return item


def stand_ins(template: dict, required_only: bool) -> tuple[dict, dict]:
    """Schema-valid slot pins (any library noun of the slot's category) and parameter values."""
    slots = {}
    for name, spec in template["brief"]["slot_specs"].items():
        if required_only and not spec["required"]:
            continue
        target = next(t for t, cat in sorted(IDX.targets.items()) if cat == spec["category"])
        store, noun_key = target.split("/", 1)
        ref = {"store": store, "key": noun_key, "version": 1, "value_sha256": IDX.pins[(store, noun_key)]}
        slots[name] = [ref] if spec["many"] else ref
    params = {}
    for name, spec in template["brief"]["param_specs"].items():
        if "default" in spec:
            continue
        schema = spec["schema"]
        if schema.get("enum"):
            params[name] = schema["enum"][0]
        elif schema.get("type") == "integer":
            params[name] = schema.get("minimum", 1)
        elif schema.get("type") == "object":
            params[name] = {}
        else:
            params[name] = next(g for g in ("a", "A", "en", "2026-10-29", "stand-in")
                                if not vp.schema_errors(schema, g))
    return slots, params


class LibraryChecks(unittest.TestCase):
    def test_every_pack_validates(self):
        summary = vp.validate_library(ROOT)
        self.assertEqual(summary["packs"], len(PACKS))
        self.assertEqual(summary["nouns"], sum(len(IDX.docs[p]["nouns.json"]["records"]) for p in PACKS))
        self.assertEqual(summary["verbs"], sum(len(IDX.docs[p]["verbs.json"]["tasks"]) for p in PACKS))
        self.assertEqual(summary["worked_examples"], 6)
        self.assertTrue(summary["offline_only"])
        self.assertIsNone(summary["live_evaluation"])

    def test_required_packs_present(self):
        for pack in ("repo-review", "video-showcase", "tool-discovery", "evaluation-design", "checks-of-checks",
                     "decomposition-patterns", "taste-palettes", "harness-onboarding-e2e", "security-review",
                     "cost-optimization", "docs-improvement", "benchmark-scores", "visual-rendering",
                     "public-good-kits", "freshness-checks"):
            self.assertIn(pack, PACKS)

    def test_packs_are_plain_english_collections(self):
        for pack in PACKS:
            source = IDX.lib.sources[pack]
            self.assertTrue(source["summary"].startswith(bp.PACK_PHRASE), pack)
            descriptor = record(pack, "pack")
            self.assertTrue(descriptor["value"]["title"].startswith(bp.PACK_PHRASE), pack)
            readme = (ROOT / "packs" / pack / "README.md").read_text()
            self.assertIsNone(vp.SURFACE_NAMES.search(readme), pack)

    def test_repo_review_question_bank(self):
        questions = [r for r in IDX.docs["repo-review"]["nouns.json"]["records"] if r["value"]["role"] == "question"]
        self.assertEqual(len(questions), 50)
        families = {q["value"]["family"] for q in questions}
        self.assertEqual(families, {"cost", "reliability-security", "speed", "reach-distribution", "revenue"})
        for q in questions:
            value = q["value"]
            for field in ("applies_when", "evidence_required", "spawns_verbs"):
                self.assertTrue(value[field], f"{q['key']} needs {field}")
            self.assertTrue(value["rubric"]["strong_answer"] and value["rubric"]["fails_if"])
            self.assertTrue(value["falsified_by"] and value["unknown_when"])
            for verb in value["spawns_verbs"]:
                self.assertIn(verb, IDX.templates)
        bank = record("repo-review", "question-bank")["value"]
        self.assertEqual({q["pin"]["key"] for q in bank["questions"]}, {q["key"] for q in questions})

    def test_daily_refresh_packs_have_unactivated_schedules(self):
        schedules = [r for p in PACKS for r in IDX.docs[p]["nouns.json"]["records"] if r["value"]["role"] == "schedule_proposal"]
        self.assertEqual({r["value"]["pack"] for r in schedules}, {"tool-discovery", "benchmark-scores", "freshness-checks"})
        for item in schedules:
            self.assertEqual(item["value"]["activation"], "not_activated")
            self.assertIn("No scheduler is activated", item["value"]["activation_path"])
            for verb in item["value"]["enqueues"]:
                self.assertIn(task(verb)["kind"], {"verb.fetch_feed", "verb.recheck_fragility", "verb.verify_gate"})

    def test_build_is_byte_identical_and_committed(self):
        first = bp.build_library(bp.load_library())
        second = bp.build_library(bp.load_library())
        self.assertEqual(first, second)
        for pack, files in first.items():
            for name, data in files.items():
                self.assertEqual((ROOT / "packs" / pack / name).read_bytes(), data, f"{pack}/{name}")

    def test_build_is_identical_across_environments(self):
        script = (
            "import hashlib,sys;sys.path.insert(0,'scripts');import build_packs as b;"
            "built=b.build_library(b.load_library());"
            "print(hashlib.sha256(b''.join(built[p][n] for p in sorted(built) for n in sorted(built[p]))).hexdigest())"
        )
        digests = set()
        for env in ({"PYTHONHASHSEED": "1", "TZ": "UTC", "LC_ALL": "C"},
                    {"PYTHONHASHSEED": "4242", "TZ": "Pacific/Auckland", "LC_ALL": "C.UTF-8"}):
            result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, env={**os.environ, **env},
                                    capture_output=True, text=True, check=True)
            digests.add(result.stdout.strip())
        built = bp.build_library(bp.load_library())
        digests.add(hashlib.sha256(b"".join(built[p][n] for p in sorted(built) for n in sorted(built[p]))).hexdigest())
        self.assertEqual(len(digests), 1)

    def test_build_and_validation_never_touch_network_processes_or_files(self):
        script = (
            "import sys\n"
            "blocked=('socket.','subprocess.','os.system','os.exec','os.posix_spawn','os.fork','urllib.Request','http.client','ctypes')\n"
            "def hook(event,args):\n"
            "    if event.startswith(blocked):\n"
            "        raise RuntimeError('forbidden '+event)\n"
            "    if event=='open' and len(args)>1 and isinstance(args[1],str) and any(m in args[1] for m in 'wax+'):\n"
            "        raise RuntimeError('write attempted '+str(args[0]))\n"
            "sys.addaudithook(hook)\n"
            "sys.path.insert(0,'scripts')\n"
            "import build_packs, validate_packs\n"
            "build_packs.build_library(build_packs.load_library())\n"
            "print(validate_packs.validate_library()['packs'])\n"
        )
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(int(result.stdout.strip()), len(PACKS))

    def test_receipt_covers_current_payloads_and_store_probe(self):
        receipt = json.loads((ROOT / "packs" / "VALIDATION.json").read_text())
        self.assertEqual(receipt["errors"], [])
        self.assertTrue(receipt["tessera"]["files_clean"])
        self.assertEqual(set(receipt["packs"]), set(PACKS))
        self.assertTrue(all(v == "rejected" for v in receipt["negative_probes"].values()))
        for name in ("network_requests", "model_calls", "fabric_records_written", "fabric_tasks_enqueued"):
            self.assertEqual(receipt[name], 0)
        total_nouns = sum(len(IDX.docs[p]["nouns.json"]["records"]) for p in PACKS)
        total_verbs = sum(len(IDX.docs[p]["verbs.json"]["tasks"]) for p in PACKS)
        for name in ("RecordWrite", "canonical_category_tags_strict", "noun_validate_category_payload", "value_sha256"):
            self.assertEqual(receipt["checks"][name], total_nouns)
        for name in ("TaskSpec", "verb_validate_category_payload", "normalize_report", "shape_hash", "instantiated_TaskSpec"):
            self.assertEqual(receipt["checks"][name], total_verbs)
        probe = receipt["local_store_probe"]
        self.assertTrue(probe["passed"])
        self.assertEqual(probe["records_read_by_second_key"], total_nouns)
        self.assertEqual(probe["records_hidden_from_other_surfaces"], total_nouns)
        self.assertEqual(probe["claimed_by_second_key"], total_verbs)
        self.assertEqual(probe["blocked_outputs_submitted"], total_verbs)
        self.assertEqual(probe["claims_by_other_surfaces"], 0)
        self.assertTrue(probe["cas_update_by_second_key"] and probe["output_read_by_requester"] and probe["output_hidden_from_other_surface"])

    def test_stale_receipt_is_detected(self):
        built = copy.deepcopy(IDX.built)
        built["repo-review"]["nouns.json"] += b" "
        with self.assertRaises(bp.PackError):
            vp.check_receipt(ROOT, built)

    def test_doc_counts_must_match_the_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("README.md", "docs/status.md", "packs/README.md"):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / name, root / name)
            vp.check_doc_counts(root, IDX)
            text = (root / "packs" / "README.md").read_text()
            (root / "packs" / "README.md").write_text(text.replace("| 66 | 6 |", "| 67 | 6 |"))
            with self.assertRaises(bp.PackError):
                vp.check_doc_counts(root, IDX)


class VerbTemplateChecks(unittest.TestCase):
    def test_every_template_offers_unknown_and_no_change(self):
        for pack in PACKS:
            for item in IDX.docs[pack]["verbs.json"]["tasks"]:
                brief = item["brief"]
                self.assertIn("no_change", brief["permitted_outcomes"])
                self.assertIn("unknown", brief["permitted_outcomes"])
                self.assertEqual(brief["outcome_requirements"]["unknown"], ["unknowns"])
                self.assertEqual(brief["outcome_requirements"]["no_change"], ["no_change_reason"])

    def test_workers_create_nouns_and_propose_verbs(self):
        for pack in PACKS:
            for item in IDX.docs[pack]["verbs.json"]["tasks"]:
                brief = item["brief"]
                self.assertEqual(brief["creates"], bp.CREATES)
                self.assertEqual(brief["guidance"]["required"][-1], bp.FOLLOW_UP_STEP)
                props = brief["output_schema"]["properties"]
                self.assertEqual(props["proposed_verbs"]["items"]["properties"]["kind"]["pattern"], "^verb\\.[a-z_]+$")
                self.assertIn("proposed_nouns", props)
                self.assertEqual(brief["execution"]["maximum_automatically_enqueued_children"], 0)
        proposal = {"kind": "verb.solve_draft", "title": "Follow up", "outcome": "One more finding", "why": "A gap", "priority": 2}
        output = {"outcome": "blocked", "summary": "x", "artifacts": [], "checks": [], "unknowns": [], "blocked_question": "q",
                  "proposed_verbs": [proposal]}
        schema = task("repo-review.select-questions")["brief"]["output_schema"]
        self.assertEqual(vp.schema_errors(schema, output), [])
        self.assertTrue(vp.schema_errors(schema, {**output, "proposed_verbs": [{**proposal, "kind": "enqueue.now"}]}))

    def test_every_template_has_typed_io_checks_and_report(self):
        for pack in PACKS:
            for item in IDX.docs[pack]["verbs.json"]["tasks"]:
                brief = item["brief"]
                report = brief["execution_report"]
                self.assertEqual(report["template"]["contract"], {"input_schema": brief["input_schema"], "output_schema": brief["output_schema"]})
                self.assertEqual(report["shape_sha256"], bp.shape_sha256(brief["input_schema"], brief["output_schema"]))
                self.assertEqual(set(brief["output_schema"]["properties"]["run_notes"]["properties"]),
                                 {"went_right", "went_wrong", "next_steps", "ideas"})
                self.assertTrue(brief["acceptance_checks"])
                self.assertFalse(brief["execution"]["server_fallback"])
                self.assertIn(brief["execution"]["network"]["mode"], bp.NETWORK_MODES)
                self.assertEqual(brief["output_contract"]["visibility_scope"], "surface_only")

    def test_every_template_instantiates_with_required_slots_only_and_with_all(self):
        for pack in PACKS:
            for item in IDX.docs[pack]["verbs.json"]["tasks"]:
                for required_only in (True, False):
                    slots, params = stand_ins(item, required_only)
                    instance = bp.instantiate(item, slots, params, "team-queue")
                    with self.subTest(template=item["brief"]["template_id"], required_only=required_only):
                        self.assertEqual(vp.schema_errors(instance["brief"]["input_schema"], instance["brief"]["inputs"]), [])
                        self.assertEqual(instance["queue"], "team-queue")

    def test_instantiate_fills_slots_and_changes_identity(self):
        template = task("repo-review.profile-repo")
        snapshot = pin("repo-review", "example.repo-snapshot")
        instance = bp.instantiate(template, {"repo_snapshot": snapshot}, {})
        self.assertEqual(instance["brief"]["inputs"]["slots"]["repo_snapshot"], snapshot)
        self.assertEqual(instance["brief"]["instantiation"]["status"], "instance")
        self.assertNotEqual(instance["idempotency_key"], template["idempotency_key"])
        self.assertTrue(instance["idempotency_key"].startswith("seedpack:repo-review:profile-repo:"))
        self.assertEqual(bp.instantiate(template, {"repo_snapshot": snapshot}, {}), instance)
        self.assertNotEqual(bp.instantiate(template, {"repo_snapshot": snapshot}, {}, "other-queue")["idempotency_key"],
                            instance["idempotency_key"])
        self.assertEqual(template, task("repo-review.profile-repo"))

    def test_instantiate_refuses_missing_malformed_or_out_of_schema_inputs(self):
        template = task("repo-review.investigate-family")
        good = {"store": "s", "key": "k", "version": 1, "value_sha256": "0" * 64}
        both = {"repo_profile": good, "review_plan": good}
        cases = [
            ({"repo_profile": good}, {"family": "cost"}, None),
            ({"repo_profile": good, "review_plan": {**good, "version": 0}}, {"family": "cost"}, None),
            (both, {}, None),
            ({**both, "extra": good}, {"family": "cost"}, None),
            (both, {"family": "nonsense"}, None),
            (both, {"family": "cost", "allow_sandboxed_runs": "yes"}, None),
            (both, {"family": "cost", "output_store": "Bad Store"}, None),
            (both, {"family": "cost", "output_store": "seedpack.outputs\n"}, None),
            (both, {"family": "cost"}, "Bad Queue"),
        ]
        for slots, params, queue in cases:
            with self.subTest(slots=sorted(slots), params=params, queue=queue), self.assertRaises(bp.PackError):
                bp.instantiate(template, slots, params, queue)
        instance = bp.instantiate(template, both, {"family": "cost"})
        with self.assertRaises(bp.PackError):
            bp.instantiate(instance, {}, {})
        sheet = task("taste-palettes.assemble-comparison")
        slots, _ = stand_ins(sheet, True)
        with self.assertRaises(bp.PackError):
            bp.instantiate(sheet, slots, {"order_seed": 2**53 + 1})

    def test_human_verbs_use_no_model(self):
        humans = [t for p in PACKS for t in IDX.docs[p]["verbs.json"]["tasks"] if t["brief"]["claimant"] == "human"]
        self.assertGreaterEqual(len(humans), 5)
        for item in humans:
            self.assertEqual(item["brief"]["execution"]["model_use"], "none")


class NegativeChecks(unittest.TestCase):
    def assert_record_rejected(self, mutate, pack="repo-review", slug="question.cost.ci-minutes"):
        item = record(pack, slug)
        mutate(item)
        with self.assertRaises(bp.PackError):
            check_record(item)

    def assert_task_rejected(self, mutate, template_id="repo-review.investigate-family", rekeyed=True):
        item = task(template_id)
        mutate(item)
        if rekeyed:
            rekey(item)
        with self.assertRaises(bp.PackError):
            check_task(item)

    def test_unmodified_fixtures_pass(self):
        check_record(record("repo-review", "question.cost.ci-minutes"))
        check_task(task("repo-review.investigate-family"))

    def test_record_boundaries(self):
        cases = [
            lambda r: r["value"].update(category_id="noun.not_registered"),
            lambda r: r["value"].update(category_id="noun.case_bundle"),
            lambda r: r["value"]["dimensions"].update(determinism=0.9),
            lambda r: r["value"]["dimensions"].pop("safety_compliance"),
            lambda r: r["value"]["dimensions"].update(verification_tier="steward_attested"),
            lambda r: r["value"]["relations"].append({"relation": "produces_noun", "target_id": r["value"]["relations"][0]["target_id"],
                                                      "target_category": "noun.benchmark_suite", "note": ""}),
            lambda r: r["value"]["relations"].append({"relation": "requires_noun", "target_id": "seedpack.x/missing",
                                                      "target_category": "noun.skill_pack", "note": ""}),
            lambda r: r.update(visibility_scope="public_commons"),
            lambda r: r.update(visibility_scope="private"),
            lambda r: r.update(allowed_surfaces=["surface:other"]),
            lambda r: r.update(expected_version=1),
            lambda r: r.update(key=r["key"].replace(".v0.1.0.", ".")),
            lambda r: r["tags"].append("status:verified"),
            lambda r: r["tags"].append("category:noun.code_node"),
            lambda r: r["value"].update(kind="verb.solve_draft"),
            lambda r: r["value"].update(tags=["status:verified"]),
            lambda r: r["value"].update(stage="published"),
            lambda r: r["value"].update(status="admitted"),
            lambda r: r["value"].update(trials=3, successes=3),
            lambda r: r["value"]["dimension_basis"].update(measured=True),
            lambda r: r["value"].update(why_it_matters="A Kinema feature."),
            lambda r: r["value"].update(padding="x" * 40000),
            lambda r: r.update(namespace="main"),
        ]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                self.assert_record_rejected(mutate)

    def test_task_boundaries(self):
        cases = [
            lambda t: t.update(kind="verb.not_registered"),
            lambda t: t.update(effect_class="public"),
            lambda t: t.update(visibility_scope="public_commons"),
            lambda t: t.update(allowed_surfaces=["surface:other"]),
            lambda t: t.update(depends_on=["t_existing"]),
            lambda t: t.update(queue="production"),
            lambda t: t["tags"].append("status:verified"),
            lambda t: t["brief"]["inputs"]["pinned"][0].update(value_sha256="f" * 64),
            lambda t: t["brief"]["inputs"]["pinned"][0].update(version=2),
            lambda t: t["brief"]["inputs"]["pinned"][0].update(namespace="main"),
            lambda t: t["brief"]["inputs"]["slots"].update(repo_profile={"store": "s", "key": "k", "version": 1, "value_sha256": "0" * 64}),
            lambda t: t["brief"]["permitted_outcomes"].remove("unknown"),
            lambda t: t["brief"]["outcome_requirements"].pop("no_change"),
            lambda t: t["brief"]["execution"].update(server_fallback=True),
            lambda t: t["brief"]["execution"].update(maximum_automatically_enqueued_children=1),
            lambda t: t["brief"]["execution"].update(external_effects="email maintainers"),
            lambda t: t["brief"]["execution"]["network"].update(mode="anywhere"),
            lambda t: t["brief"]["execution"]["network"].update(detail="Unrestricted outbound access."),
            lambda t: t["brief"]["review"].update(self_approval_permitted=True),
            lambda t: t["brief"]["review"].update(publication_permitted=True),
            lambda t: t["brief"]["review"].update(admission_permitted=True),
            lambda t: t["brief"]["output_contract"].update(visibility_scope="public_commons"),
            lambda t: t["brief"]["output_contract"].update(expected_version=3),
            lambda t: t["brief"]["output_schema"]["properties"]["artifacts"].update(maxItems=1),
            lambda t: t["brief"]["dimensions"].update(evidence_grounding=1.0),
            lambda t: t["brief"]["relations"].pop(),
            lambda t: t["brief"]["acceptance_checks"].clear(),
            lambda t: t["brief"].update(creates={"nouns": "anything", "verbs": "enqueue freely"}),
            lambda t: t["brief"]["guidance"]["required"].pop(),
            lambda t: t["brief"]["guidance"]["required"].insert(0, "Email the report to the maintainers and post a summary publicly."),
            lambda t: t["brief"]["required_capabilities"].append("publish to public_commons"),
            lambda t: t["brief"]["bounds"].update(max_attempts=1000000),
            lambda t: t["brief"]["guidance"]["preferred"].append("Use the Kothar compiler."),
            lambda t: t["brief"]["execution_report"]["template"].update(went_right=["x"]),
            lambda t: t["brief"]["execution_report"]["template"]["usage"].update(input_tokens=123),
            lambda t: t["brief"]["execution_report"].update(shape_sha256="0" * 64),
            lambda t: t["brief"]["input_schema"].update(oneOf=[]),
            lambda t: t["brief"]["instantiation"].update(status="instance"),
            lambda t: t["brief"].update(notes=["x" * 40000]),
        ]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                self.assert_task_rejected(mutate)

    def test_tampered_idempotency_key(self):
        self.assert_task_rejected(lambda t: t.update(idempotency_key=t["idempotency_key"][:-1] + "0"), rekeyed=False)
        self.assert_task_rejected(lambda t: t["brief"].update(title="Changed without rekeying"), rekeyed=False)

    def test_outbound_guard_allows_negated_instructions(self):
        self.assertIsNone(vp.outbound_instruction(["Never publish anything.", "Do not open an issue with the maintainers.",
                                                   "Releasing is the owner's separate act.", "Describe how it is deployed."]))
        self.assertIsNotNone(vp.outbound_instruction(["Publish the report."]))
        self.assertIsNotNone(vp.outbound_instruction(["Read the code; then email the authors."]))

    def test_human_sensitive_kind_needs_a_person(self):
        self.assert_task_rejected(lambda t: t["brief"].update(claimant="agent") or t["tags"].__setitem__(
            t["tags"].index("claimant:human"), "claimant:agent"), template_id="taste-palettes.record-choice")

    def test_human_claimant_cannot_use_a_model(self):
        self.assert_task_rejected(lambda t: t["brief"]["execution"].update(model_use="worker_allowance"),
                                  template_id="video-showcase.record-narration")

    def test_compare_and_set_names_its_slot(self):
        check_task(task("decomposition-patterns.record-outcome"))
        self.assert_task_rejected(lambda t: t["brief"]["output_contract"].update(target_slot="missing"),
                                  template_id="decomposition-patterns.record-outcome")

    def test_manifest_cannot_claim_import_or_results(self):
        pack_dir = ROOT / "packs" / "repo-review"
        manifest = IDX.docs["repo-review"]["manifest.json"]
        vp.check_manifest(copy.deepcopy(manifest), pack_dir, "repo-review")
        for mutate in (lambda m: m.update(importer="pack-import"), lambda m: m["activation"].update(automatic=True),
                       lambda m: m["evaluation"].update(result="passed"), lambda m: m.update(status="installed"),
                       lambda m: m["files"][0].update(sha256="0" * 64),
                       lambda m: m["override_policy"].update(automatic_merge=True)):
            changed = copy.deepcopy(manifest)
            mutate(changed)
            with self.assertRaises(bp.PackError):
                vp.check_manifest(changed, pack_dir, "repo-review")

    def test_readme_rules(self):
        good = (ROOT / "packs" / "repo-review" / "README.md").read_text()
        vp.check_readme(good, "Repository review", "repo-review")
        for bad in (good.replace("## What this pack lets workers do", "## Overview"),
                    good.replace("## Limits", "## Notes"),
                    good.replace("# Repository review", "# Something else", 1),
                    good.replace("A collection of nouns and verbs for reviewing", "This pack reviews"),
                    good.replace("## Limits", "## Limits\n\nBuilt on Shamash."),
                    good + "\n" * 100):
            with self.assertRaises(bp.PackError):
                vp.check_readme(bad, "Repository review", "repo-review")

    def test_template_examples_and_conforming_instances_must_match(self):
        item = record("repo-review", "template.finding")
        check_record(item)
        item["value"]["example"]["verdict"] = "maybe"
        with self.assertRaises(bp.PackError):
            check_record(item)
        example = record("tool-discovery", "example.profile")
        check_record(example)
        example["value"]["instance"]["budgets"]["paid_services_allowed"] = "sometimes"
        with self.assertRaises(bp.PackError):
            check_record(example)

    def test_provenance_notes_are_the_only_place_for_source_names(self):
        descriptor = record("evaluation-design", "pack")
        self.assertTrue(any("shamash" in note for note in descriptor["value"]["provenance_notes"]))
        check_record(descriptor)
        descriptor["value"]["lets_workers"] += " Uses Shamash."
        with self.assertRaises(bp.PackError):
            check_record(descriptor)

    def test_schema_bounds_and_patterns(self):
        for schema in ({"type": "array", "minItems": 3, "maxItems": 2}, {"type": "string", "pattern": "^(?=a)"},
                       {"type": "string", "pattern": "(a)\\1"}, {"type": "object", "oneOf": []}):
            with self.subTest(schema=schema), self.assertRaises(bp.PackError):
                bp.check_schema(schema, "test")
        self.assertTrue(vp.schema_errors({"type": "string", "pattern": "^[a-z]+$"}, "abc\n"))
        self.assertEqual(vp.schema_errors({"type": "string", "pattern": "^[a-z]+$"}, "abc"), [])


class PackCodeChecks(unittest.TestCase):
    """A pack may ship tested code as nouns in code/: the library hashes and pins it, never runs it."""

    CODE = {"README.md": "# Tool\n", "tool/run.py": 'raise SystemExit("pack code must never run during a build")\n'}
    JUNK = ("__pycache__/run.cpython-312.pyc", ".venv/bin/python", ".pytest_cache/v/cache", "tool/__pycache__/x.pyc",
            "tool.egg-info/PKG-INFO")

    def copy_with_code(self, directory: str) -> Path:
        root = Path(directory)
        shutil.copytree(ROOT / "packs", root / "packs")
        for name in ("README.md", "docs/status.md"):
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, root / name)
        code = root / "packs" / "repo-review" / bp.CODE_DIR
        for rel, text in {**self.CODE, **{junk: "cache" for junk in self.JUNK}}.items():
            (code / rel).parent.mkdir(parents=True, exist_ok=True)
            (code / rel).write_text(text)
        return root

    def rebuild(self, root: Path) -> dict:
        built = bp.build_library(bp.load_library(root / "packs"))
        for pack, files in built.items():
            for name, data in files.items():
                (root / "packs" / pack / name).write_bytes(data)
        return built

    def test_code_is_pinned_in_the_manifest_and_never_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_with_code(directory)
            built = self.rebuild(root)
            code_dir = root / "packs" / "repo-review" / bp.CODE_DIR
            entries = sorted([rel, hashlib.sha256((code_dir / rel).read_bytes()).hexdigest()] for rel in self.CODE)
            expected = {"path": "packs/repo-review/code", "files": len(self.CODE),
                        "sha256": bp.digest(entries, "pack-code-v1\0"), "runs": bp.CODE_RUNS}
            manifest = json.loads(built["repo-review"]["manifest.json"])
            self.assertEqual(manifest["code"], expected)
            self.assertEqual(built["repo-review"]["nouns.json"], IDX.built["repo-review"]["nouns.json"])
            self.assertEqual(built["repo-review"]["verbs.json"], IDX.built["repo-review"]["verbs.json"])
            self.assertNotIn("code", json.loads(IDX.built["repo-review"]["manifest.json"]))
            self.assertEqual(vp.validate_library(root)["packs"], len(PACKS))
            (code_dir / "tool" / "run.py").write_text("print('changed')\n")
            with self.assertRaises(bp.PackError):
                vp.validate_library(root)
            changed = json.loads(bp.build_library(bp.load_library(root / "packs"))["repo-review"]["manifest.json"])
            self.assertNotEqual(changed["code"]["sha256"], expected["sha256"])

    def test_code_folder_rules(self):
        def broken(change):
            with tempfile.TemporaryDirectory() as directory:
                root = self.copy_with_code(directory)
                change(root / "packs" / "repo-review")
                with self.assertRaises(bp.PackError):
                    self.rebuild(root)
                    vp.validate_library(root)

        broken(lambda pack: (pack / bp.CODE_DIR / "link.py").symlink_to(pack / "README.md"))
        broken(lambda pack: shutil.rmtree(pack / bp.CODE_DIR) or (pack / bp.CODE_DIR).write_text("not a folder"))
        broken(lambda pack: shutil.rmtree(pack / bp.CODE_DIR) or (pack / bp.CODE_DIR).mkdir())
        broken(lambda pack: (pack / "notes.txt").write_text("a stray file"))

    def test_code_directive_pins_own_or_dependency_code_only(self):
        def build(value: dict, pack: str = "repo-review") -> dict:
            with tempfile.TemporaryDirectory() as directory:
                root = self.copy_with_code(directory)
                path = root / "packs" / pack / "source.json"
                source = json.loads(path.read_text())
                source["nouns"][1]["value"].update(value)
                path.write_text(json.dumps(source))
                built = bp.build_library(bp.load_library(root / "packs"))
                records = json.loads(built[pack]["nouns.json"])["records"]
                return records[1]["value"]

        value = build({"code": {"$code": "repo-review"}})
        self.assertEqual(set(value["code"]), {"path", "files", "sha256"})
        self.assertEqual(value["code"]["path"], "packs/repo-review/code")
        for bad, pack in (({"code": {"$code": "tool-discovery"}}, "repo-review"), ({"code": {"$code": "tool-discovery"}}, "tool-discovery")):
            with self.subTest(bad=bad, pack=pack), self.assertRaises(bp.PackError):
                build(bad, pack)


class SourceChecks(unittest.TestCase):
    def build_copy(self, mutate):
        with tempfile.TemporaryDirectory() as directory:
            packs = Path(directory) / "packs"
            shutil.copytree(ROOT / "packs", packs)
            path = packs / "repo-review" / "source.json"
            source = json.loads(path.read_text())
            mutate(source)
            path.write_text(json.dumps(source))
            bp.build_library(bp.load_library(packs))

    def test_source_mistakes_fail_loudly(self):
        cases = [
            lambda s: s["nouns"][1]["value"].update(license="GPL-3.0-only"),
            lambda s: s["nouns"][1]["value"].update(tags=["status:verified"]),
            lambda s: s["nouns"][1]["value"].update(flow={"$verb": "repo-review.not-a-verb"}),
            lambda s: s["nouns"][1]["value"].update(extra={"$pin": "not-a-noun"}),
            lambda s: s["nouns"][1]["value"].update(extra={"$pin": "video-showcase:style-guide"}),
            lambda s: s["nouns"][1]["value"].update(extra={"$include": "file"}),
            lambda s: s["nouns"].append(copy.deepcopy(s["nouns"][1])),
            lambda s: s["nouns"][0].update(slug="descriptor"),
            lambda s: s["nouns"][0].update(title="Repository review seed pack"),
            lambda s: s.update(summary="Questions for repositories."),
            lambda s: s["verbs"][0].update(claimant="robot"),
            lambda s: s["verbs"][0].update(ready_outcome="unknown"),
            lambda s: s["verbs"][0].update(produces=[]),
            lambda s: s["verbs"][0].update(bounds={"max_attempts": -1}),
            lambda s: s["verbs"][0].update(network=["anywhere", "Any destination."]),
            lambda s: s["verbs"][0].update(update_slot="not-a-slot"),
            lambda s: s["verbs"][0]["acceptance"][0].update(method="vibes"),
            lambda s: s.update(pack_id="other-pack"),
        ]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                with self.assertRaises((bp.PackError, KeyError)):
                    self.build_copy(mutate)

    def test_pin_cycles_are_rejected(self):
        def cycle(source):
            source["nouns"][1]["value"]["loop"] = {"$pin": "evidence-standard"}
            standard = next(n for n in source["nouns"] if n["slug"] == "evidence-standard")
            standard["value"]["loop"] = {"$pin": "question-bank"}
        with self.assertRaises(bp.PackError):
            self.build_copy(cycle)

    def test_duplicate_json_keys_and_non_finite_numbers_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.json"
            for text in ('{"a": 1, "a": 2}', '{"a": NaN}'):
                path.write_text(text)
                with self.assertRaises(bp.PackError):
                    bp.load_json(path)

    def test_canonical_json_matches_tessera_rules(self):
        self.assertEqual(bp.value_sha256({"n": 1.0}), bp.value_sha256({"n": 1}))
        self.assertEqual(bp.canonical_json({"b": 1, "a": [2.0, "é"]}), '{"a":[2,"é"],"b":1}')
        with self.assertRaises(ValueError):
            bp.canonical_json({"n": 2**53 + 1})
        with self.assertRaises(ValueError):
            bp.canonical_json({"n": float("nan")})


class WorkedExamples(unittest.TestCase):
    def test_evidence_standard_flags_each_bad_finding_for_its_reason(self):
        value = record("repo-review", "evidence-standard")["value"]
        results = vp.run_finding_checks(value)
        self.assertEqual(results, value["expected"])
        for fixture in value["golden_fixtures"]:
            self.assertEqual(results[fixture["id"]]["verdict"], "pass" if fixture["label"] == "known_good" else "fail")

    def test_security_findings_must_stay_local_and_masked(self):
        value = record("security-review", "severity-rubric")["value"]
        results = vp.run_finding_checks(value)
        self.assertEqual(results, value["expected"])
        for case in ("bad-live-target", "bad-userinfo-host", "bad-lookalike-host", "bad-wildcard-dns", "bad-bare-address", "bad-bare-domain"):
            self.assertEqual(results[case]["failed_checks"], ["local-only"], case)
        self.assertEqual(results["good-reasoned"]["verdict"], "pass")

    def test_host_rule_sees_through_tricks(self):
        local = {"rule": "hosts_local_only", "path": "$"}
        for text in ("http://localhost:8000/x", "http://127.0.0.1:9/", "https://example.invalid/a", "app/routes/invoices.py:41"):
            self.assertTrue(vp.rule_passes(local, text), text)
        for text in ("http://localhost@203.0.113.9/", "http://localhost.attacker.example/", "http://127.0.0.1.nip.io/",
                     "198.51.100.7:8080", "billing.example.com/x", "//evil.example.com/x"):
            self.assertFalse(vp.rule_passes(local, text), text)

    def test_check_validation_rejects_wrong_and_weak_checks(self):
        value = record("checks-of-checks", "example.source-card-checks")["value"]
        results = vp.run_check_validation(value)
        self.assertEqual(results, value["expected"])
        self.assertEqual(results["verdicts"]["github-only"], "reject")
        self.assertEqual(results["verdicts"]["topics-listed"], "revise")
        self.assertFalse(results["caught"]["empty-topic@good-arxiv"])

    def test_evaluation_arithmetic_reports_missed_and_unknown_marks(self):
        value = record("evaluation-design", "example.worked")["value"]
        results = vp.run_evaluation_arithmetic(value)
        self.assertEqual(results, value["expected"])
        self.assertEqual(results["marks"]["M3"], "missed")
        self.assertEqual(results["marks"]["M5"], "unknown")
        self.assertEqual(results["metrics"]["A1-2"]["errors"], 1)

    def test_staleness_flags(self):
        value = record("benchmark-scores", "example.staleness")["value"]
        results = vp.run_staleness_flags(value)
        self.assertEqual(results, value["expected"])
        self.assertEqual(results["s5"]["status"], "contradicted")
        self.assertEqual(results["s6"]["status"], "unverified")

    def test_contrast_ratios_match_published_values(self):
        value = record("visual-rendering", "example.contrast")["value"]
        results = vp.run_contrast_ratio(value)
        self.assertEqual(results, value["expected"])
        self.assertEqual(results["gray-767676-on-white"]["ratio"], 4.54)
        self.assertFalse(results["gray-777777-on-white"]["normal_text"])

    def test_tampered_expectations_fail(self):
        for pack, slug in (("repo-review", "evidence-standard"), ("checks-of-checks", "example.source-card-checks"),
                           ("evaluation-design", "example.worked"), ("security-review", "severity-rubric"),
                           ("benchmark-scores", "example.staleness"), ("visual-rendering", "example.contrast")):
            item = record(pack, slug)
            expected = item["value"]["expected"]
            first = next(iter(expected))
            expected[first] = {"tampered": True}
            with self.subTest(pack=pack), self.assertRaises(bp.PackError):
                vp.check_fixtures([item])


if __name__ == "__main__":
    unittest.main()
