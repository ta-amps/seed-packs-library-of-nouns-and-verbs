"""Command line for the health checks. It reads the folder it is given and prints JSON; it writes nothing.

  python -m health_checks todos ROOT [--as-of 2026-10-30] [--no-git] [--exclude GLOB] [--fail-on stale]
  python -m health_checks swallowed ROOT [--exclude GLOB] [--strict]

todos exits 1 when --fail-on names a bucket (aging, stale or ancient) and any marker is that old or
older. swallowed exits 1 when a swallowed handler or a broad suppress is found; with --strict, logged
and fallback handlers count too. A file that does not parse is listed, and with --strict it fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from .swallowed import ACT, find_swallowed
from .todos import BUCKETS, age_todos

ORDER = [name for name, _, _ in BUCKETS]


def cmd_todos(args: argparse.Namespace) -> int:
    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
    result = age_todos(args.root, as_of, use_git=not args.no_git, exclude=args.exclude)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    if args.fail_on:
        worst = set(ORDER[ORDER.index(args.fail_on):])
        return 1 if any(item["bucket"] in worst for item in result["items"]) else 0
    return 0


def cmd_swallowed(args: argparse.Namespace) -> int:
    result = find_swallowed(args.root, exclude=args.exclude)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    failing = ACT | ({"logged_only", "fallback"} if args.strict else set())
    if any(item["class"] in failing for item in result["items"]) or (args.strict and result["unparsed"]):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="health_checks", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    todos = sub.add_parser("todos", help="markers in comments, aged by git blame")
    todos.add_argument("root", type=Path)
    todos.add_argument("--as-of", help="the date ages are counted to, YYYY-MM-DD; default today in UTC")
    todos.add_argument("--no-git", action="store_true", help="do not run git; every age is unknown")
    todos.add_argument("--exclude", action="append", default=[], help="glob relative to ROOT; repeatable")
    todos.add_argument("--fail-on", choices=ORDER[1:], help="exit 1 when a marker is in this bucket or older")
    todos.set_defaults(func=cmd_todos)
    swallowed = sub.add_parser("swallowed", help="Python handlers that swallow errors")
    swallowed.add_argument("root", type=Path)
    swallowed.add_argument("--exclude", action="append", default=[], help="glob relative to ROOT; repeatable")
    swallowed.add_argument("--strict", action="store_true", help="logged, fallback and unparsed count as failures too")
    swallowed.set_defaults(func=cmd_swallowed)
    args = parser.parse_args(argv)
    if not args.root.exists():
        parser.error(f"{args.root} does not exist")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
