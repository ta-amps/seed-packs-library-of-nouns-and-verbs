"""The command line on the worked example, in a temporary folder."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from promotion_check.__main__ import main

PACK = Path(__file__).resolve().parents[2]
NOUNS = {n["slug"]: n["value"] for n in json.loads((PACK / "source.json").read_text(encoding="utf-8"))["nouns"]}


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


class CommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, value: object) -> str:
        path = self.dir / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return str(path)

    def test_decide_reproduces_round_two(self) -> None:
        inputs = NOUNS["example.evaluations"]["round_2"]
        code, out = run("decide", "--rule", self.write("rule.json", NOUNS["rule.tool-call-specialist-v1"]["instance"]),
                        "--evaluations", self.write("evals.json", inputs),
                        "--integrity", self.write("integrity.json", inputs["integrity"]))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), NOUNS["example.decision-round-2"]["instance"])

    def test_bootstrap_and_digest(self) -> None:
        inputs = NOUNS["example.evaluations"]["round_1"]
        pairs = {"candidate": inputs["candidate"]["test"]["exact"], "champion": inputs["champion"]["test"]["exact"]}
        code, out = run("bootstrap", "--pairs", self.write("pairs.json", pairs))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), NOUNS["example.decision-round-1"]["instance"]["paired_test"])
        code, out = run("digest", self.write("rule.json", NOUNS["rule.tool-call-specialist-v1"]["instance"]))
        self.assertEqual(out.strip(), "bf0fa821717c2400faab77652f067ea85f2616eea329c6e139af33a423e4b3b7")

    def test_receipt_passes_then_fails_when_scored_first(self) -> None:
        receipt = NOUNS["example.frozen-test-receipt"]
        rows = self.dir / "rows.jsonl"
        rows.write_text("".join(json.dumps(r) + "\n" for r in NOUNS["example.frozen-test-rows"]["rows"]), encoding="utf-8")
        path = self.write("receipt.json", receipt["instance"])
        self.assertEqual(run("receipt", "--receipt", path, "--rows", str(rows), "--first-scored-at",
                             receipt["first_scored_at"])[0], 0)
        code, out = run("receipt", "--receipt", path, "--rows", str(rows), "--first-scored-at", "2026-10-29T13:00:00Z")
        self.assertEqual(code, 1)
        self.assertTrue(json.loads(out)["problems"])


if __name__ == "__main__":
    unittest.main()
