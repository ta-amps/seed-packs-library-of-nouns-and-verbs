"""The command line reads one folder, prints JSON, sets its exit code by the stated rule and writes nothing."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from health_checks.__main__ import main


def run(*argv: str) -> tuple[int, dict]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, json.loads(out.getvalue())


class CommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.py").write_text("try:\n    x()\nexcept Exception as exc:\n    print(exc)\n# TODO: tidy\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_todos_without_git(self) -> None:
        code, out = run("todos", str(self.root), "--as-of", "2026-10-30", "--no-git")
        self.assertEqual((code, out["count"], out["counts"]["unknown"]), (0, 1, 1))
        code, _ = run("todos", str(self.root), "--no-git", "--fail-on", "stale")
        self.assertEqual(code, 0, "an unknown age is not stale")

    def test_swallowed_exit_codes(self) -> None:
        code, out = run("swallowed", str(self.root))
        self.assertEqual((code, out["counts"]["logged_only"]), (0, 1), "logged only is a watch item")
        code, _ = run("swallowed", str(self.root), "--strict")
        self.assertEqual(code, 1)
        (self.root / "b.py").write_text("try:\n    x()\nexcept:\n    pass\n", encoding="utf-8")
        code, out = run("swallowed", str(self.root))
        self.assertEqual((code, out["act"]), (1, 1))

    def test_unparsed_files_fail_only_in_strict_mode(self) -> None:
        (self.root / "a.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "bad.py").write_text("def f(:\n", encoding="utf-8")
        code, out = run("swallowed", str(self.root))
        self.assertEqual((code, len(out["unparsed"])), (0, 1))
        code, _ = run("swallowed", str(self.root), "--strict")
        self.assertEqual(code, 1)

    def test_a_missing_root_fails_loudly(self) -> None:
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            run("todos", str(self.root / "missing"))

    def test_nothing_is_written(self) -> None:
        before = sorted(p.name for p in self.root.iterdir())
        run("todos", str(self.root), "--no-git")
        run("swallowed", str(self.root))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
