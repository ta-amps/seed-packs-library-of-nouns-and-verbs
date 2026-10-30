"""The command line: JSON on stdout, exit codes, and nothing run, written or sent."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from wiring_checks.__main__ import main

CODE = Path(__file__).resolve().parents[1]
FIXTURE = CODE / "tests" / "fixtures" / "pantry"


def run_cli(*args: str) -> tuple[int, dict]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(list(args))
    return code, json.loads(out.getvalue())


class Modules(unittest.TestCase):
    def test_dark_modules_fail_and_a_missing_entry_is_a_usage_error(self) -> None:
        code, result = run_cli("modules", str(FIXTURE / "src"), "--tests", str(FIXTURE / "tests"), "--base", str(FIXTURE))
        self.assertEqual((code, result["counts"]["dark"]), (1, 2))
        code, result = run_cli("modules", str(FIXTURE / "src"), "--entry", "pantry_app.server", "--base", str(FIXTURE))
        self.assertEqual((code, result["missing_entries"]), (2, ["pantry_app.server"]))

    def test_strict_also_fails_modules_only_tests_reach(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel, text in {"app/__init__.py": "from . import a\n", "app/a.py": "", "app/b.py": "",
                              "tests/test_b.py": "from app import b\n"}.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(text, encoding="utf-8")
            args = ("modules", str(root), "--package", "app", "--tests", str(root / "tests"))
            self.assertEqual(run_cli(*args)[0], 0)
            self.assertEqual(run_cli(*args, "--strict")[0], 1)

    def test_an_unknown_package_stops(self) -> None:
        with self.assertRaises(SystemExit):
            run_cli("modules", str(FIXTURE / "src"), "--package", "nothing_here")


class MocksAndProbes(unittest.TestCase):
    def test_mocks_fail_on_mock_only_and_untested_behaviors(self) -> None:
        code, result = run_cli("mocks", str(FIXTURE / "tests"), "--base", str(FIXTURE), "--behaviors",
                               str(FIXTURE / "behaviors.json"))
        self.assertEqual(code, 1)
        self.assertEqual([row["status"] for row in result["behaviors"]], ["mock_only", "mock_only", "real_path", "untested"])
        clean = [row for row in json.loads((FIXTURE / "behaviors.json").read_text(encoding="utf-8")) if row["id"] == "B3"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.json"
            path.write_text(json.dumps({"behaviors": clean}), encoding="utf-8")
            code, result = run_cli("mocks", str(FIXTURE / "tests"), "--base", str(FIXTURE), "--behaviors", str(path))
        self.assertEqual((code, [row["status"] for row in result["behaviors"]]), (0, ["real_path"]))
        code, result = run_cli("mocks", str(FIXTURE / "tests"), "--base", str(FIXTURE))
        self.assertEqual((code, "behaviors" in result, len(result["tests"])), (0, False, 6))

    def test_probes_fail_when_one_is_hollow(self) -> None:
        code, result = run_cli("probes", str(FIXTURE / "src"), "--base", str(FIXTURE))
        self.assertEqual((code, len(result["hollow"])), (1, 3))
        code, result = run_cli("probes", str(FIXTURE / "src"), str(FIXTURE / "src" / "pantry_app" / "store.py"))
        self.assertEqual((code, result["probes"]), (0, []))


class NothingRunsOrWrites(unittest.TestCase):
    def test_no_process_socket_or_write(self) -> None:
        script = textwrap.dedent(f"""
            import sys
            blocked = ("socket.", "subprocess.", "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.remove",
                       "os.rename", "shutil.", "urllib.Request", "http.client")
            def hook(event, args):
                if event.startswith(blocked):
                    raise RuntimeError("forbidden " + event)
                if event == "open" and len(args) > 1 and isinstance(args[1], str) and any(m in args[1] for m in "wax+"):
                    raise RuntimeError("write attempted " + str(args[0]))
            sys.addaudithook(hook)
            sys.dont_write_bytecode = True
            from wiring_checks.__main__ import main
            fixture = {str(FIXTURE)!r}
            codes = [main(["modules", fixture + "/src", "--tests", fixture + "/tests", "--base", fixture]),
                     main(["mocks", fixture + "/tests", "--base", fixture, "--behaviors", fixture + "/behaviors.json"]),
                     main(["probes", fixture + "/src", "--base", fixture])]
            print("CODES", codes, file=sys.stderr)
        """)
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=CODE, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CODES [1, 1, 1]", result.stderr)


if __name__ == "__main__":
    unittest.main()
