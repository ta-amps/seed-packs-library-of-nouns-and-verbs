"""Recompute this pack's worked example from source.json, from the file's bytes to the checked findings."""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from csv_checks import check_charts, flag, numbers_in, profile, read_csv, run_queries, trace_findings, validate

PACK = Path(__file__).resolve().parents[2]
NOUNS = {n["slug"]: n["value"] for n in json.loads((PACK / "source.json").read_text(encoding="utf-8"))["nouns"]}
DATASET = NOUNS["example.dataset"]
REQUEST = NOUNS["example.analysis-request"]["instance"]
RESULTS = NOUNS["example.query-results"]["instance"]
FINDINGS = NOUNS["example.findings"]["instance"]
CHARTS = NOUNS["example.chart-specs"]["instance"]["charts"]


def same(value: object) -> object:
    return json.loads(json.dumps(value))


class WorkedExample(unittest.TestCase):
    def setUp(self) -> None:
        self.data = DATASET["text"].encode("utf-8")
        self.table = read_csv(self.data, REQUEST["dataset"]["delimiter"])
        self.flags = flag(self.table, REQUEST)
        self.by_id = {item["id"]: item["result"] for item in RESULTS["results"]}

    def test_the_bytes_are_pinned(self) -> None:
        digest = hashlib.sha256(self.data).hexdigest()
        self.assertEqual(DATASET["sha256"], digest)
        self.assertEqual(REQUEST["dataset"]["sha256"], digest)
        self.assertEqual(DATASET["rows"], len(self.table.rows))
        for noun in ("example.schema-profile", "example.validation-report", "example.flag-report"):
            self.assertEqual(NOUNS[noun]["instance"]["dataset_sha256"], digest, noun)

    def test_every_step_is_recomputed_exactly(self) -> None:
        self.assertEqual(same(profile(self.table, REQUEST)), NOUNS["example.schema-profile"]["instance"])
        self.assertEqual(same(validate(self.table, REQUEST)), NOUNS["example.validation-report"]["instance"])
        self.assertEqual(same(self.flags), NOUNS["example.flag-report"]["instance"])
        self.assertEqual(same(run_queries(self.table, REQUEST, self.flags, RESULTS["queries"])), RESULTS)

    def test_what_the_example_shows(self) -> None:
        report = NOUNS["example.validation-report"]["instance"]
        self.assertEqual(report["counts"], {"allowed": 1, "max": 1, "min": 1, "required": 1, "type": 2})
        self.assertEqual(report["rows_with_violations"], 6)
        outliers = {o["column"]: o["rows"] for o in self.flags["outliers"]}
        self.assertEqual(outliers, {"meals_served": [19], "volunteers": [], "pounds_received": [12]})
        self.assertEqual(NOUNS["example.schema-profile"]["instance"]["duplicate_rows"], [{"row": 25, "same_as": 23}])

    def test_identifying_values_never_leave_the_file(self) -> None:
        addresses = set(re.findall(r"[a-z-]+@example\.invalid", DATASET["text"]))
        self.assertEqual(len(addresses), 3)
        for slug, value in NOUNS.items():
            if slug != "example.dataset":
                for address in addresses:
                    self.assertNotIn(address, json.dumps(value), slug)

    def test_charts_and_findings_trace_to_the_results(self) -> None:
        self.assertEqual(check_charts(CHARTS, self.by_id), [])
        self.assertEqual(trace_findings(FINDINGS, self.by_id, DATASET["sha256"]), [])
        listed = sum(len(f["numbers"]) for f in FINDINGS["findings"])
        self.assertEqual(listed, sum(len(numbers_in(f["text"])) for f in FINDINGS["findings"]))
        check = NOUNS["example.findings-check"]["instance"]
        self.assertEqual((check["numbers_checked"], check["queries_rerun"], check["charts_checked"]),
                         (listed, len(RESULTS["queries"]), len(CHARTS)))
        self.assertTrue(check["passed"] and check["result_digests_match"] and not check["problems"])

    def test_every_exclusion_is_counted_and_explained(self) -> None:
        excluded = {item["id"]: item["excluded_by_filter"] for item in RESULTS["results"] if item["excluded_by_filter"]}
        self.assertEqual({e["query"]: e["excluded"] for e in FINDINGS["exclusions"]}, excluded)
        for item in RESULTS["results"]:
            self.assertEqual(item["excluded_by_filter"], item["rows_in"] - item["rows_after_filter"], item["id"])

    def test_the_person_decides_on_a_passing_check(self) -> None:
        reading = NOUNS["example.interpretation"]["instance"]
        self.assertTrue(reading["check_passed"])
        self.assertTrue(reading["meaning"].startswith("MADE-UP."))

    def test_the_tool_card_names_this_code(self) -> None:
        card = NOUNS["tool.csv-checks"]
        self.assertEqual(card["code"], {"$code": "checked-data-analysis"})
        for command in card["commands"]:
            self.assertTrue(re.match(r"python -m csv_checks (profile|validate|flag|query|charts|trace) ", command))


if __name__ == "__main__":
    unittest.main()
