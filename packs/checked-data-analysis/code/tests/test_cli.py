"""The command line on the worked example, in a temporary folder."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from csv_checks.__main__ import main

PACK = Path(__file__).resolve().parents[2]
NOUNS = {n["slug"]: n["value"] for n in json.loads((PACK / "source.json").read_text(encoding="utf-8"))["nouns"]}


def run(*argv: str) -> tuple[int, object]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, json.loads(out.getvalue())


class CommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        csv_path = self.dir / "data.csv"
        csv_path.write_bytes(NOUNS["example.dataset"]["text"].encode("utf-8"))
        self.base = ["--csv", str(csv_path), "--request", self.write("request.json", NOUNS["example.analysis-request"]["instance"])]
        self.results = NOUNS["example.query-results"]["instance"]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, value: object) -> str:
        path = self.dir / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return str(path)

    def test_each_step_reproduces_its_example(self) -> None:
        for command, slug in (("profile", "example.schema-profile"), ("validate", "example.validation-report"),
                              ("flag", "example.flag-report")):
            with self.subTest(command=command):
                self.assertEqual(run(command, *self.base), (0, NOUNS[slug]["instance"]))
        queries = self.write("queries.json", {"queries": self.results["queries"]})
        self.assertEqual(run("query", *self.base, "--queries", queries), (0, self.results))

    def test_charts_and_trace_pass_then_fail_when_a_number_is_changed(self) -> None:
        results = self.write("results.json", self.results)
        charts = self.write("charts.json", NOUNS["example.chart-specs"]["instance"])
        findings = NOUNS["example.findings"]["instance"]
        self.assertEqual(run("charts", "--charts", charts, "--results", results), (0, {"problems": []}))
        self.assertEqual(run("trace", "--findings", self.write("f.json", findings), "--results", results), (0, {"problems": []}))
        changed = copy.deepcopy(findings)
        changed["findings"][0]["numbers"][0]["value"] += 1
        code, out = run("trace", "--findings", self.write("g.json", changed), "--results", results)
        self.assertEqual(code, 1)
        self.assertTrue(out["problems"])


if __name__ == "__main__":
    unittest.main()
