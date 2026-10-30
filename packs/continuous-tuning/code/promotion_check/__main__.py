"""Command line: recompute a promotion decision, a paired bootstrap, a receipt check or a rule digest.

  python -m promotion_check decide --rule RULE.json --evaluations EVALS.json --integrity INTEGRITY.json
  python -m promotion_check bootstrap --pairs PAIRS.json [--resamples 2000 --seed S --confidence 0.95]
  python -m promotion_check receipt --receipt RECEIPT.json --rows ROWS.jsonl --first-scored-at 2026-10-29T15:00:00Z
  python -m promotion_check digest RULE.json

EVALS.json holds {"candidate": ..., "champion": ..., "base": ...}; PAIRS.json holds {"candidate": [...],
"champion": [...]}. Results print as JSON. Only receipt exits 1, when it finds a problem; keeping the
champion is a valid decision, not an error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .bootstrap import paired_bootstrap
from .draw import digest
from .frozen import check_receipt
from .rule import decide


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="promotion_check", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    dec = sub.add_parser("decide", help="the decision record for one candidate")
    dec.add_argument("--rule", type=Path, required=True)
    dec.add_argument("--evaluations", type=Path, required=True)
    dec.add_argument("--integrity", type=Path, required=True)
    boot = sub.add_parser("bootstrap", help="a paired bootstrap of exact-match rows")
    boot.add_argument("--pairs", type=Path, required=True)
    boot.add_argument("--resamples", type=int, default=2000)
    boot.add_argument("--seed", default="tool-call-specialist.promotion.v1")
    boot.add_argument("--confidence", type=float, default=0.95)
    rec = sub.add_parser("receipt", help="check a frozen test receipt against its rows")
    rec.add_argument("--receipt", type=Path, required=True)
    rec.add_argument("--rows", type=Path, required=True)
    rec.add_argument("--first-scored-at", required=True)
    dig = sub.add_parser("digest", help="the SHA-256 of a JSON value's canonical form")
    dig.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "decide":
        evaluations = load(args.evaluations)
        result = decide(load(args.rule), evaluations["candidate"], evaluations["champion"], evaluations["base"],
                        load(args.integrity))
        print(json.dumps(result, indent=1))
        return 0
    if args.command == "bootstrap":
        pairs = load(args.pairs)
        print(json.dumps(paired_bootstrap(pairs["candidate"], pairs["champion"], args.resamples, args.seed,
                                          args.confidence)))
        return 0
    if args.command == "receipt":
        rows = [json.loads(line) for line in args.rows.read_text(encoding="utf-8").splitlines() if line.strip()]
        problems = check_receipt(load(args.receipt), rows, args.first_scored_at)
        print(json.dumps({"problems": problems}))
        return 1 if problems else 0
    print(digest(load(args.path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
