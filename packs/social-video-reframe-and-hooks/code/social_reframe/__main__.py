"""Command-line entry point for social_reframe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .planner import ASPECT_RATIOS, build_cutdown_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="social_reframe")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Compile a 9:16, 1:1, or 4:5 cutdown plan from a 16:9 timeline spec")
    p_plan.add_argument("spec_path", type=Path)
    p_plan.add_argument("--aspect", choices=sorted(ASPECT_RATIOS), default="9:16")

    args = parser.parse_args(argv)
    spec = json.loads(args.spec_path.read_text(encoding="utf-8"))
    plan = build_cutdown_plan(spec, aspect=args.aspect)
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
