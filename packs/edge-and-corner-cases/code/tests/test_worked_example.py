"""Recompute this pack's worked examples from source.json, and keep the label nouns equal to the code."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from edge_cases import LABELS, generate

PACK = Path(__file__).resolve().parents[2]
SOURCE = json.loads((PACK / "source.json").read_text(encoding="utf-8"))
NOUNS = {noun["slug"]: noun["value"] for noun in SOURCE["nouns"]}
PLAN = NOUNS["example.edge-plan"]["instance"]
CASE_SET = NOUNS["example.case-set"]["instance"]


class WorkedExample(unittest.TestCase):
    def setUp(self) -> None:
        self.run_ = generate(PLAN["kinds"], PLAN["seed"], {k: {n: v for n, v in limits.items()} for k, limits in PLAN["limits"].items()})
        self.cases = {case["id"]: case for case in self.run_["cases"]}

    def test_the_case_set_regenerates_exactly(self) -> None:
        self.assertEqual((CASE_SET["seed"], CASE_SET["kinds"], CASE_SET["limits"]), (PLAN["seed"], PLAN["kinds"], PLAN["limits"]))
        self.assertEqual(CASE_SET["count"], self.run_["count"])
        self.assertEqual(CASE_SET["cases_sha256"], self.run_["cases_sha256"])
        groups = {kind: dict(sorted(Counter(c["group"] for c in self.run_["cases"] if c["kind"] == kind).items())) for kind in PLAN["kinds"]}
        self.assertEqual(CASE_SET["by_group"], groups)
        self.assertEqual(CASE_SET["generator"]["code"], {"$code": "edge-and-corner-cases"}, "the build pins the code's digest")

    def test_picked_cases_and_result_rows_are_the_generated_ones(self) -> None:
        picked = {p["id"]: p for p in CASE_SET["picked"]}
        for p in picked.values():
            case = self.cases[p["id"]]
            self.assertEqual((p["label"], p["escaped"], p["sha256"]), (case["label"], case["escaped"], case["sha256"]), p["id"])
        results = NOUNS["example.case-results"]["instance"]
        self.assertEqual({row["case_id"] for row in results["rows"]}, set(picked))
        for row in results["rows"]:
            self.assertEqual((row["label"], row["input_escaped"]), (picked[row["case_id"]]["label"], picked[row["case_id"]]["escaped"]))
        self.assertEqual(results["generator"]["seed"], PLAN["seed"])

    def test_every_generated_label_the_plan_runs_is_real_and_expected(self) -> None:
        runs = [label for c in PLAN["chosen"] for label in c["run"] if label.split(".")[0] in PLAN["kinds"]]
        self.assertTrue(runs)
        for label in runs:
            self.assertIn(label, LABELS)
            matches = [x for x in PLAN["expectations"] if x["labels"] == label or (x["labels"].endswith(".") and label.startswith(x["labels"]))]
            self.assertTrue(matches, label)

    def test_the_finding_reproduces_from_its_case(self) -> None:
        finding = NOUNS["example.finding"]["instance"]
        case = next(c for c in self.run_["cases"] if c["label"] == "dates.dst.gap-us")
        reproduction = next(e for e in finding["evidence"] if e["kind"] == "reproduction")
        self.assertIn(case["id"], reproduction["detail"])
        self.assertIn(case["escaped"], reproduction["location"])
        self.assertEqual(case["value"], "2026-03-08T02:30:00")
        self.assertEqual(case["context"]["zone"], "America/New_York")

    def test_label_nouns_equal_the_code(self) -> None:
        for kind in ("strings", "numbers", "dates", "lists", "bodies"):
            noun = NOUNS[f"labels.{kind}"]
            expected = {label: {k: spec[k] for k in ("group", "why", "expect")} for label, spec in LABELS.items() if spec["kind"] == kind}
            self.assertEqual(noun["labels"], expected, kind)
            self.assertEqual(noun["count"], len(expected), kind)


if __name__ == "__main__":
    unittest.main()
