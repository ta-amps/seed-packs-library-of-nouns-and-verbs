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
from unittest import mock

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


# A made-up product name. Inside synthetic_name() it joins the hashed surface-name list, so the
# negative checks below can name a product without this repository naming a real one.
SYNTHETIC_NAME = "acme"


def synthetic_name():
    digest = hashlib.sha256(SYNTHETIC_NAME.encode()).hexdigest()
    return mock.patch.object(vp, "SURFACE_NAME_HASHES", vp.SURFACE_NAME_HASHES | {digest})


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
        self.assertEqual(summary["worked_examples"], 19)
        self.assertTrue(summary["offline_only"])
        self.assertIsNone(summary["live_evaluation"])

    def test_required_packs_present(self):
        for pack in ("repo-review", "video-showcase", "tool-discovery", "evaluation-design", "checks-of-checks",
                     "decomposition-patterns", "taste-palettes", "harness-onboarding-e2e", "security-review",
                     "cost-optimization", "docs-improvement", "benchmark-scores", "visual-rendering",
                     "public-good-kits", "freshness-checks", "findings-to-fixes"):
            self.assertIn(pack, PACKS)

    def test_packs_are_plain_english_collections(self):
        for pack in PACKS:
            source = IDX.lib.sources[pack]
            self.assertTrue(source["summary"].startswith(bp.PACK_PHRASE), pack)
            descriptor = record(pack, "pack")
            self.assertTrue(descriptor["value"]["title"].startswith(bp.PACK_PHRASE), pack)
            readme = (ROOT / "packs" / pack / "README.md").read_text()
            self.assertFalse(vp.surface_name_in(readme), pack)

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

    def test_findings_to_fixes_keeps_failures_and_independent_checks(self):
        tasks = {t["brief"]["template_id"].split(".", 1)[1]: t["brief"] for t in IDX.docs["findings-to-fixes"]["verbs.json"]["tasks"]}
        self.assertEqual(set(tasks), {"record-finding", "reproduce", "triage", "propose-fix", "fix", "verify-fix",
                                      "add-regression-guard", "close", "publish-finding", "review-patterns"})
        for slug in ("triage", "close"):
            contract = tasks[slug]["output_contract"]
            self.assertEqual((contract["write_mode"], contract["target_slot"]), ("compare_and_set", "finding"), slug)
        for slug in set(tasks) - {"triage", "close"}:
            self.assertEqual(tasks[slug]["output_contract"]["write_mode"], "create_only", slug)
        self.assertEqual(tasks["verify-fix"]["review"]["required"], "distinct_reviewer")
        self.assertEqual(tasks["close"]["execution"]["model_use"], "none")
        produced = {item["template"]["key"] for item in tasks["propose-fix"]["output_contract"]["produces"]}
        self.assertIn(key("taste-palettes", "template.brief"), produced)
        self.assertIn(key("checks-of-checks", "method"), {pin["key"] for pin in tasks["add-regression-guard"]["inputs"]["pinned"]})
        self.assertLessEqual({"prior-art-and-alternatives.survey-existing", "prior-art-and-alternatives.research-alternatives"},
                             set(tasks["propose-fix"]["follows_templates"]))
        for brief in tasks.values():
            self.assertFalse(brief["review"]["publication_permitted"])
            self.assertEqual(brief["execution"]["external_effects"], "none")

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
            lambda r: r["value"].update(why_it_matters="An Acme feature."),
            lambda r: r["value"].update(padding="x" * 40000),
            lambda r: r.update(namespace="main"),
        ]
        with synthetic_name():
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
            lambda t: t["brief"]["guidance"]["preferred"].append("Use the Acme compiler."),
            lambda t: t["brief"]["execution_report"]["template"].update(went_right=["x"]),
            lambda t: t["brief"]["execution_report"]["template"]["usage"].update(input_tokens=123),
            lambda t: t["brief"]["execution_report"].update(shape_sha256="0" * 64),
            lambda t: t["brief"]["input_schema"].update(oneOf=[]),
            lambda t: t["brief"]["instantiation"].update(status="instance"),
            lambda t: t["brief"].update(notes=["x" * 40000]),
        ]
        with synthetic_name():
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
                    good.replace("## Limits", "## Limits\n\nBuilt on Acme."),
                    good + "\n" * 100):
            with self.assertRaises(bp.PackError), synthetic_name():
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
        self.assertTrue(any(vp.surface_name_in(note) for note in descriptor["value"]["provenance_notes"]))
        check_record(descriptor)
        descriptor["value"]["lets_workers"] += " Uses Acme."
        with self.assertRaises(bp.PackError), synthetic_name():
            check_record(descriptor)

    def test_surface_names_are_stored_only_as_hashes(self):
        self.assertEqual(len(vp.SURFACE_NAME_HASHES), 6)
        # The three earlier product names of packs that moved into this library.
        moved = {
            "d488476689bd8ff0424956c989ae7508815f2821f9524dfd3ea5aea931911978",
            "4322a6b237d4d0f47990bad6edf90913cd88d2a1a6a9698a756b73e4dfd69329",
            "9410a442dd664c9234966c5ecc0ff595431749474bc67b7e2ce5ccaaed7793ec",
        }
        self.assertLessEqual(moved, vp.SURFACE_NAME_HASHES)
        for path in ("scripts/validate_packs.py", "scripts/build_packs.py", "tests/test_packs.py"):
            self.assertFalse(vp.surface_name_in((ROOT / path).read_text(encoding="utf-8")), path)
        self.assertFalse(vp.surface_name_in("Made with Acme."))
        with synthetic_name():
            for text in ("Made with Acme.", "ACME tools", "acme-labs", "the acme_tool helper"):
                self.assertTrue(vp.surface_name_in(text), text)
            for text in ("Acmeish", "academy"):
                self.assertFalse(vp.surface_name_in(text), text)

    def test_moved_from_is_one_provenance_field_that_nothing_copies(self):
        source = IDX.lib.sources["video-motion"]
        moved = source["moved_from"]
        self.assertEqual(set(moved), {"repository", "commit"})
        for name, data in IDX.built["video-motion"].items():
            self.assertNotIn(moved["repository"].encode(), data, name)
            self.assertNotIn(moved["commit"].encode(), data, name)
        good = {"repository": "https://github.com/example-org/example-repo", "commit": "0123456789abcdef0123456789abcdef01234567"}
        for bad in ({**good, "commit": "0123456"}, {**good, "repository": "http://example.invalid/x"},
                    {**good, "note": "extra"}, {"repository": good["repository"]}, "github.com/example-org/x"):
            changed = copy.deepcopy(source)
            changed["moved_from"] = bad
            with self.subTest(bad=bad), self.assertRaises(bp.PackError):
                bp.check_source("video-motion", changed)
        changed = copy.deepcopy(source)
        changed["moved_from"] = good
        bp.check_source("video-motion", changed)

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

    def test_code_folder_ignores_what_its_gitignore_ignores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_with_code(directory)
            code_dir = root / "packs" / "repo-review" / bp.CODE_DIR
            before = bp.code_digest(root / "packs" / "repo-review")
            (code_dir / ".gitignore").write_text("# generated\n/generated/\n*.log\nout/\n")
            kept = {"README.md", "tool/run.py", ".gitignore", "sub/generated/keep.py"}
            for rel in ("generated/data.json", "run.log", "sub/out/frame.png", "sub/generated/keep.py"):
                (code_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (code_dir / rel).write_text("x")
            pinned = {path.relative_to(code_dir).as_posix() for path in bp.code_files(root / "packs" / "repo-review")}
            self.assertEqual(pinned, kept)
            self.assertNotEqual(bp.code_digest(root / "packs" / "repo-review")["sha256"], before["sha256"])
            (code_dir / ".gitignore").write_text("!keep.py\n")
            with self.assertRaises(bp.PackError):
                bp.code_files(root / "packs" / "repo-review")

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

    def test_finding_record_checks_flag_each_bad_finding_for_its_reason(self):
        value = record("findings-to-fixes", "record-checks")["value"]
        results = vp.run_finding_checks(value)
        self.assertEqual(results, value["expected"])
        for fixture in value["golden_fixtures"]:
            if fixture["label"] == "known_good":
                self.assertEqual(results[fixture["id"]], {"verdict": "pass", "failed_checks": []}, fixture["id"])
            else:
                self.assertEqual(results[fixture["id"]]["failed_checks"], [fixture["fails"]], fixture["id"])
        caught = {c for f in value["golden_fixtures"] if f["label"] == "known_bad" for c in results[f["id"]]["failed_checks"]}
        self.assertEqual(caught, {check["id"] for check in value["deterministic_checks"]})

    def test_recurring_work_record_checks_flag_each_bad_example_for_its_reason(self):
        for pack, slug in (("direction-to-work", "direction-checks"), ("status-and-handoff", "status-checks"),
                           ("release-and-verify", "release-checks"), ("rename-and-relink", "rename-checks")):
            value = record(pack, slug)["value"]
            results = vp.run_finding_checks(value)
            self.assertEqual(results, value["expected"], pack)
            for fixture in value["golden_fixtures"]:
                if fixture["label"] == "known_good":
                    self.assertEqual(results[fixture["id"]], {"verdict": "pass", "failed_checks": []}, fixture["id"])
                    self.assertEqual(vp.schema_errors(value["finding_schema"], fixture["finding"]), [], fixture["id"])
                else:
                    self.assertEqual(results[fixture["id"]]["failed_checks"], [fixture["fails"]], fixture["id"])
            caught = {c for f in value["golden_fixtures"] if f["label"] == "known_bad" for c in results[f["id"]]["failed_checks"]}
            self.assertEqual(caught, {check["id"] for check in value["deterministic_checks"]}, pack)

    def test_real_findings_are_public_and_rechecked(self):
        schema = record("findings-to-fixes", "template.finding")["value"]["schema"]
        fixtures = record("findings-to-fixes", "record-checks")["value"]["golden_fixtures"]
        good = {f["finding"]["id"]: f["finding"] for f in fixtures if f["label"] == "known_good"}
        examples = [r["value"] for r in IDX.docs["findings-to-fixes"]["nouns.json"]["records"]
                    if r["value"]["role"] == "example" and r["value"]["conforms_to"]["key"] == key("findings-to-fixes", "template.finding")]
        self.assertEqual(len(examples), 8)
        for example in examples:
            instance = example["instance"]
            self.assertTrue(instance["public"], instance["id"])
            self.assertEqual(good[instance["id"]], instance)
        for finding in good.values():
            self.assertEqual(vp.schema_errors(schema, finding), [], finding["id"])

    def test_tampered_expectations_fail(self):
        for pack, slug in (("repo-review", "evidence-standard"), ("checks-of-checks", "example.source-card-checks"),
                           ("evaluation-design", "example.worked"), ("security-review", "severity-rubric"),
                           ("benchmark-scores", "example.staleness"), ("visual-rendering", "example.contrast"),
                           ("findings-to-fixes", "record-checks")):
            item = record(pack, slug)
            expected = item["value"]["expected"]
            first = next(iter(expected))
            expected[first] = {"tampered": True}
            with self.subTest(pack=pack), self.assertRaises(bp.PackError):
                vp.check_fixtures([item])


class TopicPackExamples(unittest.TestCase):
    """The topic packs of October 30: their guardrail checks, and the worked-example arithmetic of the three packs
    that ship no code. The video and tuning packs recompute their own examples in their code's CI jobs."""

    FIXTURES = (("voice-narration", "narration-checks"), ("narrated-explainer-video", "release-checks"),
                ("continuous-tuning", "decision-checks"), ("public-company-research", "brief-checks"),
                ("deep-research-report", "report-checks"))

    @staticmethod
    def instance(pack: str, slug: str):
        return record(pack, slug)["value"]["instance"]

    def test_guardrail_checks_flag_each_bad_example_for_its_reason(self):
        for pack, slug in self.FIXTURES:
            item = record(pack, slug)
            value = item["value"]
            results = vp.run_finding_checks(value)
            self.assertEqual(results, value["expected"], pack)
            for fixture in value["golden_fixtures"]:
                if fixture["label"] == "known_good":
                    self.assertEqual(results[fixture["id"]], {"verdict": "pass", "failed_checks": []}, fixture["id"])
                    self.assertEqual(vp.schema_errors(value["finding_schema"], fixture["finding"]), [], fixture["id"])
                else:
                    self.assertEqual(results[fixture["id"]]["failed_checks"], [fixture["fails"]], fixture["id"])
            caught = {c for f in value["golden_fixtures"] if f["label"] == "known_bad" for c in results[f["id"]]["failed_checks"]}
            self.assertEqual(caught, {check["id"] for check in value["deterministic_checks"]}, pack)
            first = next(iter(value["expected"]))
            value["expected"][first] = {"tampered": True}
            with self.assertRaises(bp.PackError):
                vp.check_fixtures([item])

    def test_voice_pace_take_choice_and_placements_recompute(self):
        import re

        pack = "voice-narration"
        script = {line["line"]: line for line in self.instance(pack, "example.narration-script")["lines"]}
        target = self.instance(pack, "example.narration-script")["target_wpm"]
        measured = {row["line"]: row["takes"] for row in self.instance(pack, "example.line-measurements")["lines"]}
        choice = self.instance(pack, "example.take-choice")

        def words(text: str) -> int:
            return sum(1 for token in text.split() if any(ch.isalnum() for ch in token))

        chosen = {}
        for line, takes in measured.items():
            for take in takes:
                if take["speech_s"] is not None:
                    span = take["speech_s"][1] - take["speech_s"][0]
                    self.assertEqual(take["wpm"], round(words(script[line]["text"]) / (span / 60), 1), (line, take["take"]))
            clean = [t for t in takes if t["valid"] and t["end_of_speech"] and t["full_scale_samples"] == 0]
            best = min(clean, key=lambda t: (t["cer"], abs(t["wpm"] - target), t["take"]))
            chosen[line] = best
        self.assertEqual({c["line"]: c["take"] for c in choice["chosen"]}, {k: v["take"] for k, v in chosen.items()})
        listed = {(c["line"], c["take"]) for c in choice["chosen"]} | {(c["line"], c["take"]) for c in choice["not_chosen"]}
        self.assertEqual(listed, {(line, t["take"]) for line, takes in measured.items() for t in takes})
        lufs = [t["integrated_lufs"] for t in chosen.values()]
        self.assertEqual(choice["loudness_spread_lu"], round(max(lufs) - min(lufs), 1))
        track = self.instance(pack, "example.narration-track")
        for placed in track["placements"]:
            take = chosen[placed["line"]]
            start = placed["start_s"]
            self.assertEqual(placed["take"], take["take"])
            self.assertEqual(placed["text"], script[placed["line"]]["text"])
            self.assertEqual(placed["end_s"], round(start + take["duration_s"], 3))
            self.assertEqual(placed["speech_s"], [round(start + x, 3) for x in take["speech_s"]])
            self.assertEqual(placed["pauses_s"], [[round(start + a, 3), round(start + b, 3)] for a, b in take["pauses_s"]])
        self.assertIn("AI-generated voice", track["disclosure"])
        unmarked = re.compile(r"\[([^\]]+)\]\(/[^)]*/\)")
        for line in self.instance(pack, "example.synthesis-log")["lines"]:
            self.assertEqual(unmarked.sub(r"\1", line["text_sent"]), script[line["line"]]["text"])
        for entry in self.instance(pack, "example.lexicon")["entries"]:
            self.assertFalse(entry["confirmed_by_ear"], "only a person's listening check confirms an entry")
            self.assertTrue(any(entry["grapheme"] in line["text"] for line in script.values()), entry["grapheme"])

    def test_company_metrics_comparisons_dates_and_citations_recompute(self):
        import re
        from datetime import date, timedelta

        pack = "public-company-research"
        metrics = self.instance(pack, "example.metric-table")
        values = {f["fact_id"]: f["value"] for f in metrics["facts"]}
        for item in metrics["derived"]:
            a, b = (values[name] for name in item["inputs"])
            expected = a - b if " minus " in item["formula"] else round(a / b * 100, 1)
            self.assertEqual(item["value"], expected, item["fact_id"])
            values[item["fact_id"]] = item["value"]
        for fact in metrics["facts"]:
            self.assertTrue(fact["cik"].startswith("X") and fact["accession"].startswith("X"), "synthetic identifiers")
        comparisons = self.instance(pack, "example.comparison")["comparisons"]
        for row in comparisons:
            self.assertEqual((row["from_value"], row["to_value"]), (values[row["from_fact"]], values[row["to_fact"]]))
            self.assertEqual(row["change"], row["to_value"] - row["from_value"])
            self.assertEqual(row["percent_change"], round(row["change"] / row["from_value"] * 100, 1))
        events = {e["id"]: e for e in self.instance(pack, "example.catalyst-calendar")["events"]}
        self.assertEqual(events["e-q3-10q"]["date"], (date(2026, 9, 30) + timedelta(days=40)).isoformat())
        self.assertEqual(events["e-fy-10k"]["date"], (date(2026, 12, 31) + timedelta(days=75)).isoformat())
        for event in events.values():
            self.assertEqual(event["status"] == "due_by_rule", "rule" in event, event["id"])
        risks = {r["id"] for r in self.instance(pack, "example.risk-factors")["factors"]}
        brief = self.instance(pack, "example.cited-brief")
        known = set(values) | {r["id"] for r in comparisons} | risks | set(events)
        for point in brief["points"]:
            self.assertLessEqual(set(point["cites"]), known, point["text"])
        for figure in brief["figures"]:
            self.assertEqual(figure["value"], values[figure["fact_id"]], figure["label"])
        amounts = sum(len(re.findall(r"\d+\.\d+%?", point["text"])) for point in brief["points"])
        self.assertEqual(self.instance(pack, "example.brief-review")["numbers_checked"], len(brief["figures"]) + amounts)

    def test_research_quotes_flow_and_citations_recheck(self):
        pack = "deep-research-report"
        sources = {s["id"]: s for s in record(pack, "example.sources")["value"]["sources"]}
        log = {s["id"]: s for s in self.instance(pack, "example.source-log")["sources"]}
        for source_id, source in sources.items():
            self.assertEqual(source["text_sha256"], hashlib.sha256(source["text"].encode()).hexdigest())
            self.assertEqual(log[source_id]["text_sha256"], source["text_sha256"])
        claims = {c["id"]: c for c in self.instance(pack, "example.claim-extract")["claims"]}
        for claim in claims.values():
            text, quote = sources[claim["source_id"]]["text"], claim["quote"]
            self.assertEqual(text.count(quote["exact"]), 1, claim["id"])
            self.assertEqual(text.count(quote["prefix"] + quote["exact"] + quote["suffix"]), 1, claim["id"])
        screening = self.instance(pack, "example.screening-log")
        flow = screening["flow"]
        self.assertEqual(flow["identified"], flow["duplicates"] + flow["screened"])
        self.assertEqual(flow["screened"], flow["excluded_title"] + flow["assessed"])
        self.assertEqual(flow["assessed"], flow["excluded_full_text"] + flow["included"])
        included = {d["source_id"] for d in screening["decisions"] if d["decision"] == "include"}
        self.assertEqual(len(included), flow["included"])
        self.assertEqual({c["source_id"] for c in claims.values()}, included)
        for d in screening["decisions"]:
            self.assertEqual(d["decision"] == "exclude", "reason" in d, d["source_id"])
            if d.get("reason") == "retracted":
                self.assertTrue(log[d["source_id"]]["retracted"])
        synthesis = self.instance(pack, "example.synthesis")
        report = self.instance(pack, "example.report")
        for sentence in synthesis["sentences"] + report["findings"]:
            if sentence["label"] in ("source", "synthesis"):
                self.assertTrue(sentence["claims"] and set(sentence["claims"]) <= set(claims), sentence["text"])
        contradicting = {c for c, v in claims.items() if v["direction"] == "contradicts"}
        mentioned = {c for s in synthesis["sentences"] for c in s["claims"]} | {
            c for row in synthesis["contradictions"] for c in row["claims"]}
        self.assertLessEqual(contradicting, mentioned)
        self.assertTrue(any(q["purpose"] == "counter" for q in self.instance(pack, "example.search-plan")["queries"]))
        self.assertEqual(report["method"]["flow"], {"identified": flow["identified"], "included": flow["included"]})
        self.assertEqual(self.instance(pack, "example.adversarial-review")["quotes_checked"], len(claims))


class SecondRoundPackExamples(unittest.TestCase):
    """The options chain, checked data and screenshot design review packs of October 30: their record checks,
    guardrails defined once, cross-checks between their example nouns, and the screenshot review's measured checks
    recomputed from its layout facts. The options and data packs recompute their worked examples in their code's
    CI jobs."""

    FIXTURES = (("options-chain-review", "review-checks"), ("checked-data-analysis", "findings-checks"),
                ("screenshot-design-review", "design-finding-checks"))

    @staticmethod
    def instance(pack: str, slug: str):
        return record(pack, slug)["value"]["instance"]

    def test_record_checks_flag_each_bad_example_for_its_reason(self):
        finding_schema = record("findings-to-fixes", "template.finding")["value"]["schema"]
        for pack, slug in self.FIXTURES:
            item = record(pack, slug)
            value = item["value"]
            results = vp.run_finding_checks(value)
            self.assertEqual(results, value["expected"], pack)
            for fixture in value["golden_fixtures"]:
                if fixture["label"] == "known_good":
                    self.assertEqual(results[fixture["id"]], {"verdict": "pass", "failed_checks": []}, fixture["id"])
                    schema = value.get("finding_schema", finding_schema)
                    self.assertEqual(vp.schema_errors(schema, fixture["finding"]), [], fixture["id"])
                else:
                    self.assertEqual(results[fixture["id"]]["failed_checks"], [fixture["fails"]], fixture["id"])
            caught = {c for f in value["golden_fixtures"] if f["label"] == "known_bad" for c in results[f["id"]]["failed_checks"]}
            self.assertEqual(caught, {check["id"] for check in value["deterministic_checks"]}, pack)
            first = next(iter(value["expected"]))
            value["expected"][first] = {"tampered": True}
            with self.assertRaises(bp.PackError):
                vp.check_fixtures([item])

    def test_design_findings_are_findings_to_fixes_findings(self):
        checks = record("findings-to-fixes", "record-checks")["value"]["deterministic_checks"]
        goods = [f["finding"] for f in record("screenshot-design-review", "design-finding-checks")["value"]["golden_fixtures"]
                 if f["label"] == "known_good"]
        self.assertEqual(len(goods), 7)
        for finding in goods:
            self.assertEqual(vp.failing_checks(checks, finding), [], finding["id"])
        self.assertEqual(self.instance("screenshot-design-review", "example.finding"), goods[0])

    def test_guardrails_are_defined_once_and_the_financial_ones_are_pinned(self):
        rules = [r["value"]["rule"] for p in PACKS for r in IDX.docs[p]["nouns.json"]["records"] if r["value"]["role"] == "guardrail"]
        self.assertEqual(len(rules), len(set(rules)), "a guardrail's rule is written once in the library")
        own = {r["key"] for r in IDX.docs["options-chain-review"]["nouns.json"]["records"] if r["value"]["role"] == "guardrail"}
        self.assertEqual(own, {key("options-chain-review", "guardrail.timestamp-every-number")})
        pinned = {pin["key"] for pin in record("options-chain-review", "pack")["value"]["guardrails"]}
        for pack, slug in (("public-company-research", "guardrail.not-financial-advice"),
                           ("public-company-research", "guardrail.no-trades-or-orders"),
                           ("public-company-research", "guardrail.cite-every-number"),
                           ("public-company-research", "guardrail.respect-provider-terms"),
                           ("policy-and-law-watch", "guardrail.person-decides")):
            self.assertIn(key(pack, slug), pinned)

    def test_options_verbs_never_reach_a_brokerage_or_price_an_order(self):
        for item in IDX.docs["options-chain-review"]["verbs.json"]["tasks"]:
            brief = item["brief"]
            network = brief["execution"]["network"]
            self.assertIn(network["mode"], {"none", "read_only"}, brief["template_id"])
            if network["mode"] == "read_only":
                self.assertIn("never a brokerage", network["detail"])
            self.assertFalse({name for name in brief["output_schema"]["properties"] if "order" in name or "trade" in name})
        snapshot = self.instance("options-chain-review", "example.chain-snapshot")
        underlying = snapshot["underlying"]["symbol"]
        self.assertTrue(underlying.endswith(".X"))
        self.assertTrue(all(c["symbol"].startswith(underlying + " ") for c in snapshot["contracts"]))
        self.assertIs(snapshot["source"]["brokerage_connection"], False)
        review = self.instance("options-chain-review", "example.chain-review")
        self.assertEqual((review["notice"], review["stale_quotes_used"]), ("Not financial advice", False))

    def test_data_findings_resolve_to_their_query_results(self):
        import re

        pack = "checked-data-analysis"
        dataset = record(pack, "example.dataset")["value"]
        self.assertEqual(dataset["sha256"], hashlib.sha256(dataset["text"].encode("utf-8")).hexdigest())
        self.assertEqual(self.instance(pack, "example.analysis-request")["dataset"]["sha256"], dataset["sha256"])
        results = {r["id"]: r for r in self.instance(pack, "example.query-results")["results"]}
        findings = self.instance(pack, "example.findings")
        self.assertEqual(findings["dataset_sha256"], dataset["sha256"])
        for finding in findings["findings"]:
            for number in finding["numbers"]:
                self.assertEqual(results[number["query"]]["result"][number["row"]][number["column"]], number["value"])
        for exclusion in findings["exclusions"]:
            self.assertEqual(results[exclusion["query"]]["excluded_by_filter"], exclusion["excluded"])
        for chart in self.instance(pack, "example.chart-specs")["charts"]:
            self.assertEqual(chart["data"]["values"], results[chart["usermeta"]["query"]]["result"])
        addresses = set(re.findall(r"[a-z-]+@example\.invalid", dataset["text"]))
        self.assertTrue(addresses)
        for item in IDX.docs[pack]["nouns.json"]["records"]:
            if item["key"] != key(pack, "example.dataset"):
                for address in addresses:
                    self.assertNotIn(address, json.dumps(item["value"]), item["key"])

    def test_screenshot_checks_recompute_from_the_layout(self):
        from collections import Counter

        pack = "screenshot-design-review"

        def luminance(color):
            channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast(a, b):
            high, low = sorted((luminance(a), luminance(b)), reverse=True)
            return (high + 0.05) / (low + 0.05)

        example = record("visual-rendering", "example.contrast")["value"]
        for pair in example["pairs"]:
            self.assertEqual(round(contrast(pair["foreground"], pair["background"]), 2), example["expected"][pair["id"]]["ratio"])

        def failures(layout, request):
            t = request["rules"]
            out = []
            for cell in layout["cells"]:
                elements = {e["selector"]: e for e in cell["elements"]}

                def add(rule, e, measured, threshold, cell=cell):
                    out.append({"cell": cell["id"], "rule": rule, "selector": e["selector"], "box": e["box"],
                                "measured": measured, "threshold": threshold})

                for e in cell["elements"]:
                    size = e.get("font_size_px")
                    if size is not None and size < t["min_text_px"]:
                        add("text-size", e, f"{size} px", f"{t['min_text_px']} px")
                    if "color" in e:
                        large = size >= t["large_text_px"] or (size >= t["large_bold_px"] and e["font_weight"] >= t["bold_weight"])
                        need = t["contrast_large"] if large else t["contrast_normal"]
                        ratio = contrast(e["color"], e["background"])
                        if ratio < need:
                            add("contrast", e, f"{ratio:.2f}:1", f"{need:g}:1")
                    if e.get("clips_overflow") and e["scroll_width_px"] > e["client_width_px"] + 1:
                        add("cropping", e, f"content {e['scroll_width_px']} px wide in {e['client_width_px']} px", "content fits its box")
                    if e["role"] == "image" and (not e["loaded"] or e["natural_width_px"] == 0):
                        add("broken-asset", e, f"not loaded, natural width {e['natural_width_px']} px", "loaded, natural width above 0")
                if cell["document"]["scroll_width_px"] > cell["width_px"]:
                    widest = max(cell["elements"], key=lambda e: (e["box"][0] + e["box"][2], e["selector"]))
                    add("overflow", widest, f"page {cell['document']['scroll_width_px']} px wide at a {cell['width_px']} px viewport",
                        "no sideways scrolling")
                for group in request["alignment_groups"]:
                    edges = Counter(elements[m]["box"][0] for m in group["members"])
                    common = min(edges, key=lambda edge: (-edges[edge], edge))
                    for m in group["members"]:
                        if elements[m]["box"][0] != common:
                            add("alignment", elements[m], f"{abs(elements[m]['box'][0] - common)} px off the group's left edge", "0 px")
                for stack in request["stacks"]:
                    members = sorted((elements[m] for m in stack["members"]), key=lambda e: e["box"][1])
                    for above, below in zip(members, members[1:]):
                        gap = below["box"][1] - above["box"][1] - above["box"][3]
                        if gap % t["spacing_unit_px"]:
                            add("spacing", below, f"gap {gap} px after {above['selector']}", f"multiples of {t['spacing_unit_px']} px")
            return out

        request = self.instance(pack, "example.review-request")
        rule_order = ("text-size", "contrast", "cropping", "broken-asset", "overflow", "alignment", "spacing")
        reports = {}
        for when, layout_slug, report_slug, captures_slug in (
                ("before", "example.layout-facts", "example.check-report", "example.capture-set"),
                ("after", "example.layout-facts-after", "example.check-report-after", "example.capture-set-after")):
            layout, report = self.instance(pack, layout_slug), self.instance(pack, report_slug)
            found = failures(layout, request)
            key_of = lambda f: (f["cell"], rule_order.index(f["rule"]), f["selector"])  # noqa: E731
            self.assertEqual(sorted(found, key=key_of), sorted(report["failures"], key=key_of), when)
            self.assertEqual(report["passed"], not found)
            self.assertTrue(report["contrast_example_reproduced"])
            self.assertEqual({(c["cell"], c["rule"]) for c in report["counts"]},
                             {(cell["id"], rule) for cell in layout["cells"] for rule in rule_order})
            for count in report["counts"]:
                self.assertEqual(count["failed"], sum(1 for f in found if (f["cell"], f["rule"]) == (count["cell"], count["rule"])))
            captures = {c["cell"]: c for c in self.instance(pack, captures_slug)["captures"]}
            self.assertEqual(set(captures), {cell["id"] for cell in layout["cells"]})
            for cell in layout["cells"]:
                self.assertEqual(captures[cell["id"]]["layout_facts_sha256"], bp.value_sha256(cell))
            reports[when] = (found, captures, bp.value_sha256(report))
        before, shots, digest = reports["before"]
        self.assertEqual(Counter(f["rule"] for f in before), Counter({"text-size": 6, "spacing": 6, "broken-asset": 6,
                                                                       "alignment": 4, "contrast": 3, "cropping": 2, "overflow": 2}))
        self.assertEqual([(f["cell"], f["rule"]) for f in reports["after"][0]], [("1440-light", "alignment"), ("1440-dark", "alignment")])
        groups = {}
        for f in before:
            groups.setdefault((f["rule"], f["selector"]), []).append(f)
        findings = [f["finding"] for f in record(pack, "design-finding-checks")["value"]["golden_fixtures"] if f["label"] == "known_good"]
        self.assertEqual(len(findings), len(groups))
        for finding in findings:
            measurement = next(e for e in finding["evidence"] if e["kind"] == "measurement")
            rule, selector = measurement["detail"].split(":")[0][len("rule "):], measurement["location"][len("selector "):]
            rows = groups[(rule, selector)]
            self.assertEqual(measurement["detail"], f"rule {rule}: measured {rows[0]['measured']}; threshold {rows[0]['threshold']}")
            self.assertEqual(measurement["sha256"], digest)
            screens = [e for e in finding["evidence"] if e["kind"] == "screenshot"]
            self.assertEqual([s["location"] for s in screens],
                             [f"cell {r['cell']}; box {r['box'][0]},{r['box'][1]},{r['box'][2]}x{r['box'][3]} css px" for r in rows])
            self.assertEqual([s["sha256"] for s in screens], [shots[r["cell"]]["screenshot_sha256"] for r in rows])
            self.assertTrue(finding["fingerprint"].startswith(f"design_flaw/signup-page/{rule}-"))
        after = {(f["rule"], f["selector"]) for f in reports["after"][0]}
        _, shots_after, digest_after = reports["after"]
        for slug, group in (("example.verification-contrast", ("contrast", "a.terms-link")),
                            ("example.verification-alignment", ("alignment", ".card:nth-child(2)"))):
            check = self.instance(pack, slug)
            self.assertEqual(check["verdict"], "fix_failed" if group in after else "fix_verified", slug)
            self.assertEqual([run["shows_problem"] for run in check["runs"]], [True, group in after])
            self.assertEqual(check["runs"][1]["evidence_sha256"], [digest_after])
            self.assertEqual([s["sha256"] for s in check["screenshots"]],
                             [shots_after[r["cell"]]["screenshot_sha256"] for r in groups[group]])
        description = self.instance(pack, "example.screenshot-description")
        self.assertIsNone(description["css_width"])
        self.assertEqual(set(description["proposed_cells"]), {c["id"] for c in self.instance(pack, "example.capture-plan")["cells"]})


if __name__ == "__main__":
    unittest.main()
