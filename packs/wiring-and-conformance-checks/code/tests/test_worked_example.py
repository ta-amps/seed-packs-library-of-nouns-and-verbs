"""Recompute this pack's worked examples from source.json, and keep the pack's nouns equal to the code."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from wiring_checks import BEHAVIOR_STATUSES, KINDS, STATUSES, check_behaviors, find_unused, scan_probes, scan_tests

PACKS = Path(__file__).resolve().parents[3]
SOURCE = json.loads((PACKS / "wiring-and-conformance-checks" / "source.json").read_text(encoding="utf-8"))
NOUNS = {noun["slug"]: noun["value"] for noun in SOURCE["nouns"]}
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pantry"


def instance(slug: str) -> dict:
    return NOUNS[slug]["instance"]


class WorkedExamples(unittest.TestCase):
    def test_module_map_is_the_finders_output(self) -> None:
        result = find_unused(FIXTURE / "src", test_paths=[FIXTURE / "tests"], base=FIXTURE)
        self.assertEqual(instance("example.module-map")["result"], result)
        loaded = set(instance("example.module-map")["trace"]["loaded"])
        candidates = {row["module"] for row in result["modules"] if row["status"] == "dynamic_candidate"}
        self.assertEqual(loaded, candidates, "the trace settles every dynamic candidate and loads no gap")

    def test_behavior_map_is_the_mock_scans_output(self) -> None:
        behaviors = json.loads((FIXTURE / "behaviors.json").read_text(encoding="utf-8"))
        example = instance("example.behavior-map")
        self.assertEqual(example["behaviors"], behaviors)
        tests = scan_tests([FIXTURE / "tests"], FIXTURE)
        self.assertEqual(example["scan"], {"tests": tests, "behaviors": check_behaviors(behaviors, tests)})

    def test_probe_report_static_part_is_the_scan_and_hollow_follows(self) -> None:
        example = instance("example.probe-report")
        static = scan_probes(FIXTURE / "src", base=FIXTURE)
        self.assertEqual(example["static"], static)
        passed = [run["probe"] for run in example["runs"] if run["when_stopped"] == "passed"]
        self.assertEqual(example["hollow"], sorted(static["hollow"] + passed))
        for run in example["runs"]:
            kind = next(row["kind"] for row in static["probes"] if row["probe"] == run["probe"])
            self.assertEqual(kind, "calls", "only a probe that calls something needs a stopped run")

    def test_conformance_report_follows_from_the_other_examples(self) -> None:
        report = instance("example.conformance-report")
        modules = instance("example.module-map")["result"]["modules"]
        gaps = {(f["rule"], f["item"]) for f in report["failures"]}
        dark = {row["module"] for row in modules if row["status"] in ("dark", "test_only")}
        self.assertEqual({item for rule, item in gaps if rule == "no-dark-modules"}, dark)
        self.assertEqual({item for rule, item in gaps if rule == "probes-probe"}, set(instance("example.probe-report")["hollow"]))
        coverage = instance("example.behavior-map")["scan"]["behaviors"]
        self.assertEqual({item for rule, item in gaps if rule == "behaviors-on-real-path"},
                         {row["id"] for row in coverage if row["status"] != "real_path"})
        self.assertEqual([row["id"] for row in report["real_path_behaviors"]],
                         [row["id"] for row in coverage if row["status"] == "real_path"])
        trip = instance("example.round-trip-report")
        lost = {f"Config.{row['field']}" for row in trip["fields"] if row["result"] != "survives"}
        self.assertEqual({item for rule, item in gaps if rule == "config-round-trip"} - {"unknown keys"}, lost)
        self.assertEqual(trip["unknown_keys"], "silently_dropped")
        for rule in report["rules"]:
            self.assertEqual(rule["failures"], sum(1 for f in report["failures"] if f["rule"] == rule["rule"]), rule["rule"])
        refs = [f["finding_ref"] for f in report["failures"]]
        self.assertEqual(refs, [f"WF-{n}" for n in range(1, len(refs) + 1)])

    def test_the_finding_cites_the_module_map_digest(self) -> None:
        finding = instance("example.finding")
        canonical = json.dumps(instance("example.module-map"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        measurement = next(e for e in finding["evidence"] if e["kind"] == "measurement")
        self.assertEqual(measurement["sha256"], hashlib.sha256(canonical.encode("utf-8")).hexdigest())
        report = instance("example.conformance-report")
        gap = next(f for f in report["failures"] if f["finding_ref"] == finding["id"])
        self.assertIn(gap["item"], finding["title"])

    def test_the_packs_rule_nouns_match_the_code(self) -> None:
        self.assertEqual(list(NOUNS["rules.live-paths"]["statuses"]), list(STATUSES))
        self.assertEqual(NOUNS["rules.behavior-coverage"]["statuses"], list(BEHAVIOR_STATUSES))
        self.assertEqual(list(NOUNS["rules.health-probes"]["static_kinds"]), list(KINDS))
        commands = " ".join(NOUNS["tool.wiring-checks"]["commands"])
        for command in ("modules", "mocks", "probes"):
            self.assertIn(f"python -m wiring_checks {command}", commands)


if __name__ == "__main__":
    unittest.main()
