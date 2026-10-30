"""The command line on the worked example, in a temporary folder."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from chain_measures.__main__ import main

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
        self.args = []
        for flag, slug in (("--request", "example.review-request"), ("--snapshot", "example.chain-snapshot"),
                           ("--history", "example.iv-history")):
            self.args += [flag, self.write(slug + ".json", NOUNS[slug]["instance"])]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, value: object) -> str:
        path = self.dir / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return str(path)

    def test_each_command_reproduces_its_example(self) -> None:
        self.assertEqual(run("check", *self.args), (0, {"problems": []}))
        for command, slug in (("measures", "example.chain-measures"), ("screen", "example.liquidity-screen"),
                              ("candidates", "example.roll-candidates")):
            with self.subTest(command=command):
                self.assertEqual(run(command, *self.args), (0, NOUNS[slug]["instance"]))

    def test_iv_rank(self) -> None:
        code, out = run("iv-rank", "--history", self.args[5])
        expected = dict(NOUNS["example.chain-measures"]["instance"]["iv_rank"])
        expected.pop("measure")
        self.assertEqual((code, out), (0, expected))

    def test_a_snapshot_with_a_brokerage_connection_is_refused(self) -> None:
        snapshot = copy.deepcopy(NOUNS["example.chain-snapshot"]["instance"])
        snapshot["source"]["brokerage_connection"] = True
        args = list(self.args)
        args[3] = self.write("bad.json", snapshot)
        for command in ("check", "measures"):
            code, out = run(command, *args)
            self.assertEqual(code, 1)
            self.assertTrue(any("brokerage" in p for p in out["problems"]))


if __name__ == "__main__":
    unittest.main()
