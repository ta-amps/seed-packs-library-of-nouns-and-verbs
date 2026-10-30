"""The command line prints ASCII-only JSON, refuses limits for kinds it was not asked for and writes nothing."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from edge_cases import generate
from edge_cases.__main__ import main


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


class CommandLine(unittest.TestCase):
    def test_generate_matches_the_library_and_is_ascii(self) -> None:
        code, text = run("generate", "--kind", "strings", "--kind", "dates", "--seed", "11", "--max-length", "12")
        self.assertEqual(code, 0)
        self.assertTrue(text.isascii())
        self.assertEqual(json.loads(text), generate(["strings", "dates"], 11, {"strings": {"max_length": 12}}))

    def test_summary_and_seeded(self) -> None:
        _, text = run("generate", "--kind", "lists", "--seed", "2", "--page-size", "3", "--seeded", "0", "--summary")
        out = json.loads(text)
        self.assertEqual(out["limits"], {"lists": {"page_size": 3, "seeded": 0}})
        self.assertFalse(any("value" in case for case in out["cases"]))

    def test_labels(self) -> None:
        _, text = run("labels", "--kind", "bodies")
        out = json.loads(text)
        self.assertTrue(out and all(spec["kind"] == "bodies" for spec in out.values()))

    def test_mistakes_fail_loudly(self) -> None:
        for argv in (["generate", "--kind", "lists", "--seed", "1", "--year", "2030"],
                     ["generate", "--kind", "strings", "--seed", "1", "--max-length", "0"],
                     ["generate", "--kind", "colors", "--seed", "1"],
                     ["generate", "--kind", "strings"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                run(*argv)

    def test_nothing_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            before = sorted(os.listdir(directory))
            cwd = os.getcwd()
            try:
                os.chdir(directory)
                run("generate", "--kind", "bodies", "--seed", "5")
                run("labels")
            finally:
                os.chdir(cwd)
            self.assertEqual(sorted(os.listdir(directory)), before)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
