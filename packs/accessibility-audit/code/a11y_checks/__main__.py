"""Command line for the accessibility checks. Reads only the files it is given and prints JSON.

  python -m a11y_checks contrast FOREGROUND BACKGROUND [--size-px N] [--weight W] [--non-text]
  python -m a11y_checks contrast --pairs PAIRS.json
  python -m a11y_checks structure PAGE.html [PAGE.html ...] [--strict]

contrast exits 1 when a pair misses its WCAG 2.2 AA threshold. structure exits 1 when a page has a
failure; with --strict, advisories count too. Nothing is written and no network is used.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .contrast import check_pair
from .structure import lint


def _pairs(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("pairs", [])
    if not isinstance(rows, list):
        raise SystemExit("--pairs needs a JSON list of pairs, or an object with a pairs list")
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or "foreground" not in row or "background" not in row:
            raise SystemExit(f"pair {i} needs foreground and background")
        result = check_pair(row["foreground"], row["background"], size_px=row.get("size_px"),
                            weight=row.get("weight", 400), kind=row.get("kind", "text"))
        out.append({"id": row.get("id", str(i)), **result})
    return out


def cmd_contrast(args: argparse.Namespace) -> int:
    try:
        if args.pairs:
            results = _pairs(args.pairs)
        elif args.foreground and args.background:
            results = [check_pair(args.foreground, args.background, size_px=args.size_px, weight=args.weight,
                                  kind="non_text" if args.non_text else "text")]
        else:
            raise SystemExit("give FOREGROUND and BACKGROUND, or --pairs FILE")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({"results": results, "failed": sum(1 for r in results if not r["passes"])}, indent=1))
    return 1 if any(not r["passes"] for r in results) else 0


def cmd_structure(args: argparse.Namespace) -> int:
    reports = {}
    worst = 0
    for path in args.pages:
        report = lint(path.read_text(encoding="utf-8"))
        reports[str(path)] = report
        if report["failures"] or (args.strict and report["advisories"]):
            worst = 1
    print(json.dumps(reports, indent=1, ensure_ascii=False))
    return worst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="a11y_checks", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    contrast = sub.add_parser("contrast", help="contrast ratio of color pairs")
    contrast.add_argument("foreground", nargs="?")
    contrast.add_argument("background", nargs="?")
    contrast.add_argument("--size-px", type=float, default=None)
    contrast.add_argument("--weight", type=float, default=400)
    contrast.add_argument("--non-text", action="store_true", help="a user interface part or graphic, 3:1")
    contrast.add_argument("--pairs", type=Path, help="JSON list of {id, foreground, background, size_px, weight, kind}")
    contrast.set_defaults(func=cmd_contrast)
    structure = sub.add_parser("structure", help="landmarks, heading order, language and title")
    structure.add_argument("pages", nargs="+", type=Path)
    structure.add_argument("--strict", action="store_true", help="advisories fail too")
    structure.set_defaults(func=cmd_structure)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
