"""The command line reads the files it is given, prints JSON and sets its exit code; it writes nothing."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from a11y_checks.__main__ import main

GOOD = ('<!doctype html><html lang="en"><head><title>Page</title></head><body><a href="#main">Skip</a>'
        '<main id="main"><h1>Page</h1><h2>Part</h2></main></body></html>')


def run(*argv: str) -> tuple[int, dict]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, json.loads(out.getvalue())


class CommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_contrast_pair_exit_codes(self) -> None:
        code, out = run("contrast", "#767676", "#ffffff", "--size-px", "16")
        self.assertEqual((code, out["failed"], out["results"][0]["ratio"]), (0, 0, 4.54))
        code, out = run("contrast", "#777777", "#ffffff")
        self.assertEqual((code, out["failed"]), (1, 1))
        code, out = run("contrast", "#949494", "#ffffff", "--non-text")
        self.assertEqual((code, out["results"][0]["sc"]), (0, "1.4.11"))

    def test_contrast_pairs_file(self) -> None:
        pairs = self.dir / "pairs.json"
        pairs.write_text(json.dumps({"pairs": [{"id": "a", "foreground": "#000", "background": "#fff"},
                                               {"id": "b", "foreground": "#aaaaaa", "background": "#ffffff", "size_px": 30}]}))
        code, out = run("contrast", "--pairs", str(pairs))
        self.assertEqual(code, 1)
        self.assertEqual([r["id"] for r in out["results"]], ["a", "b"])
        self.assertEqual(out["failed"], 1)

    def test_bad_input_fails_loudly(self) -> None:
        with self.assertRaises(SystemExit):
            run("contrast", "#zzzzzz", "#ffffff")
        with self.assertRaises(SystemExit):
            run("contrast")

    def test_structure_exit_codes_and_strict(self) -> None:
        good, skipped = self.dir / "good.html", self.dir / "skipped.html"
        good.write_text(GOOD, encoding="utf-8")
        skipped.write_text(GOOD.replace("<h2>Part</h2>", "<h4>Deep</h4>"), encoding="utf-8")
        code, out = run("structure", str(good), str(skipped))
        self.assertEqual(code, 0, "advisories alone do not fail")
        self.assertEqual(out[str(skipped)]["advisories"], 1)
        code, _ = run("structure", str(skipped), "--strict")
        self.assertEqual(code, 1)
        nolang = self.dir / "nolang.html"
        nolang.write_text(GOOD.replace(' lang="en"', ""), encoding="utf-8")
        code, out = run("structure", str(nolang))
        self.assertEqual((code, out[str(nolang)]["failures"]), (1, 1))

    def test_nothing_is_written(self) -> None:
        page = self.dir / "page.html"
        page.write_text(GOOD, encoding="utf-8")
        before = sorted(p.name for p in self.dir.iterdir())
        run("structure", str(page))
        run("contrast", "#000000", "#ffffff")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
