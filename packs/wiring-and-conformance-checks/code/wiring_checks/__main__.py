"""Command line for the wiring checks. Reads only the files it is given and prints JSON.

  python -m wiring_checks modules ROOT [--package NAME] [--entry MODULE] [--tests PATH] [--pyproject FILE]
                                       [--base DIR] [--strict]
  python -m wiring_checks mocks PATH [PATH ...] [--behaviors FILE] [--base DIR]
  python -m wiring_checks probes ROOT [PATH ...] [--names REGEX] [--base DIR]

modules exits 1 when a module is dark (with --strict, also when one is reached only from tests) and 2
when a named entry point is not a module under ROOT. mocks exits 1 when a behavior in the map is
mock_only or untested. probes exits 1 when a probe is hollow. Nothing is written and no network is used.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .mocks import check_behaviors, scan_tests
from .modules import find_unused
from .probes import PROBE_NAMES, scan_probes


def _print(result: dict) -> None:
    print(json.dumps(result, indent=1, ensure_ascii=False))


def cmd_modules(args: argparse.Namespace) -> int:
    try:
        result = find_unused(args.root, args.package or None, args.entry or None, args.tests or None,
                             args.pyproject, args.base)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    _print(result)
    if result["missing_entries"]:
        return 2
    failing = {"dark", "test_only"} if args.strict else {"dark"}
    return 1 if any(row["status"] in failing for row in result["modules"]) else 0


def cmd_mocks(args: argparse.Namespace) -> int:
    tests = scan_tests(args.paths, args.base or Path.cwd())
    result: dict = {"tests": tests}
    if args.behaviors:
        behaviors = json.loads(args.behaviors.read_text(encoding="utf-8"))
        if isinstance(behaviors, dict):
            behaviors = behaviors.get("behaviors", [])
        result["behaviors"] = check_behaviors(behaviors, tests)
    _print(result)
    return 1 if any(row["status"] != "real_path" for row in result.get("behaviors", [])) else 0


def cmd_probes(args: argparse.Namespace) -> int:
    result = scan_probes(args.root, args.paths or None, args.names, args.base)
    _print(result)
    return 1 if result["hollow"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wiring_checks", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    modules = sub.add_parser("modules", help="modules no live path imports")
    modules.add_argument("root", type=Path, help="the folder that holds the top-level packages, such as src")
    modules.add_argument("--package", action="append", help="a top-level package to check; default: all")
    modules.add_argument("--entry", action="append", help="an entry point module, or module:function")
    modules.add_argument("--tests", action="append", type=Path, help="a test file or folder outside the packages")
    modules.add_argument("--pyproject", type=Path, help="read entry points from this pyproject.toml")
    modules.add_argument("--base", type=Path, help="show paths relative to this folder; default: ROOT")
    modules.add_argument("--strict", action="store_true", help="modules reached only from tests fail too")
    modules.set_defaults(func=cmd_modules)
    mocks = sub.add_parser("mocks", help="what each test patches, and behaviors covered only by mocks")
    mocks.add_argument("paths", nargs="+", type=Path, help="test files, or folders of test_*.py files")
    mocks.add_argument("--behaviors", type=Path, help="JSON list of {id, real_path, tests}")
    mocks.add_argument("--base", type=Path, help="test ids start from this folder; default: the current one")
    mocks.set_defaults(func=cmd_mocks)
    probes = sub.add_parser("probes", help="health probes that probe nothing")
    probes.add_argument("root", type=Path, help="the folder module names start from, such as src")
    probes.add_argument("paths", nargs="*", type=Path, help="files or folders to scan; default: ROOT")
    probes.add_argument("--names", default=PROBE_NAMES, help="regular expression for probe function names")
    probes.add_argument("--base", type=Path, help="show paths relative to this folder; default: ROOT")
    probes.set_defaults(func=cmd_probes)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
