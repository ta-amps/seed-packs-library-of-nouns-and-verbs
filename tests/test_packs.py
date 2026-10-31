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
        self.assertEqual(summary["worked_examples"], 45)
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
        self.assertEqual({r["value"]["pack"] for r in schedules}, {"tool-discovery", "benchmark-scores", "freshness-checks", "agent-harness-feeds"})
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


class CorpusPackExamples(unittest.TestCase):
    """The five packs of October 30 drawn from recurring work across design notes, agent sessions and project
    folders: their record checks, and the arithmetic their worked examples state."""

    FIXTURES = (("atomic-step-contract", "step-checks"), ("unattended-run-record", "run-checks"),
                ("retrieval-triggers-and-reuse", "reuse-checks"), ("file-triage-at-scale", "triage-checks"),
                ("measured-claims", "claim-checks"))

    @staticmethod
    def instance(pack: str, slug: str):
        return record(pack, slug)["value"]["instance"]

    def test_record_checks_flag_each_bad_example_for_its_reason(self):
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
            template = record(pack, next(n["slug"] for n in IDX.lib.sources[pack]["nouns"]
                                         if n["role"] == "template" and n["value"]["schema"] == value["finding_schema"]))
            self.assertEqual(template["value"]["role"], "template", pack)
            first = next(iter(value["expected"]))
            value["expected"][first] = {"tampered": True}
            with self.assertRaises(bp.PackError):
                vp.check_fixtures([item])

    def test_break_even_hit_rates_recompute(self):
        inst = self.instance("atomic-step-contract", "example.overhead-measurement")
        content, k = inst["slicing"]["content_tokens"], inst["slicing"]["slices"]
        rates = {}
        for cfg in inst["configurations"]:
            self.assertEqual(cfg["total_prefix_tokens"], cfg["message_tokens"] + cfg["tool_tokens"])
            prefix = cfg["total_prefix_tokens"]
            rates[f"{cfg['harness']}, {cfg['configuration']}"] = round((k - 1) * prefix / (k * prefix + content), 3)
        self.assertEqual({row["harness"]: row["required_hit_rate"] for row in inst["break_even"]}, rates)
        self.assertLess(min(rates.values()), 1 - 1 / k, "a small prefix lowers the threshold below 1 - 1/k")
        self.assertGreater(min(rates.values()), 0.5, "but does not remove it at this content size")

    def test_unattended_report_and_triage_agree(self):
        value = record("unattended-run-record", "run-checks")["value"]
        night = next(f["finding"] for f in value["golden_fixtures"] if f["id"] == "good-night")
        rungs = [entry["rung"] for entry in night["entries"]]
        self.assertTrue(night["headline"].startswith(f"{rungs.count('verified')} verified"))
        self.assertIn(f"{len(night['declined'])} declined", night["headline"])
        voided = {entry["candidate_ref"] for entry in night["entries"] if entry["rung"] == "void"}
        self.assertEqual(set(night["integrity"]["void_entries"]), voided)
        self.assertEqual(voided, {b.split("/", 1)[1] for b in night["delivery"]["discarded_kept_as_branches"]})
        triage = self.instance("unattended-run-record", "example.triage-record")
        self.assertEqual(triage["model_calls"], 0)
        ranks = [item["rank"] for item in triage["items"] if item["decision"] == "attempt"]
        self.assertEqual(ranks, list(range(1, len(ranks) + 1)))
        for item in triage["items"]:
            if item["decision"] == "decline":
                self.assertIsNone(item["rank"], item["candidate_ref"])
                self.assertNotEqual(item["reason"], "ranked", item["candidate_ref"])

    def test_reuse_ledger_rates_and_rollbacks_recompute(self):
        ledger = self.instance("retrieval-triggers-and-reuse", "example.reuse-ledger")
        self.assertEqual(ledger["verified_per_1000_calls"], round(ledger["verified"] / ledger["cost"]["model_calls"] * 1000, 1))
        base = ledger["baseline"]
        self.assertEqual(base["verified_per_1000_calls"], round(base["verified"] / base["model_calls"] * 1000, 1))
        self.assertEqual(ledger["rollbacks"], sum(hit["attempts"] - hit["verified"] for hit in ledger["hits"]))
        self.assertEqual(ledger["verdict"] == "reuse_pays", ledger["verified_per_1000_calls"] > base["verified_per_1000_calls"])
        lookup = self.instance("retrieval-triggers-and-reuse", "example.lookup-record")
        fits = [c for c in lookup["candidates"] if c["fit"] != "no_fit"]
        self.assertEqual(lookup["rung_answered"], "retrieved" if any(c["fit"] == "use_as_is" for c in fits) else lookup["rung_answered"])

    def test_duplicate_reclaim_and_inventory_recompute(self):
        dup = self.instance("file-triage-at-scale", "example.duplicate-set")
        self.assertEqual(dup["evidence_level"], "full_sha256")
        self.assertEqual(len({member["sha256"] for member in dup["members"]}), 1)
        self.assertEqual(len({member["inode"] for member in dup["members"]}), len(dup["members"]))
        self.assertTrue(all(member["hardlinks"] == 1 for member in dup["members"]))
        self.assertEqual(dup["reclaimable_bytes"], sum(sorted(m["allocated_bytes"] for m in dup["members"])[1:]))
        inventory = self.instance("file-triage-at-scale", "example.inventory")
        self.assertEqual(inventory["files_changed_by_scan"], 0)
        self.assertLessEqual(sum(group["allocated_bytes"] for group in inventory["groups"]), inventory["totals"]["allocated_bytes"])
        for root in inventory["roots"]:
            self.assertLessEqual(root["free_bytes"], root["total_bytes"], root["root_ref"])
        used = sum(root["total_bytes"] - root["free_bytes"] for root in inventory["roots"])
        self.assertLessEqual(inventory["totals"]["allocated_bytes"], used, "scanned files fit in the space used")

    def test_reproduction_verdict_follows_its_tolerance(self):
        rep = self.instance("measured-claims", "example.reproduction")
        claimed = float(rep["claimed_value"].split()[0])
        tolerance = float(rep["tolerance"].split()[1]) / 100
        within = all(abs(float(run["value"]) - claimed) / claimed <= tolerance for run in rep["runs"])
        self.assertEqual(rep["verdict"], "reproduced" if within else "not_reproduced")
        self.assertEqual(rep["correction_needed"], not within)
        correction = self.instance("measured-claims", "example.correction")
        self.assertIn(rep["claimed_value"].split()[0], correction["claimed"])


class QualityPackExamples(unittest.TestCase):
    """The acceptance, accessibility, usability, launch and exploratory packs of October 30: their record checks,
    the theme contrast example, and the people who keep every decision. The accessibility audit pack's code
    recomputes its contrast and lint examples in its own CI job."""

    FIXTURES = (("user-acceptance-testing", "signoff-checks"), ("accessibility-audit", "audit-checks"),
                ("usability-heuristics-review", "heuristic-checks"), ("launch-readiness", "go-checks"),
                ("exploratory-testing-charters", "session-checks"))
    PEOPLE = ("user-acceptance-testing.agree-criteria", "user-acceptance-testing.sign-off",
              "accessibility-audit.check-with-assistive-tech", "launch-readiness.record-go-decision")

    def test_record_checks_flag_each_bad_example_for_its_reason(self):
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

    def test_record_check_schemas_are_the_templates_they_check(self):
        for pack, slug, template_slug in (("user-acceptance-testing", "signoff-checks", "template.sign-off"),
                                          ("launch-readiness", "go-checks", "template.readiness-report"),
                                          ("exploratory-testing-charters", "session-checks", "template.session-notes")):
            self.assertEqual(record(pack, slug)["value"]["finding_schema"], record(pack, template_slug)["value"]["schema"], pack)

    def test_theme_contrast_example_recomputes(self):
        value = record("accessibility-audit", "example.contrast")["value"]
        results = vp.run_contrast_ratio(value)
        self.assertEqual(results, value["expected"])
        self.assertTrue(results["muted-text-light"]["normal_text"])
        self.assertFalse(results["muted-text-dark"]["normal_text"])
        self.assertEqual(results["muted-text-dark"]["ratio"], 3.69)

    def test_decisions_and_sessions_stay_with_people(self):
        for template_id in self.PEOPLE:
            brief = task(template_id)["brief"]
            self.assertEqual((brief["claimant"], brief["execution"]["model_use"]), ("human", "none"), template_id)
        for template_id in ("accessibility-audit.review-audit", "usability-heuristics-review.review-findings",
                            "exploratory-testing-charters.debrief-session"):
            self.assertEqual(task(template_id)["brief"]["review"]["required"], "distinct_reviewer", template_id)

    def test_live_checks_are_read_only(self):
        for pack in ("accessibility-audit", "user-acceptance-testing", "usability-heuristics-review", "launch-readiness",
                     "exploratory-testing-charters"):
            for item in IDX.docs[pack]["verbs.json"]["tasks"]:
                mode = item["brief"]["execution"]["network"]["mode"]
                self.assertIn(mode, ("none", "read_only"), item["brief"]["template_id"])
                self.assertEqual(item["brief"]["execution"]["external_effects"], "none")

    def test_findings_cite_wcag_criteria_from_the_checklist(self):
        listed = {row["sc"] for row in record("accessibility-audit", "wcag-checklist")["value"]["criteria"]}
        report = record("accessibility-audit", "example.audit-report")["value"]["instance"]
        for finding in report["findings"]:
            if finding["level"] != "AAA":
                self.assertIn(finding["sc"], listed, finding["id"])
            else:
                self.assertEqual(finding["conformance"], "advisory", finding["id"])
        self.assertEqual(report["statement"], "failures_found")


class VideoImprovementPackExamples(unittest.TestCase):
    """The video editing, QA, review, cut-down, thumbnail and audience acceptance packs of October 30: their record
    checks, and the arithmetic and consistency their worked examples state. The video QA pack recomputes its own
    worked example in its code's CI job."""

    FIXTURES = (("video-qa", "report-checks"), ("video-editing", "edit-checks"), ("video-review", "review-checks"),
                ("social-cutdowns", "cutdown-checks"), ("thumbnail-and-title", "title-checks"), ("video-uat", "uat-checks"))

    @staticmethod
    def instance(pack: str, slug: str):
        return record(pack, slug)["value"]["instance"]

    @staticmethod
    def words(text: str) -> int:
        return sum(1 for token in text.split() if any(ch.isalnum() for ch in token))

    def test_record_checks_flag_each_bad_example_for_its_reason(self):
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

    def test_pacing_report_recomputes_from_the_edit_list(self):
        edl = record("video-editing", "example.edit-list")["value"]
        lines, plan = edl["lines"], edl["instance"]
        report = self.instance("video-editing", "example.pacing-report")
        limits = report["limits"]
        rows = []
        for ev in [e for e in plan["events"] if e["track"] == "V1"]:
            start, end = ev["record_in_frame"] / plan["fps"], ev["record_out_frame"] / plan["fps"]
            length = round(end - start, 3)
            spoken = sum(self.words(lines[line]) for line in ev["carries_lines"])
            marks = [start, *ev["beats_s"], end]
            gap = round(max(b - a for a, b in zip(marks, marks[1:])), 3)
            wps, need = round(spoken / length, 2), round(0.5 + ev["new_text_words"] / 3, 2)
            verdicts = [name for name, hit in (
                ("rushed", wps > limits["rushed_above_wps"]),
                ("slack", wps < limits["slack_below_wps"] and not ev["beats_s"]),
                ("unreadable", length < need),
                ("dense", ev["new_text_words"] > limits["dense_new_words"] and spoken > 0),
                ("long", length > limits["long_shot_s"] and gap > limits["max_gap_between_beats_s"])) if hit]
            rows.append({"shot_id": ev["event_id"], "start_s": round(start, 3), "end_s": round(end, 3), "length_s": length,
                         "spoken_words": spoken, "words_per_second": wps, "new_text_words": ev["new_text_words"],
                         "reading_need_s": need, "longest_gap_s": gap, "verdicts": verdicts})
        self.assertEqual(rows, report["shots"])
        self.assertEqual(report["flagged"], sum(1 for row in rows if row["verdicts"]))
        main = [e for e in plan["events"] if e["track"] == "V1"]
        self.assertEqual([e["record_in_frame"] for e in main[1:]], [e["record_out_frame"] for e in main[:-1]])
        self.assertEqual(main[-1]["record_out_frame"], plan["total_frames"])
        note = self.instance("video-editing", "example.revision-note")
        self.assertFalse(note["overwrites_previous"])
        self.assertLessEqual({e for change in note["changes"] for e in change["events"]}, {e["event_id"] for e in plan["events"]})

    def test_review_examples_agree_with_each_other(self):
        review = self.instance("video-review", "example.review-findings")
        ids = [f["finding_id"] for f in review["findings"]]
        self.assertEqual(review["open_blockers"], sum(1 for f in review["findings"] if f["severity"] == "blocker" and f["status"] == "open"))
        self.assertLessEqual(set(review["top_fixes"]), set(ids))
        self.assertEqual(set(review["scores"]), set(record("video-review", "rubric")["value"]["areas"]))
        for finding in review["findings"]:
            self.assertIn(finding["fix_verb"], IDX.templates, finding["finding_id"])
            self.assertLessEqual(finding["start_s"], finding["end_s"], finding["finding_id"])
        trace = self.instance("video-review", "example.claim-trace")
        self.assertEqual(trace["numbers_found"], len(trace["claims"]))
        self.assertEqual(trace["numbers_traced"], sum(1 for c in trace["claims"] if c["result"] in ("upheld", "disputed")))
        again = self.instance("video-review", "example.re-review")
        self.assertEqual(sorted(r["finding_id"] for r in again["results"]), sorted(ids))
        self.assertNotEqual(again["media_sha256"], again["previous_sha256"])
        self.assertEqual(again["open_blockers"], sum(1 for f in again["new_findings"] if f["severity"] == "blocker"))
        routes = record("video-review", "fix-routes")["value"]["routes"]
        for route in routes:
            self.assertIn(route["fix_verb"], IDX.templates)

    def test_cutdown_plan_and_copy_recheck(self):
        plan = self.instance("social-cutdowns", "example.cutdown-plan")
        profile = self.instance("social-cutdowns", "example.platform-profile")
        self.assertEqual(plan["length_s"], round(sum(s["source_out_s"] - s["source_in_s"] for s in plan["segments"]), 3))
        low, high = profile["target_length_s"]
        self.assertTrue(low <= plan["length_s"] <= high and plan["length_s"] <= profile["max_length_s"])
        self.assertEqual(plan["segments"][0]["purpose"], "hook")
        hooks = self.instance("social-cutdowns", "example.hook-candidates")["candidates"]
        self.assertEqual(sorted(h["rank"] for h in hooks), list(range(1, len(hooks) + 1)))
        self.assertEqual(plan["segments"][0]["source_in_s"], next(h for h in hooks if h["rank"] == 1)["start_s"])
        meaning = self.instance("social-cutdowns", "example.meaning-check")
        empty = not (meaning["new_claims"] or meaning["changed_claims"] or meaning["dropped_qualifiers"])
        self.assertEqual(meaning["passes"], empty and all(n["traced"] for n in meaning["numbers"]))
        copy = self.instance("social-cutdowns", "example.copy-draft")
        self.assertTrue(3 <= len(copy["hashtags"]) <= 6)
        self.assertTrue(any("AI-generated voice" in d for d in copy["disclosures"]))
        private = record("social-cutdowns", "cutdown-checks")["value"]["deterministic_checks"]
        rule = next(c["rule"] for c in private if c["id"] == "nothing-private")
        for text in (copy["title"], copy["description"], copy["alt_text"], copy["call_to_action"]):
            self.assertTrue(vp.rule_passes(rule, {"copy_text": text}), text)
        self.assertFalse(any(copy["privacy_scan"].values()))

    def test_thumbnail_sizes_contrast_and_honesty_recompute(self):
        thumbs = self.instance("thumbnail-and-title", "example.thumbnail-candidates")
        sizes = self.instance("thumbnail-and-title", "example.size-check")
        width = thumbs["master"]["width_px"]
        for cand, checked in zip(thumbs["candidates"], sizes["candidates"]):
            self.assertEqual(cand["words"], self.words(cand["text_overlay"]), cand["candidate_id"])
            rows = [{"display": s["name"], "width_px": s["width_px"], "text_css_px": round(cand["text_px"] * s["width_px"] / width, 2),
                     "readable": round(cand["text_px"] * s["width_px"] / width, 2) >= sizes["min_css_px"]} for s in sizes["sizes"]]
            self.assertEqual(checked["rows"], rows, cand["candidate_id"])
            self.assertEqual(checked["readable_everywhere"], all(r["readable"] for r in rows))
            self.assertEqual(checked["words_ok"], cand["words"] <= 5)
        contrast = record("thumbnail-and-title", "contrast-example")["value"]
        self.assertEqual(vp.run_contrast_ratio(contrast), contrast["expected"])
        self.assertFalse(contrast["expected"]["T3"]["normal_text"])
        titles = self.instance("thumbnail-and-title", "example.title-candidates")["candidates"]
        for title in titles:
            self.assertEqual(title["chars"], len(title["text"]), title["candidate_id"])
        honesty = {c["candidate_id"]: c for c in self.instance("thumbnail-and-title", "example.honesty-check")["candidates"]}
        banned = record("thumbnail-and-title", "rules.honesty")["value"]["banned_pattern"]
        for title in titles:
            found = bool(__import__("re").search(banned, title["text"]))
            self.assertEqual(bool(honesty[title["candidate_id"]]["banned_patterns"]), found, title["candidate_id"])
        for item in honesty.values():
            kept = all(c["traced"] for c in item["claims"]) and not item["banned_patterns"] and item["promise_kept_at_s"] is not None
            self.assertEqual(item["passes"], kept, item["candidate_id"])
        plan = self.instance("thumbnail-and-title", "example.ab-plan")
        self.assertTrue(set(plan["variants"]) <= {k for k, v in honesty.items() if v["passes"]})

    def test_acceptance_decision_recomputes_from_the_plan_and_scores(self):
        plan = self.instance("video-uat", "example.uat-plan")
        scores = self.instance("video-uat", "example.scored-answers")
        decision = self.instance("video-uat", "example.uat-decision")
        self.assertLess(plan["criteria_fixed_on"], plan["first_session_on"])
        results = []
        for crit in plan["pass_criteria"]:
            rows = [r for r in scores["rows"] if r["task_id"] == crit["task_id"] and crit["segment"] in ("all", r["segment"])]
            met = sum(1 for r in rows if r["met_key"])
            share = round(met / len(rows), 3) if rows else None
            result = "unknown" if share is None else ("met" if share >= crit["min_share"] else "missed")
            results.append({"task_id": crit["task_id"], "segment": crit["segment"], "answers": len(rows), "met": met,
                            "share": share, "min_share": crit["min_share"], "result": result})
        self.assertEqual(decision["results"], results)
        self.assertEqual(decision["accepted"], all(r["result"] == "met" for r in results))
        self.assertEqual(decision["findings_proposed"], sum(1 for r in results if r["result"] == "missed") + len(scores["notes"]))
        bank = {task["task_id"] for task in record("video-uat", "task-bank")["value"]["tasks"]}
        self.assertLessEqual(set(plan["tasks"]), bank)


class GapPackExamples(unittest.TestCase):
    """The living research dossier, wiring and conformance checks, and persona panel packs of October 30: their
    record checks against their own templates, and the dates, counts, digests, reading order and quotes their worked
    examples state. The wiring pack's code recomputes its module map, behavior map and probe scan in its own CI job."""

    FIXTURES = (("living-research-dossier", "dossier-checks", "template.dossier", "example.dossier"),
                ("wiring-and-conformance-checks", "wiring-checks", "template.conformance-report",
                 "example.conformance-report"),
                ("persona-panel-second-opinion", "panel-checks", "template.synthesis", "example.synthesis"))

    @staticmethod
    def instance(pack: str, slug: str):
        return record(pack, slug)["value"]["instance"]

    def test_record_checks_flag_each_bad_example_for_its_reason(self):
        for pack, slug, template_slug, example_slug in self.FIXTURES:
            item = record(pack, slug)
            value = item["value"]
            self.assertEqual(value["finding_schema"], record(pack, template_slug)["value"]["schema"], pack)
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
            self.assertEqual(vp.failing_checks(value["deterministic_checks"], self.instance(pack, example_slug)), [], pack)
            first = next(iter(value["expected"]))
            value["expected"][first] = {"tampered": True}
            with self.assertRaises(bp.PackError):
                vp.check_fixtures([item])

    def test_dossier_dates_queue_cycles_and_triggers_recompute(self):
        from datetime import date, timedelta

        pack = "living-research-dossier"
        days = {name: spec["refresh_after_days"] for name, spec in record(pack, "rules.decay-classes")["value"]["classes"].items()}

        def refresh_by(as_of: str, decay: str) -> str:
            return (date.fromisoformat(as_of) + timedelta(days=days[decay])).isoformat()

        dossier = self.instance(pack, "example.dossier")
        facts = {f["id"]: f for f in dossier["facts"]}
        for fact in facts.values():
            self.assertEqual(fact["refresh_by"], refresh_by(fact["as_of"], fact["decay_class"]), fact["id"])
        self.assertEqual(dossier["due"], [f for f, v in facts.items() if v["refresh_by"] < dossier["as_of"]])
        self.assertEqual(dossier["open_questions"], sum(q["status"] in ("open", "partial") for q in dossier["questions"]))
        self.assertEqual((dossier["mode"], dossier["open_questions"]), ("watching", 0))
        self.assertEqual([q["number"] for q in dossier["questions"]], list(range(1, len(dossier["questions"]) + 1)))
        for question in dossier["questions"]:
            self.assertLessEqual(set(question["facts"]), set(facts), question["number"])
        self.assertEqual({p["number"] for p in dossier["parked"]},
                         {q["number"] for q in dossier["questions"] if q["status"] == "parked"})
        for old in dossier["superseded"]:
            self.assertIn(old["superseded_by"], facts)
            self.assertNotIn(old["id"], facts)
        self.assertEqual([c["cycle"] for c in dossier["cycles"]], list(range(1, len(dossier["cycles"]) + 1)))
        most = max(c["questions_worked"].count(n) for c in dossier["cycles"] for n in c["questions_worked"])
        self.assertEqual(dossier["max_sub_agents_per_question"], most)
        watched = {n for trigger in dossier["triggers"] for n in trigger["reopens"]}
        for question in dossier["questions"]:
            if any(facts[f]["decay_class"] != "stable" for f in question["facts"]):
                self.assertIn(question["number"], watched, question["number"])
        self.assertEqual(dossier["publication"]["decided_by_kind"], "person")
        for item in IDX.docs[pack]["nouns.json"]["records"]:
            self.assertNotEqual(item["value"]["role"], "schedule_proposal", "no schedule is proposed or activated")

        plan, log = self.instance(pack, "example.cycle-plan"), self.instance(pack, "example.cycle-log")
        worked = [w["question"] for w in log["worked"]]
        self.assertEqual([p["question"] for p in plan["picked"]], worked)
        self.assertEqual(len(set(worked)), len(worked), "one sub-agent per question in a cycle")
        self.assertEqual(len({w["sub_agent"] for w in log["worked"]}), len(worked))
        self.assertEqual(log["max_sub_agents_per_question"], 1)
        self.assertEqual(next(c for c in dossier["cycles"] if c["cycle"] == log["cycle"])["questions_worked"], worked)
        self.assertLessEqual(set(log["facts_added"]), set(facts))
        self.assertEqual({(s["id"], s["by"]) for s in log["facts_superseded"]},
                         {(s["id"], s["superseded_by"]) for s in dossier["superseded"]})
        self.assertEqual(log["questions_parked"], [p["number"] for p in dossier["parked"]])

        trigger = self.instance(pack, "example.trigger-check")
        fired = [r for r in trigger["results"] if r["result"] == "fired"]
        self.assertEqual(trigger["fired"], [r["trigger"] for r in fired])
        self.assertEqual(trigger["reopened"], sorted({n for r in fired for n in r["reopens"]}))
        self.assertEqual({p["question"] for p in plan["picked"]}, set(trigger["reopened"]))
        self.assertEqual([r["trigger"] for r in trigger["results"]], [t["name"] for t in dossier["triggers"]])
        for row in trigger["results"]:
            named = next(t for t in dossier["triggers"] if t["name"] == row["trigger"])
            self.assertEqual((row["check"], row["reopens"] if row in fired else named["reopens"]),
                             (named["check"], named["reopens"]))

        refresh = self.instance(pack, "example.refresh-record")
        for row in refresh["facts"]:
            self.assertLess(row["refresh_by"], refresh["checked_on"], row["fact"])
            if row["result"] == "still_true":
                self.assertEqual(row["new_refresh_by"], refresh_by(row["new_as_of"], row["decay_class"]))
                self.assertEqual((facts[row["fact"]]["as_of"], facts[row["fact"]]["refresh_by"]),
                                 (row["new_as_of"], row["new_refresh_by"]))
        self.assertEqual(refresh["due_before"], len(refresh["facts"]))
        self.assertEqual(refresh["due_after"], sum(r["result"] == "source_unreadable" for r in refresh["facts"]))

        answer = self.instance(pack, "example.answer")
        for fact in answer["facts"]:
            self.assertEqual(fact["refresh_by"], refresh_by(fact["as_of"], fact["decay_class"]))
            replaced = next(s for s in dossier["superseded"] if s["id"] == fact["replaces"])
            current = facts[replaced["superseded_by"]]
            self.assertEqual({k: current[k] for k in ("statement", "as_of", "decay_class", "refresh_by", "claims", "sources")},
                             {k: fact[k] for k in ("statement", "as_of", "decay_class", "refresh_by", "claims", "sources")})
        self.assertIn(answer["sub_agent"], {w["sub_agent"] for w in log["worked"] if w["question"] == answer["question"]})

    def test_dossier_pins_the_deep_research_nouns_instead_of_redefining_them(self):
        pack = "living-research-dossier"
        own = {r["value"]["describes"] for r in IDX.docs[pack]["nouns.json"]["records"] if r["value"]["role"] == "template"}
        theirs = {r["value"]["describes"] for r in IDX.docs["deep-research-report"]["nouns.json"]["records"]
                  if r["value"]["role"] == "template"}
        self.assertFalse(own & theirs)
        tasks = {t["brief"]["template_id"]: t["brief"] for t in IDX.docs[pack]["verbs.json"]["tasks"]}
        produced = {tid: {p["template"]["key"] for p in brief["output_contract"]["produces"]} for tid, brief in tasks.items()}
        self.assertLessEqual({key("deep-research-report", "template.source-log"), key("deep-research-report", "template.claim-extract")},
                             produced[f"{pack}.answer-question"])
        self.assertEqual(produced[f"{pack}.review-dossier"], {key("deep-research-report", "template.adversarial-review")})
        self.assertEqual(produced[f"{pack}.decide-publication"], {key("policy-and-law-watch", "template.delivery-record")})
        pinned = {pin["key"] for brief in tasks.values() for pin in brief["inputs"]["pinned"]}
        for slug in ("guardrail.quote-exactly", "guardrail.seek-counter-evidence", "guardrail.search-on-the-record",
                     "template.research-question", "rules.permitted-access", "rules.screening", "rules.evidence-strength",
                     "checklist"):
            self.assertIn(key("deep-research-report", slug), pinned, slug)
        self.assertEqual(tasks[f"{pack}.check-triggers"]["execution"]["model_use"], "none")
        for tid in (f"{pack}.answer-question", f"{pack}.check-triggers", f"{pack}.refresh-decayed-facts", f"{pack}.review-dossier"):
            self.assertEqual(tasks[tid]["execution"]["network"]["mode"], "read_only", tid)

    def test_wiring_examples_agree_with_each_other_and_with_findings_to_fixes(self):
        pack = "wiring-and-conformance-checks"
        modules = self.instance(pack, "example.module-map")["result"]
        self.assertEqual(modules["counts"], {s: sum(1 for r in modules["modules"] if r["status"] == s) for s in modules["counts"]})
        report = self.instance(pack, "example.conformance-report")
        gaps = {(f["rule"], f["item"]) for f in report["failures"]}
        self.assertEqual({item for rule, item in gaps if rule == "no-dark-modules"},
                         {r["module"] for r in modules["modules"] if r["status"] in ("dark", "test_only")})
        probes = self.instance(pack, "example.probe-report")
        passed = [run["probe"] for run in probes["runs"] if run["when_stopped"] == "passed"]
        self.assertEqual(probes["hollow"], sorted(probes["static"]["hollow"] + passed))
        self.assertEqual({item for rule, item in gaps if rule == "probes-probe"}, set(probes["hollow"]))
        coverage = self.instance(pack, "example.behavior-map")["scan"]["behaviors"]
        self.assertEqual({item for rule, item in gaps if rule == "behaviors-on-real-path"},
                         {row["id"] for row in coverage if row["status"] != "real_path"})
        rules = record(pack, "template.wiring-scope")["value"]["schema"]["properties"]["rules"]["items"]["enum"]
        self.assertEqual([row["rule"] for row in report["rules"]], rules)
        for row in report["rules"]:
            self.assertEqual(row["failures"], sum(1 for f in report["failures"] if f["rule"] == row["rule"]), row["rule"])
            self.assertTrue(row["canary"] and row["canary_caught_by"], row["rule"])
        finding = self.instance(pack, "example.finding")
        checks = record("findings-to-fixes", "record-checks")["value"]["deterministic_checks"]
        self.assertEqual(vp.failing_checks(checks, finding), [])
        self.assertEqual(vp.schema_errors(record("findings-to-fixes", "template.finding")["value"]["schema"], finding), [])
        self.assertIn(finding["id"], {f["finding_ref"] for f in report["failures"]})
        measurement = next(e for e in finding["evidence"] if e["kind"] == "measurement")
        self.assertEqual(measurement["sha256"], bp.value_sha256(self.instance(pack, "example.module-map")))
        tool = record(pack, "tool.wiring-checks")["value"]["code"]
        code = IDX.docs[pack]["manifest.json"]["code"]
        self.assertEqual(tool, {k: code[k] for k in ("path", "files", "sha256")})
        for item in IDX.docs[pack]["verbs.json"]["tasks"]:
            self.assertIn(item["brief"]["execution"]["network"]["mode"], ("none", "local_only"), item["brief"]["template_id"])

    def test_panel_digests_order_quotes_and_decision_recompute(self):
        import re

        pack = "persona-panel-second-opinion"
        panel = self.instance(pack, "example.panel")
        views = {v["reviewer_id"]: v for v in (self.instance(pack, f"example.view-{r['reviewer_id']}") for r in panel["reviewers"])}
        check = self.instance(pack, "example.independence-check")
        self.assertEqual(check["shuffle_seed"], panel["shuffle_seed"])
        for row in check["views"]:
            view = views[row["reviewer_id"]]
            self.assertEqual(row["view_sha256"], bp.value_sha256(view))
            self.assertEqual((row["packet_sha256"], view["packet_sha256"]), (panel["packet_sha256"], panel["packet_sha256"]))
            self.assertEqual(row["sealed_at"], view["sealed_at"])
            self.assertEqual(row["late"], view["sealed_at"] > panel["deadline"])
            self.assertFalse(view["saw_other_views"])
        self.assertLess(max(v["sealed_at"] for v in views.values()), check["checked_at"])
        order = sorted(views, key=lambda rid: hashlib.sha256(f"{check['shuffle_seed']}:{rid}".encode()).hexdigest())
        self.assertEqual(check["read_order"], order)
        for rid, view in views.items():
            text = " ".join([view["summary"], view["would_change_my_mind"], *(p["text"] + " " + p["why"] for p in view["points"])])
            for other in set(views) - {rid}:
                self.assertIsNone(re.search(rf"\b{other}\b", text), (rid, other))
                self.assertNotIn(views[other]["perspective"], text, (rid, other))
        cards = {r["key"].rsplit(".v0.1.0.", 1)[1]: r["value"] for r in IDX.docs[pack]["nouns.json"]["records"]
                 if r["value"]["role"] == "perspective_card"}
        for reviewer in panel["reviewers"]:
            self.assertEqual(cards[reviewer["card_ref"]]["perspective"], reviewer["perspective"])
            self.assertEqual(views[reviewer["reviewer_id"]]["perspective"], reviewer["perspective"])
            same = reviewer["model_family"] == panel["producer"]["model_family"]
            self.assertEqual(bool(reviewer["same_family_reason"]), same, reviewer["reviewer_id"])
        self.assertEqual(len({r["perspective"] for r in panel["reviewers"]}), len(panel["reviewers"]))
        synthesis = self.instance(pack, "example.synthesis")
        self.assertEqual({(v["reviewer_id"], v["view_sha256"]) for v in synthesis["views"]},
                         {(v["reviewer_id"], v["view_sha256"]) for v in check["views"]})
        self.assertEqual({r["reviewer_id"] for r in synthesis["same_family_reviewers"]},
                         {r["reviewer_id"] for r in panel["reviewers"] if r["same_family_reason"]})
        for position in synthesis["positions"]:
            view = views[position["reviewer_id"]]
            self.assertIn(position["quote"], " ".join([view["summary"], *(p["text"] for p in view["points"])]), position)
        routes = record(pack, "rules.synthesis")["value"]["routes"]
        ids = [d["id"] for d in synthesis["disagreements"]]
        self.assertEqual(synthesis["disagreement_count"], len(ids))
        for disagreement in synthesis["disagreements"]:
            self.assertEqual(disagreement["route"], routes[disagreement["kind"]], disagreement["id"])
            sides = {p["reviewer_id"] for p in synthesis["positions"] if p["disagreement_id"] == disagreement["id"]}
            self.assertGreaterEqual(len(sides), 2, disagreement["id"])
        audit = self.instance(pack, "example.synthesis-audit")
        self.assertEqual(audit["positions_checked"], len(synthesis["positions"]))
        self.assertEqual(audit["passed"], not any(audit[k] for k in ("quotes_not_found", "points_dropped", "misrouted",
                                                                      "head_count_language")))
        decision = self.instance(pack, "example.decision")
        self.assertEqual(decision["audit_passed"], audit["passed"])
        answered = [s["disagreement_id"] for s in decision["settled"]] + [s["disagreement_id"] for s in decision["left_open"]]
        self.assertEqual(sorted(answered), sorted(ids))

    def test_people_decide_and_reviewers_are_distinct(self):
        for template_id in ("living-research-dossier.decide-publication", "persona-panel-second-opinion.decide"):
            brief = task(template_id)["brief"]
            self.assertEqual((brief["claimant"], brief["execution"]["model_use"]), ("human", "none"), template_id)
        for template_id in ("living-research-dossier.review-dossier", "persona-panel-second-opinion.give-view",
                            "persona-panel-second-opinion.synthesize-disagreements",
                            "persona-panel-second-opinion.audit-synthesis"):
            self.assertEqual(task(template_id)["brief"]["review"]["required"], "distinct_reviewer", template_id)



class ReviewPackExamples(unittest.TestCase):
    """The continuous self-review, annoyance hunt, edge and corner cases, regression watch and codebase health review
    packs of October 30: their record checks against their own templates or the findings to fixes template, every
    finding they produce fitting findings to fixes with reproduce, fix, verify and regression guard verbs, and the picks,
    diffs, coverage, ranks, outcomes and statuses their worked examples state. The edge case and health check code
    recompute their own worked examples in their CI jobs."""

    F2F = None
    FIXTURES = (("continuous-self-review", "loop-checks", "template.review-run", "example.review-run"),
                ("annoyance-hunt", "annoyance-checks", F2F, "example.finding"),
                ("edge-and-corner-cases", "edge-checks", "template.case-results", "example.case-results"),
                ("regression-watch", "watch-checks", "template.comparison", "example.comparison"),
                ("codebase-health-review", "health-checks", F2F, "example.finding"))
    FOLLOW_UPS = {"reproduce", "propose-fix", "fix", "verify-fix", "add-regression-guard"}
    PACKS = ("continuous-self-review", "annoyance-hunt", "edge-and-corner-cases", "regression-watch", "codebase-health-review")

    @staticmethod
    def instance(pack: str, slug: str):
        return record(pack, slug)["value"]["instance"]

    def schema(self, pack: str, template_slug):
        if template_slug is None:
            return record("findings-to-fixes", "template.finding")["value"]["schema"]
        return record(pack, template_slug)["value"]["schema"]

    def test_record_checks_flag_each_bad_example_for_its_reason(self):
        for pack, slug, template_slug, example_slug in self.FIXTURES:
            item = record(pack, slug)
            value = item["value"]
            schema = self.schema(pack, template_slug)
            results = vp.run_finding_checks(value)
            self.assertEqual(results, value["expected"], pack)
            for fixture in value["golden_fixtures"]:
                if fixture["label"] == "known_good":
                    self.assertEqual(results[fixture["id"]], {"verdict": "pass", "failed_checks": []}, fixture["id"])
                    self.assertEqual(vp.schema_errors(schema, fixture["finding"]), [], fixture["id"])
                else:
                    self.assertEqual(results[fixture["id"]]["failed_checks"], [fixture["fails"]], fixture["id"])
            caught = {c for f in value["golden_fixtures"] if f["label"] == "known_bad" for c in results[f["id"]]["failed_checks"]}
            self.assertEqual(caught, {check["id"] for check in value["deterministic_checks"]}, pack)
            self.assertEqual(vp.failing_checks(value["deterministic_checks"], self.instance(pack, example_slug)), [], pack)
            first = next(iter(value["expected"]))
            value["expected"][first] = {"tampered": True}
            with self.assertRaises(bp.PackError):
                vp.check_fixtures([item])

    def test_every_finding_fits_findings_to_fixes_with_its_follow_ups(self):
        checks = record("findings-to-fixes", "record-checks")["value"]["deterministic_checks"]
        schema = record("findings-to-fixes", "template.finding")["value"]["schema"]
        findings = []
        for pack, slug in (("annoyance-hunt", "annoyance-checks"), ("codebase-health-review", "health-checks")):
            findings += [f["finding"] for f in record(pack, slug)["value"]["golden_fixtures"] if f["label"] == "known_good"]
        for pack, slug in (("annoyance-hunt", "example.finding"), ("codebase-health-review", "example.finding"),
                           ("edge-and-corner-cases", "example.finding"), ("regression-watch", "example.regression-finding"),
                           ("regression-watch", "example.flake-finding")):
            findings.append(self.instance(pack, slug))
        self.assertEqual(len(findings), 11)
        import re

        for finding in findings:
            self.assertEqual(vp.failing_checks(checks, finding), [], finding["id"])
            self.assertEqual(vp.schema_errors(schema, finding), [], finding["id"])
            self.assertEqual({w["verb"] for w in finding["work"]}, self.FOLLOW_UPS, finding["id"])
            self.assertEqual((finding["status"], finding["public"]), ("open", False), finding["id"])
            self.assertIsNone(re.search(r"(line-?[0-9]|-py\b|\.py|[0-9]{3,})", finding["fingerprint"]), finding["fingerprint"])
        for pack, producer in (("annoyance-hunt", "record-annoyance-findings"), ("edge-and-corner-cases", "record-edge-findings"),
                               ("regression-watch", "report-regressions"), ("codebase-health-review", "write-health-report")):
            produced = {p["template"]["key"] for p in task(f"{pack}.{producer}")["brief"]["output_contract"]["produces"]}
            self.assertIn(key("findings-to-fixes", "template.finding"), produced, pack)

    def test_rotation_pick_recomputes_from_the_catalog_and_log(self):
        from datetime import date

        pack = "continuous-self-review"
        catalog = {s["scope_id"]: s for s in self.instance(pack, "example.scope-catalog")["scopes"]}
        log = self.instance(pack, "example.review-log")
        pick = self.instance(pack, "example.scope-pick")
        as_of = date.fromisoformat(pick["as_of"][:10])
        last = {}
        for entry in log["entries"]:
            if entry["reviewed_at"] < pick["as_of"]:
                last[entry["scope_id"]] = max(last.get(entry["scope_id"], entry["reviewed_at"]), entry["reviewed_at"])
        rows = {r["scope_id"]: r for r in pick["candidates"]}
        self.assertEqual(set(rows), set(catalog))
        for sid, scope in catalog.items():
            row = rows[sid]
            self.assertEqual(row["last_reviewed"], last.get(sid), sid)
            days = (as_of - date.fromisoformat(last[sid][:10])).days if sid in last else None
            self.assertEqual(row["days_since"], days, sid)
            self.assertEqual(row["overdue"], days is not None and days > scope["max_interval_days"], sid)
            self.assertEqual(row["urgent"], days is not None and days > 2 * scope["max_interval_days"], sid)
            expected = None if days is None else round(days / scope["max_interval_days"] + min(row["churn"] / scope["churn"]["cap"], 1)
                                                       + 0.5 * min(row["open_high"], 2), 3)
            self.assertEqual(row["score"], expected, sid)
        never = [sid for sid in catalog if rows[sid]["score"] is None]
        urgent = sorted((r for r in pick["candidates"] if r["urgent"]),
                        key=lambda r: (-r["days_since"] / catalog[r["scope_id"]]["max_interval_days"], r["scope_id"]))
        rest = sorted((r for r in pick["candidates"] if r["score"] is not None and not r["urgent"]), key=lambda r: (-r["score"], r["scope_id"]))
        order = never + [r["scope_id"] for r in urgent + rest]
        self.assertEqual([r["scope_id"] for r in sorted(pick["candidates"], key=lambda r: r["rank"])], order)
        self.assertEqual(pick["picked"], order[:pick["scopes_per_window"]])
        schedule = self.instance(pack, "example.review-schedule")
        self.assertEqual(pick["scopes_per_window"], schedule["scopes_per_window"])
        approval = self.instance(pack, "example.schedule-approval")
        self.assertLessEqual(set(pick["picked"]), set(approval["scope"]))
        self.assertLess(approval["decided_at"], pick["as_of"])
        self.assertLess(pick["as_of"], approval["expires"])
        from datetime import datetime

        scheduled = [e for e in log["entries"] if e["trigger"] == "schedule"]
        self.assertTrue(scheduled)
        for entry in log["entries"]:
            if entry["reviewed_at"] < approval["decided_at"]:
                self.assertEqual(entry["trigger"], "manual", entry["run_id"])
        days = {datetime.fromisoformat(e["reviewed_at"][:10]).strftime("%A") for e in scheduled}
        self.assertEqual(len(days), 1, "scheduled runs fall on one weekday")
        self.assertTrue(any(f"Start on {next(iter(days))}" in change for change in approval["changes"]), days)
        self.assertEqual(datetime.fromisoformat(pick["as_of"][:10]).strftime("%A"), next(iter(days)))

    def test_review_diff_and_coverage_recompute(self):
        from datetime import date

        pack = "continuous-self-review"
        inputs = record(pack, "example.diff-inputs")["value"]
        run = self.instance(pack, "example.review-run")
        ran, changed = set(inputs["checks_run"]), set(inputs["checks_changed"])
        seen = {fp for check, fps in inputs["seen_now"].items() if check in ran for fp in fps}
        previous = {f["fingerprint"]: f["check"] for f in inputs["previous_open"]}
        resolved = {f["fingerprint"] for f in inputs["closed_before"] if f["reason"] == "resolved"}
        decided = {f["fingerprint"] for f in inputs["closed_before"] if f["reason"] != "resolved"}
        fixes = {f["fingerprint"] for f in inputs["fixes"]}
        verified = {v["fingerprint"] for v in inputs["verifications"] if v["verified_by"] != "fixer"}
        gone = {fp: c for fp, c in previous.items() if fp not in seen}
        expected = {"new": sorted(seen - set(previous) - resolved - decided),
                    "still_open": sorted(fp for fp in seen & set(previous) if not (fp in fixes and fp in verified)),
                    "reopened": sorted((seen & resolved) | {fp for fp in seen & set(previous) if fp in fixes and fp in verified}),
                    "not_checked": sorted(fp for fp, c in gone.items() if c not in ran or c in changed),
                    "fixed": sorted(fp for fp, c in gone.items() if c in ran and c not in changed and fp in fixes and fp in verified),
                    "gone_unverified": sorted(fp for fp, c in gone.items() if c in ran and c not in changed and fp in fixes and fp not in verified),
                    "gone_unexplained": sorted(fp for fp, c in gone.items() if c in ran and c not in changed and fp not in fixes)}
        self.assertEqual({name: sorted(row["fingerprint"] for row in rows) for name, rows in run["diff"].items()}, expected)
        self.assertEqual(sorted(d["fingerprint"] for d in run["decided_seen"]), sorted(seen & decided))
        self.assertEqual(run["carried"], sum(len(rows) for name, rows in run["diff"].items() if name != "new"))
        self.assertTrue(all(len(rows) == 1 for rows in expected.values()), "the example shows one finding in each class")
        self.assertEqual(len(run["decided_seen"]), 1, "and one a person decided, left alone")
        follow = record(pack, "diff-rules")["value"]["follow_ups"]
        for name, key_ in (("gone_unverified", "gone_unverified"), ("gone_unexplained", "gone_unexplained"), ("reopened", "reopened")):
            for row in run["diff"][name]:
                self.assertEqual(row["proposed_verb"], follow[key_], name)
        self.assertEqual({c["check"] for c in run["checks_run"]}, ran)
        self.assertEqual(run["checks_not_run"], inputs["checks_not_run"])
        log = self.instance(pack, "example.review-log")
        catalog = {s["scope_id"]: s for s in self.instance(pack, "example.scope-catalog")["scopes"]}
        self.assertEqual([e["reviewed_at"] for e in log["entries"]], sorted(e["reviewed_at"] for e in log["entries"]), "append-only, in order")
        self.assertIn(run["run_id"], {e["run_id"] for e in log["entries"]})
        self.assertEqual(next(e for e in log["entries"] if e["run_id"] == run["run_id"])["counts"], {n: len(r) for n, r in run["diff"].items()})
        last = {}
        for entry in log["entries"]:
            last[entry["scope_id"]] = max(last.get(entry["scope_id"], entry["reviewed_at"]), entry["reviewed_at"])
        today = date.fromisoformat(log["as_of"][:10])
        age = {sid: (today - date.fromisoformat(at[:10])).days for sid, at in last.items()}
        coverage = log["coverage"]
        self.assertEqual(coverage["scopes_total"], len(catalog))
        self.assertEqual(coverage["never_reviewed"], [sid for sid in catalog if sid not in last])
        self.assertEqual(coverage["overdue"], [sid for sid in catalog if sid in age and age[sid] > catalog[sid]["max_interval_days"]])
        self.assertEqual(coverage["reviewed_within_interval"], sum(1 for sid in catalog if sid in age and age[sid] <= catalog[sid]["max_interval_days"]))
        latest = {}
        for entry in log["entries"]:
            latest[entry["scope_id"]] = entry
        self.assertEqual(log["open_findings"], sum(v for e in latest.values() for c, v in e["counts"].items() if c != "fixed"))

    def test_schedules_wait_for_a_person_and_nothing_self_approves(self):
        pack = "continuous-self-review"
        schedule = self.instance(pack, "example.review-schedule")
        self.assertEqual((schedule["activation"], schedule["start"], schedule["stop"]), ("not_activated", None, None))
        self.assertEqual(schedule["enqueues"], [f"{pack}.pick-scope"])
        self.assertIn("No scheduler is activated", schedule["activation_path"])
        for p in self.PACKS:
            for item in IDX.docs[p]["nouns.json"]["records"]:
                self.assertNotEqual(item["value"]["role"], "schedule_proposal", item["key"])
        approve = task(f"{pack}.approve-schedule")["brief"]
        self.assertEqual({p["template"]["key"] for p in approve["output_contract"]["produces"]}, {key("unattended-run-record", "template.run-approval")})
        for template_id in (f"{pack}.approve-schedule", "annoyance-hunt.confirm-ranking", "regression-watch.accept-baseline"):
            brief = task(template_id)["brief"]
            self.assertEqual((brief["claimant"], brief["execution"]["model_use"]), ("human", "none"), template_id)
        self.assertIs(self.instance(pack, "example.self-review")["self_approval"], False)
        log = task(f"{pack}.log-run")["brief"]["output_contract"]
        self.assertEqual((log["write_mode"], log["target_slot"]), ("compare_and_set", "review_log"))
        acceptance = self.instance("regression-watch", "example.acceptance")
        self.assertEqual(acceptance["decided_by_kind"], "person")
        self.assertIs(self.instance("regression-watch", "example.comparison")["baseline_updated"], False)

    def test_annoyance_scores_ranks_and_findings_recompute(self):
        pack = "annoyance-hunt"
        log = self.instance(pack, "example.annoyance-log")

        def level(occurrences, opportunities):
            share = occurrences / opportunities
            return 4 if share >= 0.75 else 3 if share >= 0.35 else 2 if share >= 0.10 else 1

        for entry in log["entries"]:
            lv = level(entry["occurrences"], entry["opportunities"])
            self.assertEqual(entry["frequency_level"], lv, entry["id"])
            self.assertEqual(entry["score"], lv * entry["pain"], entry["id"])
            self.assertEqual(entry["low_confidence"], entry["opportunities"] < 3, entry["id"])
            self.assertEqual(entry["severity"], "P2" if entry["score"] >= 8 and not entry["low_confidence"] else "P3", entry["id"])
            self.assertTrue(entry["fingerprint"].startswith(f"annoyance/{entry['surface']}/"), entry["id"])
            self.assertNotIn(entry["category"], entry["fingerprint"], "a person may change the category without splitting duplicates")

        def ranked(entries, pain):
            return [e["id"] for e in sorted(entries, key=lambda e: (-level(e["occurrences"], e["opportunities"]) * pain(e), -len(e["groups"]),
                                                                    -pain(e), int(e["id"].split("-")[1])))]

        self.assertEqual([e["id"] for e in sorted(log["entries"], key=lambda e: e["rank"])], ranked(log["entries"], lambda e: e["pain"]))
        confirmation = self.instance(pack, "example.ranking-confirmation")
        changed = {c["id"]: int(c["to"]) for c in confirmation["changes"] if c["field"] == "pain"}
        self.assertEqual(confirmation["ranking_after"], ranked(log["entries"], lambda e: changed.get(e["id"], e["pain"])))
        self.assertEqual(confirmation["confirmed_by_kind"], "person")
        by_fp = {e["fingerprint"]: e for e in log["entries"]}
        goods = [f["finding"] for f in record(pack, "annoyance-checks")["value"]["golden_fixtures"] if f["label"] == "known_good"]
        self.assertEqual(self.instance(pack, "example.finding"), goods[0])
        for finding in goods:
            entry = by_fp[finding["fingerprint"]]
            measurement = next(e["detail"] for e in finding["evidence"] if e["kind"] == "measurement")
            self.assertEqual(measurement, f"category {entry['category']}: frequency {entry['occurrences']} of {entry['opportunities']} {entry['unit']}; "
                                          f"pain {entry['pain']} of 4; score {entry['score']} (frequency level {entry['frequency_level']} x pain {entry['pain']}); "
                                          f"affects {', '.join(entry['groups'])}")
            quote = next(e for e in finding["evidence"] if e["kind"] == "quote")
            self.assertEqual((quote["detail"], quote["location"]), (entry["quotes"][0]["quote"], entry["quotes"][0]["from"]))
            self.assertEqual(finding["severity"], entry["severity"])
        session = self.instance(pack, "example.friction-session")
        from_session = {q["quote"] for e in log["entries"] for q in e["quotes"] if q["from"].startswith("session FS-1,")}
        self.assertEqual(from_session, {o["quote"] for o in session["observations"]}, "every observation of the session is kept in the log")
        extract = self.instance(pack, "example.complaint-extract")
        self.assertEqual(extract["messages_with_complaint"], sum(c["count"] for c in extract["complaints"]))
        self.assertEqual(extract["messages_read"], extract["messages_with_complaint"] + sum(x["count"] for x in extract["excluded"])
                         + extract["messages_without_complaint"])
        for category in record(pack, "friction-catalog")["value"]["categories"]:
            self.assertEqual(IDX.values[f"{category['heuristic']['store']}/{category['heuristic']['key']}"]["role"], "heuristic", category["category"])
        for slug in ("example.charter-website", "example.charter-cli", "example.charter-video", "example.charter-docs"):
            self.assertEqual(record(pack, slug)["value"]["conforms_to"]["key"], key("exploratory-testing-charters", "template.charter"))

    def test_edge_results_follow_their_plan_and_case_set(self):
        pack = "edge-and-corner-cases"
        plan = self.instance(pack, "example.edge-plan")
        case_set = self.instance(pack, "example.case-set")
        picked = {p["id"]: p for p in case_set["picked"]}
        self.assertEqual((case_set["seed"], case_set["kinds"], case_set["limits"]), (plan["seed"], plan["kinds"], plan["limits"]))
        self.assertEqual(case_set["count"], sum(sum(groups.values()) for groups in case_set["by_group"].values()))
        catalog_labels = {s["label"] for s in record(pack, "catalog.interface")["value"]["states"]}
        catalog_labels |= {s["label"] for s in record(pack, "catalog.video")["value"]["edges"]}
        generated = {label for kind in ("strings", "numbers", "dates", "lists", "bodies") for label in record(pack, f"labels.{kind}")["value"]["labels"]}
        classes = [c["class"] for c in record(pack, "catalog.inputs")["value"]["classes"]] + sorted(catalog_labels)
        classes += [e["label"] for e in record(pack, "catalog.api")["value"]["edges"]]
        placed = [c["class"] for c in plan["chosen"]] + [c["class"] for c in plan["skipped"]]
        self.assertEqual(sorted(placed), sorted(classes), "every catalog class is chosen or skipped, once")
        self.assertEqual(len(placed), 43)

        def expected(label):
            matches = [x for x in plan["expectations"] if x["labels"] == label or (x["labels"].endswith(".") and label.startswith(x["labels"]))]
            return max(matches, key=lambda x: len(x["labels"]))["expected"]

        runs = {label for c in plan["chosen"] for label in c["run"]}
        for slug, source in (("example.case-results", "generator"), ("example.interface-and-video-results", "catalog")):
            results = self.instance(pack, slug)
            self.assertEqual(results["cases_from"], source, slug)
            self.assertLess(plan["pinned_at"], results["run_at"], "expectations were pinned before the run")
            rows = results["rows"]
            self.assertEqual(results["counts"], {"pass": sum(r["verdict"] == "pass" for r in rows), "fail": sum(r["verdict"] == "fail" for r in rows),
                                                 "not_run": len(results["not_run"])}, slug)
            self.assertEqual(results["any_failed"], any(r["verdict"] == "fail" for r in rows), slug)
            self.assertEqual({f["case_id"] for f in results["findings_proposed"]}, {r["case_id"] for r in rows if r["verdict"] == "fail"}, slug)
            for proposal in results["findings_proposed"]:
                self.assertIn(proposal["case_id"], proposal["guard"], slug)
            for row in rows:
                self.assertTrue(row["input_escaped"].isascii(), row["case_id"])
                self.assertEqual(row["expected"].split(":")[0], expected(row["label"]), row["case_id"])
                self.assertIn(row["label"], runs, row["case_id"])
                if source == "generator":
                    self.assertEqual((row["label"], row["input_escaped"]), (picked[row["case_id"]]["label"], picked[row["case_id"]]["escaped"]))
                    self.assertIn(row["label"], generated)
                else:
                    self.assertIn(row["label"], catalog_labels)
        labels_run = {r["label"] for slug in ("example.case-results", "example.interface-and-video-results") for r in self.instance(pack, slug)["rows"]}
        labels_run |= {n["label"] for slug in ("example.case-results", "example.interface-and-video-results") for n in self.instance(pack, slug)["not_run"]}
        self.assertEqual(labels_run, runs, "every label the plan runs is a row or listed as not run")
        for template_id in (f"{pack}.run-input-cases", f"{pack}.check-interface-edges", f"{pack}.check-api-edges", f"{pack}.check-video-edges"):
            self.assertIn(task(template_id)["brief"]["execution"]["network"]["mode"], ("none", "local_only"), template_id)
        finding = self.instance(pack, "example.finding")
        reproduction = next(e for e in finding["evidence"] if e["kind"] == "reproduction")
        dst = next(p for p in picked.values() if p["label"] == "dates.dst.gap-us")
        self.assertIn(str(plan["seed"]), reproduction["detail"])
        self.assertIn(dst["id"], reproduction["detail"])
        self.assertIn(dst["escaped"], reproduction["location"])
        self.assertEqual(sum(record(pack, f"labels.{k}")["value"]["count"] for k in ("strings", "numbers", "dates", "lists", "bodies")), len(generated))

    def test_regression_outcomes_recompute_from_baseline_measurement_and_reruns(self):
        pack = "regression-watch"
        baseline = {item["item"]: item for item in self.instance(pack, "example.baseline-set")["items"]}
        measurement = self.instance(pack, "example.measurement")
        comparison = self.instance(pack, "example.comparison")
        first = {item["item"]: item["value"] for item in measurement["items"]}

        def text(item, value):
            if item["kind"] == "screenshot":
                return f"sha256 {value[:12]}"
            if item["kind"] == "api_shape":
                return "shifts[].ends_at:string present" if "ends_at" in value else "shifts[].ends_at removed"
            return f"{value:g} {item['unit']}".strip()

        def judge(item, shown):
            """within, or the direction it moved: better, neutral or worse."""
            rule, base = item["tolerance"], item["value"]
            if item["kind"] in ("screenshot", "api_shape"):
                same = shown == text(item, base)
                return "within" if same else ("neutral" if item["kind"] == "screenshot" else "worse")
            value = float(shown.split()[0])
            if rule["rule"] == "relative":
                inside = abs(value - base) <= rule["amount"] * base
            elif rule["rule"] == "absolute":
                inside = abs(value - base) <= rule["amount"]
            elif rule["rule"] == "at_most":
                inside = value <= rule["amount"]
            else:
                inside = value == base
            if inside:
                return "within"
            if rule["better"] == "none":
                return "worse"
            return "better" if (value < base) == (rule["better"] == "lower") else "worse"

        outcome = {}
        for name, rows in (("regressions", comparison["regressions"]), ("flaky", comparison["flaky"]), ("changed", comparison["changed"])):
            for row in rows:
                item = baseline[row["item"]]
                runs = [judge(item, row[k]) for k in ("first_run", "rerun_1", "rerun_2")]
                self.assertEqual(row["first_run"], text(item, first[row["item"]]), row["item"])
                self.assertNotEqual(runs[0], "within", row["item"])
                verdict = ("flaky" if "within" in runs else "regressions" if set(runs) == {"worse"} else "changed" if "worse" not in runs else "flaky")
                outcome[row["item"]] = verdict
                self.assertEqual(verdict, name, row["item"])
                if name == "changed":
                    self.assertEqual(row["direction"], runs[0], row["item"])
        for row in comparison["matches"]:
            item = baseline[row["item"]]
            self.assertEqual(row["value"], text(item, first[row["item"]]))
            self.assertEqual(judge(item, row["value"]), "within", row["item"])
            outcome[row["item"]] = "matches"
        self.assertEqual({m["item"] for m in comparison["missing"]}, {m["item"] for m in measurement["not_measured"]})
        for row in comparison["missing"]:
            outcome[row["item"]] = "missing"
        self.assertEqual(sorted(outcome), sorted(baseline), "every baseline item has exactly one outcome")
        self.assertEqual(comparison["counts"], {"match": len(comparison["matches"]), "regression": len(comparison["regressions"]),
                                                "flaky": len(comparison["flaky"]), "changed": len(comparison["changed"]),
                                                "missing": len(comparison["missing"]), "not_comparable": len(comparison["not_comparable"])})
        acceptance = self.instance(pack, "example.acceptance")
        decided = [d["item"] for d in acceptance["decisions"]]
        self.assertEqual(sorted(decided), sorted(row["item"] for name in ("regressions", "flaky", "changed") for row in comparison[name]),
                         "one decision for every item that moved, none for matches or missing items")
        accepted = {d["item"] for d in acceptance["decisions"] if d["decision"] == "accept_new"}
        self.assertEqual(accepted, {row["item"] for row in comparison["changed"]})
        self.assertFalse(accepted & {row["item"] for row in comparison["regressions"] + comparison["flaky"]})
        tolerances = {d["item"]: d["tolerance"] for d in acceptance["decisions"] if d["decision"] == "change_tolerance"}
        old = self.instance(pack, "example.baseline-set")
        new = self.instance(pack, "example.new-baseline-set")
        applied = [{**item, "value": first[item["item"]] if item["item"] in accepted else item["value"],
                    "tolerance": tolerances.get(item["item"], item["tolerance"])} for item in old["items"]]
        self.assertEqual(new["items"], applied, "the new set is the old one with only the person's decisions applied")
        self.assertEqual((new["status"], new["supersedes"], new["change"], new["settings"], new["subject"]),
                         ("accepted", old["baseline_set_id"], measurement["change"], old["settings"], old["subject"]))
        self.assertIn(acceptance["acceptance_id"], new["acceptance_ref"])
        self.assertTrue(acceptance["new_baseline_set"].startswith(f"{new['baseline_set_id']}:"))
        self.assertLess(acceptance["decided_at"], new["captured_at"])
        apply = task(f"{pack}.apply-acceptance")["brief"]
        self.assertEqual((apply["claimant"] != "human", apply["execution"]["model_use"]), (True, "none"))
        self.assertEqual({p["template"]["key"] for p in apply["output_contract"]["produces"]}, {key(pack, "template.baseline")})
        fingerprints = {r["finding_fingerprint"] for r in comparison["regressions"]} | {r["check_finding_fingerprint"] for r in comparison["flaky"]}
        self.assertLessEqual({self.instance(pack, s)["fingerprint"] for s in ("example.regression-finding", "example.flake-finding")}, fingerprints)
        self.assertEqual(self.instance(pack, "example.flake-finding")["kind"], "issue", "a flaky check is a finding about the check")

    def test_health_report_follows_its_scans_and_has_no_single_score(self):
        pack = "codebase-health-review"
        areas = [a["area"] for a in record(pack, "health-areas")["value"]["areas"]]
        plan = self.instance(pack, "example.health-plan")
        report = self.instance(pack, "example.health-report")
        self.assertEqual(sorted([a["area"] for a in plan["areas"]] + [a["area"] for a in plan["not_measured"]]), sorted(areas))
        self.assertEqual(sorted([a["area"] for a in report["areas"]] + [a["area"] for a in report["not_run"]]), sorted(areas))
        self.assertEqual(report["not_run"], plan["not_measured"])
        for slug in ("example.todo-scan", "example.swallow-scan"):
            scan = self.instance(pack, slug)
            levels = {i["level"] for i in scan["items"]}
            self.assertEqual(scan["status"], "act" if "act" in levels else "watch" if "watch" in levels else "ok", slug)
            row = next(a for a in report["areas"] if a["area"] == scan["area"])
            self.assertEqual(row["status"], scan["status"], slug)
            proposed = [f for f in report["findings_proposed"] if f["area"] == scan["area"]]
            self.assertEqual(len(proposed), sum(1 for i in scan["items"] if i["level"] == "act"), slug)
            self.assertEqual(sorted(f["location"] for f in proposed), sorted(i["location"] for i in scan["items"] if i["level"] == "act"), slug)
        import re

        rows = {row["area"]: row for row in report["areas"]}
        for row in report["areas"]:
            if row["status"] == "act":
                self.assertTrue(any(f["area"] == row["area"] for f in report["findings_proposed"]), row["area"])
        for proposal in report["findings_proposed"]:
            self.assertEqual(rows[proposal["area"]]["status"], "act", proposal["fingerprint"])
            self.assertTrue(any(t.startswith(f"{proposal['location']}: ") for t in rows[proposal["area"]]["top_items"]), proposal["location"])
            self.assertTrue(proposal["fingerprint"].startswith(f"{proposal['kind']}/"), proposal["fingerprint"])
            self.assertIsNone(re.search(r"(line-?[0-9]|\.py|\.ya?ml|[0-9]{3,})", proposal["fingerprint"]), proposal["fingerprint"])
        self.assertEqual(len({f["fingerprint"] for f in report["findings_proposed"]}), len(report["findings_proposed"]))
        props = set(record(pack, "template.health-report")["value"]["schema"]["properties"])
        self.assertFalse({p for p in props if any(w in p for w in ("score", "grade", "percent", "overall"))})
        swallow = self.instance(pack, "example.swallow-scan")
        finding = self.instance(pack, "example.finding")
        location = next(e["location"] for e in finding["evidence"] if e["kind"] == "measurement")
        self.assertIn(location.split("-")[0], {i["location"] for i in swallow["items"]})
        self.assertIn((finding["fingerprint"], location.split("-")[0]), {(f["fingerprint"], f["location"]) for f in report["findings_proposed"]})

    def test_health_review_leaves_wiring_to_its_own_pack(self):
        pack = "codebase-health-review"
        value = record(pack, "health-areas")["value"]
        names = {a["area"] for a in value["areas"]}
        self.assertFalse({n for n in names if any(w in n for w in ("unused", "dark", "mock", "probe", "wiring"))})
        elsewhere = {v for row in value["elsewhere"] for v in row["verbs"]}
        self.assertLessEqual({"wiring-and-conformance-checks.find-unused-modules", "wiring-and-conformance-checks.map-behaviors-to-tests",
                              "wiring-and-conformance-checks.check-health-probes"}, elsewhere)
        pinned = {p["key"] for p in task(f"{pack}.review-tests-and-errors")["brief"]["inputs"]["pinned"]}
        self.assertIn(key("wiring-and-conformance-checks", "rules.behavior-coverage"), pinned)
        self.assertIn("conformance_report", task(f"{pack}.write-health-report")["brief"]["slot_specs"])

    def test_test_cases_expect_outcomes_their_verbs_can_return(self):
        for pack in self.PACKS:
            own = {item["brief"]["template_id"] for item in IDX.docs[pack]["verbs.json"]["tasks"]}
            flow = {step["verb"] for step in record(pack, "pack")["value"]["flow"]}
            self.assertLessEqual(own, flow, f"{pack}: every verb of the pack is in its flow")
            allowed = {o for template_id in flow for o in task(template_id)["brief"]["permitted_outcomes"]}
            for case in record(pack, "test-cases")["value"]["cases"]:
                self.assertIn(case["expected_outcome"], allowed, f"{pack} {case['id']}")

    def test_live_effects_stay_read_only_local_or_sandboxed(self):
        for pack in self.PACKS:
            for item in IDX.docs[pack]["verbs.json"]["tasks"]:
                execution = item["brief"]["execution"]
                self.assertIn(execution["network"]["mode"], ("none", "read_only", "local_only", "sandbox_packages"), item["brief"]["template_id"])
                self.assertEqual(execution["external_effects"], "none")
                self.assertFalse(item["brief"]["review"]["publication_permitted"])


if __name__ == "__main__":
    unittest.main()
