"""Command-line entry point for diagram_svg."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .compiler import compile_diagram


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="diagram_svg")
    sub = parser.add_subparsers(dest="command", required=True)

    p_render = sub.add_parser("render", help="Render a declarative JSON spec to accessible SVG or audit JSON")
    p_render.add_argument("spec_path", type=Path)
    p_render.add_argument("--audit-json", action="store_true", help="Emit JSON with both SVG and deterministic audit")

    args = parser.parse_args(argv)
    spec = json.loads(args.spec_path.read_text(encoding="utf-8"))
    compiled = compile_diagram(spec)
    if not compiled["audit"]["passed"]:
        print(json.dumps(compiled["audit"], indent=2, sort_keys=True), file=sys.stderr)
        return 1
    if args.audit_json:
        print(json.dumps(compiled, indent=2, sort_keys=True))
    else:
        print(compiled["svg"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
