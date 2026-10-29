"""Seed-pack library checks: determinism, offline builds, authority limits and worked examples.

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


def record(key: str) -> dict:
    for files in IDX.docs.values():
        for item in files["nouns.json"]["records"]:
            if item["key"] == key:
                return copy.deepcopy(item)
    raise KeyError(key)


def task(template_id: str) -> dict:
    for files in IDX.docs.values():
        for item in files["verbs.json"]["tasks"]:
            if item["brief"]["template_id"] == template_id:
                return copy.deepcopy(item)
    raise KeyError(template_id)


def check_record(item: dict) -> None:
    vp.check_record(item, item["value"]["pack"], IDX.contract, IDX.targets)


def check_task(item: dict) -> None:
    vp.check_task(item, item["brief"]["pack"], IDX.contract, IDX.pins, IDX.targets, IDX.templates)


def rekey(item: dict) -> dict:
    """Recompute a template's idempotency key so a test isolates one other change."""
    slug = item["brief"]["template_id"].split(".", 1)[1]
    item["idempotency_key"] = bp.template_idempotency_key(item["brief"]["pack"], slug, item["queue"], item["kind"], item["brief"])
    return item


class LibraryChecks(unittest.TestCase):
    def test_every_pack_validates(self):
        summary = vp.validate_library(ROOT)
        self.assertEqual(summary["packs"], len(PACKS))
        self.assertGreaterEqual(summary["packs"], 8)
        self.assertEqual(summary["nouns"], sum(len(IDX.docs[p]["nouns.json"]["records"]) for p in PACKS))
        self.assertEqual(summary["verbs"], sum(len(IDX.docs[p]["verbs.json"]["tasks"]) for p in PACKS))
        self.assertEqual(summary["worked_examples"], 4)
        self.assertTrue(summary["offline_only"])
        self.assertIsNone(summary["live_evaluation"])

    def test_required_packs_present(self):
        for pack in ("repo-review", "video-showcase", "tool-discovery", "evaluation-design", "checks-of-checks",
                     "decomposition-patterns", "taste-palettes", "harness-onboarding-e2e", "security-review",
                     "cost-optimization", "docs-improvement"):
            self.assertIn(pack, PACKS)

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
        bank = record("repo-review.question-bank")["value"]
        self.assertEqual({q["pin"]["key"] for q in bank["questions"]}, {q["key"] for q in questions})

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
            "blocked=('socket.','subprocess.','os.system','os.exec','os.posix_spawn','os.fork','urllib.','http.client','ctypes')\n"
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

    def test_receipt_covers_current_payloads(self):
        receipt = json.loads((ROOT / "packs" / "VALIDATION.json").read_text())
        self.assertEqual(receipt["errors"], [])
        self.assertEqual(set(receipt["packs"]), set(PACKS))
        self.assertTrue(all(v == "rejected" for v in receipt["negative_probes"].values()))
        for name in ("network_requests", "model_calls", "records_written", "tasks_enqueued"):
            self.assertEqual(receipt[name], 0)
        counts = receipt["checks"]
        total_nouns = sum(len(IDX.docs[p]["nouns.json"]["records"]) for p in PACKS)
        total_verbs = sum(len(IDX.docs[p]["verbs.json"]["tasks"]) for p in PACKS)
        for name in ("RecordWrite", "canonical_category_tags_strict", "noun_validate_category_payload", "value_sha256"):
            self.assertEqual(counts[name], total_nouns)
        for name in ("TaskSpec", "verb_validate_category_payload", "normalize_report", "shape_hash", "instantiated_TaskSpec"):
            self.assertEqual(counts[name], total_verbs)

    def test_stale_receipt_is_detected(self):
        built = copy.deepcopy(IDX.built)
        built["repo-review"]["nouns.json"] += b" "
        with self.assertRaises(bp.PackError):
            vp.check_receipt(ROOT, built)


class VerbTemplateChecks(unittest.TestCase):
    def test_every_template_offers_unknown_and_no_change(self):
        for pack in PACKS:
            for item in IDX.docs[pack]["verbs.json"]["tasks"]:
                brief = item["brief"]
                self.assertIn("no_change", brief["permitted_outcomes"])
                self.assertIn("unknown", brief["permitted_outcomes"])
                self.assertEqual(brief["outcome_requirements"]["unknown"], ["unknowns"])
                self.assertEqual(brief["outcome_requirements"]["no_change"], ["no_change_reason"])

    def test_every_template_has_typed_io_checks_and_report(self):
        for pack in PACKS:
            for item in IDX.docs[pack]["verbs.json"]["tasks"]:
                brief = item["brief"]
                report = brief["execution_report"]
                self.assertEqual(report["template"]["contract"], {"input_schema": brief["input_schema"], "output_schema": brief["output_schema"]})
                self.assertEqual(report["shape_sha256"], bp.shape_sha256(brief["input_schema"], brief["output_schema"]))
                self.assertIn("run_notes", brief["output_schema"]["properties"])
                self.assertEqual(set(brief["output_schema"]["properties"]["run_notes"]["properties"]),
                                 {"went_right", "went_wrong", "next_steps", "ideas"})
                self.assertTrue(brief["acceptance_checks"])
                self.assertFalse(brief["execution"]["server_fallback"])
                self.assertEqual(brief["execution"]["maximum_automatically_enqueued_children"], 0)

    def test_instantiate_fills_slots_and_changes_identity(self):
        template = task("repo-review.profile-repo")
        pin = {"store": "seedpack.repo-review", "key": "repo-review.example.repo-snapshot", "version": 1,
               "value_sha256": IDX.pins[("seedpack.repo-review", "repo-review.example.repo-snapshot")]}
        instance = bp.instantiate(template, {"repo_snapshot": pin}, {})
        self.assertEqual(instance["brief"]["inputs"]["slots"]["repo_snapshot"], pin)
        self.assertEqual(instance["brief"]["instantiation"]["status"], "instance")
        self.assertNotEqual(instance["idempotency_key"], template["idempotency_key"])
        self.assertTrue(instance["idempotency_key"].startswith("seedpack:repo-review:profile-repo:"))
        self.assertEqual(vp.schema_errors(instance["brief"]["input_schema"], instance["brief"]["inputs"]), [])
        self.assertEqual(bp.instantiate(template, {"repo_snapshot": pin}, {}), instance)
        self.assertEqual(template, task("repo-review.profile-repo"))

    def test_instantiate_refuses_missing_or_malformed_pins(self):
        template = task("repo-review.investigate-family")
        good = {"store": "s", "key": "k", "version": 1, "value_sha256": "0" * 64}
        with self.assertRaises(bp.PackError):
            bp.instantiate(template, {"repo_profile": good}, {"family": "cost"})
        with self.assertRaises(bp.PackError):
            bp.instantiate(template, {"repo_profile": good, "review_plan": {**good, "version": 0}}, {"family": "cost"})
        with self.assertRaises(bp.PackError):
            bp.instantiate(template, {"repo_profile": good, "review_plan": good}, {})
        with self.assertRaises(bp.PackError):
            bp.instantiate(template, {"repo_profile": good, "review_plan": good, "extra": good}, {"family": "cost"})
        for params in ({"family": "nonsense"}, {"family": "cost", "allow_sandboxed_runs": "yes"},
                       {"family": "cost", "output_store": "Bad Store"}):
            with self.subTest(params=params), self.assertRaises(bp.PackError):
                bp.instantiate(template, {"repo_profile": good, "review_plan": good}, params)
        instance = bp.instantiate(template, {"repo_profile": good, "review_plan": good}, {"family": "cost"})
        with self.assertRaises(bp.PackError):
            bp.instantiate(instance, {}, {})

    def test_human_verbs_use_no_model(self):
        humans = [t for p in PACKS for t in IDX.docs[p]["verbs.json"]["tasks"] if t["brief"]["claimant"] == "human"]
        self.assertGreaterEqual(len(humans), 3)
        for item in humans:
            self.assertEqual(item["brief"]["execution"]["model_use"], "none")


class NegativeChecks(unittest.TestCase):
    def assert_record_rejected(self, mutate):
        item = record("repo-review.question.cost.ci-minutes")
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
        check_record(record("repo-review.question.cost.ci-minutes"))
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
            lambda r: r.update(allowed_surfaces=["surface:other"]),
            lambda r: r.update(expected_version=1),
            lambda r: r["tags"].append("status:verified"),
            lambda r: r["tags"].append("category:noun.code_node"),
            lambda r: r["value"].update(kind="verb.solve_draft"),
            lambda r: r["value"].update(status="admitted"),
            lambda r: r["value"].update(trials=3, successes=3),
            lambda r: r["value"]["dimension_basis"].update(measured=True),
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
            lambda t: t["brief"]["review"].update(self_approval_permitted=True),
            lambda t: t["brief"]["review"].update(publication_permitted=True),
            lambda t: t["brief"]["review"].update(admission_permitted=True),
            lambda t: t["brief"]["output_contract"].update(visibility_scope="public_commons"),
            lambda t: t["brief"]["output_contract"].update(expected_version=3),
            lambda t: t["brief"]["dimensions"].update(evidence_grounding=1.0),
            lambda t: t["brief"]["relations"].pop(),
            lambda t: t["brief"]["acceptance_checks"].clear(),
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

    def test_human_sensitive_kind_needs_a_person(self):
        self.assert_task_rejected(lambda t: t["brief"].update(claimant="agent") or t["tags"].__setitem__(
            t["tags"].index("claimant:human"), "claimant:agent"), template_id="taste-palettes.record-choice")

    def test_human_claimant_cannot_use_a_model(self):
        self.assert_task_rejected(lambda t: t["brief"]["execution"].update(model_use="worker_allowance"),
                                  template_id="video-showcase.record-narration")

    def test_compare_and_set_names_its_slot(self):
        check_task(task("decomposition-patterns.record-outcome"))
        self.assert_task_rejected(lambda t: t["brief"]["output_contract"].update(expected_version={"from_slot": "missing"}),
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
                    good + "\n" * 100):
            with self.assertRaises(bp.PackError):
                vp.check_readme(bad, "Repository review", "repo-review")

    def test_template_examples_must_match_their_schemas(self):
        item = record("repo-review.template.finding")
        check_record(item)
        item["value"]["example"]["verdict"] = "maybe"
        with self.assertRaises(bp.PackError):
            check_record(item)


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
            lambda s: s["nouns"][1]["value"].update(flow={"$verb": "repo-review.not-a-verb"}),
            lambda s: s["nouns"][1]["value"].update(extra={"$pin": "not-a-noun"}),
            lambda s: s["nouns"][1]["value"].update(extra={"$pin": "video-showcase:style-guide"}),
            lambda s: s["nouns"][1]["value"].update(extra={"$include": "file"}),
            lambda s: s["nouns"].append(copy.deepcopy(s["nouns"][1])),
            lambda s: s["nouns"][0].update(slug="descriptor"),
            lambda s: s["verbs"][0].update(claimant="robot"),
            lambda s: s["verbs"][0].update(ready_outcome="unknown"),
            lambda s: s["verbs"][0].update(produces=[]),
            lambda s: s["verbs"][0].update(bounds={"max_attempts": -1}),
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
        value = record("repo-review.evidence-standard")["value"]
        results = vp.run_finding_checks(value)
        self.assertEqual(results, value["expected"])
        for fixture in value["golden_fixtures"]:
            verdict = results[fixture["id"]]["verdict"]
            self.assertEqual(verdict, "pass" if fixture["label"] == "known_good" else "fail")

    def test_check_validation_rejects_wrong_and_weak_checks(self):
        value = record("checks-of-checks.example.source-card-checks")["value"]
        results = vp.run_check_validation(value)
        self.assertEqual(results, value["expected"])
        self.assertEqual(results["verdicts"]["github-only"], "reject")
        self.assertEqual(results["verdicts"]["topics-listed"], "revise")
        self.assertFalse(results["caught"]["empty-topic@good-arxiv"])

    def test_evaluation_arithmetic_reports_missed_and_unknown_marks(self):
        value = record("evaluation-design.example.worked")["value"]
        results = vp.run_evaluation_arithmetic(value)
        self.assertEqual(results, value["expected"])
        self.assertEqual(results["marks"]["M3"], "missed")
        self.assertEqual(results["marks"]["M5"], "unknown")
        self.assertEqual(results["metrics"]["A1-2"]["errors"], 1)

    def test_security_findings_must_stay_local_and_masked(self):
        value = record("security-review.severity-rubric")["value"]
        results = vp.run_finding_checks(value)
        self.assertEqual(results, value["expected"])
        self.assertEqual(results["bad-live-target"]["failed_checks"], ["local-only"])
        self.assertEqual(results["good-reasoned"]["verdict"], "pass")

    def test_doc_counts_must_match_the_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("README.md", "docs/status.md", "packs/README.md"):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / name, root / name)
            vp.check_doc_counts(root, IDX)
            text = (root / "README.md").read_text().replace("verb templates were", "verb templates (stale) were")
            (root / "README.md").write_text(text.replace(" nouns and ", " nouns and 1", 1))
            with self.assertRaises(bp.PackError):
                vp.check_doc_counts(root, IDX)

    def test_tampered_expectations_fail(self):
        for key in ("repo-review.evidence-standard", "checks-of-checks.example.source-card-checks", "evaluation-design.example.worked",
                    "security-review.severity-rubric"):
            item = record(key)
            expected = item["value"]["expected"]
            first = next(iter(expected))
            expected[first] = {"tampered": True}
            with self.subTest(key=key), self.assertRaises(bp.PackError):
                vp.check_fixtures([item])


if __name__ == "__main__":
    unittest.main()
