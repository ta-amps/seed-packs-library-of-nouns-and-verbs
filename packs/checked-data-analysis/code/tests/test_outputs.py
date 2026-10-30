"""Chart specs kept as data, and findings whose numbers trace to query results."""

from __future__ import annotations

import copy
import unittest

from csv_checks import VEGA_LITE_V5, check_chart, numbers_in, trace_findings

RESULTS = {"q-by-team": [{"team": "a", "total": 30, "mean": 15.0}, {"team": "b", "total": 70, "mean": 35.0}]}
SPEC = {
    "title": "Total by team", "description": "Totals per team from q-by-team.",
    "usermeta": {"query": "q-by-team", "vega_lite": "v5"}, "data": {"values": copy.deepcopy(RESULTS["q-by-team"])},
    "mark": "bar",
    "encoding": {"x": {"field": "team", "type": "nominal", "title": "Team"},
                 "y": {"field": "total", "type": "quantitative", "title": "Total (points)"}},
}
FINDINGS = {
    "dataset_sha256": "a" * 64,
    "findings": [{"text": "Team b scored 70 points, a mean of 35.0 over the 2026-01-05 week.",
                  "numbers": [{"value": 70, "query": "q-by-team", "row": 1, "column": "total"},
                              {"value": 35.0, "query": "q-by-team", "row": 1, "column": "mean"}]}],
}


class Charts(unittest.TestCase):
    def test_a_good_spec_passes_with_or_without_its_schema_url(self) -> None:
        self.assertEqual(check_chart(SPEC, RESULTS), [])
        self.assertEqual(check_chart({**SPEC, "$schema": VEGA_LITE_V5}, RESULTS), [])

    def test_each_problem_is_named(self) -> None:
        cases = {
            "version": lambda s: s["usermeta"].update(vega_lite="v4"),
            "description is missing": lambda s: s.update(description=""),
            "never a URL": lambda s: s["data"].update(url="https://example.invalid/data.csv"),
            "does not name": lambda s: s["usermeta"].update(query="q-other"),
            "differ from": lambda s: s["data"]["values"][0].update(total=31),
            "mark is one of": lambda s: s.update(mark="arc"),
            "not in every data row": lambda s: s["encoding"]["y"].update(field="median"),
            "names its unit": lambda s: s["encoding"]["y"].pop("title"),
            "starts at zero": lambda s: s["encoding"]["y"].update(scale={"zero": False}),
            "needs x and y": lambda s: s["encoding"].pop("x"),
        }
        for words, change in cases.items():
            spec = copy.deepcopy(SPEC)
            change(spec)
            with self.subTest(problem=words):
                self.assertTrue(any(words in p for p in check_chart(spec, RESULTS)), check_chart(spec, RESULTS))
        self.assertTrue(check_chart({**SPEC, "$schema": "https://vega.github.io/schema/vega-lite/v4.json"}, RESULTS))


class Trace(unittest.TestCase):
    def test_numbers_in_prose_skip_dates_times_and_labels(self) -> None:
        self.assertEqual(numbers_in("On 2026-01-05 at 10:30, the 30-day mean was 35.0 of 70 points, 1.5x."), ["35.0", "70"])

    def test_traced_findings_pass(self) -> None:
        self.assertEqual(trace_findings(FINDINGS, RESULTS, "a" * 64), [])

    def test_each_problem_is_found(self) -> None:
        cases = {
            "not the pinned dataset": lambda f: f.update(dataset_sha256="b" * 64),
            "unknown query": lambda f: f["findings"][0]["numbers"][0].update(query="q-missing"),
            "has no row": lambda f: f["findings"][0]["numbers"][0].update(row=5),
            "differs from": lambda f: f["findings"][0]["numbers"][0].update(value=71),
            "is not a listed number": lambda f: f["findings"][0].update(text=f["findings"][0]["text"] + " It grew 12 percent."),
        }
        for words, change in cases.items():
            findings = copy.deepcopy(FINDINGS)
            change(findings)
            with self.subTest(problem=words):
                self.assertTrue(any(words in p for p in trace_findings(findings, RESULTS, "a" * 64)))


if __name__ == "__main__":
    unittest.main()
