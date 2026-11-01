"""Command-line entry point for tier_firewall."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .firewall import evaluate_dispatch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tier_firewall")
    sub = parser.add_subparsers(dest="command", required=True)

    p_eval = sub.add_parser("evaluate", help="Evaluate an outbound agent request against a capability and tier policy")
    p_eval.add_argument("request_path", type=Path)
    p_eval.add_argument("--policy", type=Path, required=True)

    args = parser.parse_args(argv)
    req = json.loads(args.request_path.read_text(encoding="utf-8"))
    pol = json.loads(args.policy.read_text(encoding="utf-8"))
    decision = evaluate_dispatch(req, pol)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0 if decision["allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
