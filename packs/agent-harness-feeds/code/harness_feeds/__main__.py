"""CLI entry point for harness_feeds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .feed import encapsulate_feed
from .metrics import normalize_harness_benchmark
from .pareto import compute_freshness_decay, select_harness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness_feeds")
    sub = parser.add_subparsers(dest="command", required=True)

    nm = sub.add_parser("normalize", help="normalize raw harness benchmark JSON records")
    nm.add_argument("--input", required=True, type=Path)

    rk = sub.add_parser("rank", help="compute Pareto frontier and rank normalized harness benchmarks")
    rk.add_argument("--input", required=True, type=Path)
    rk.add_argument("--max-cost-usd", type=float, default=None)
    rk.add_argument("--max-tax-ratio", type=float, default=None)
    rk.add_argument("--min-mcp-reliability", type=float, default=0.90)

    fr = sub.add_parser("freshness", help="compute freshness decay for an observed date")
    fr.add_argument("--observed", required=True)
    fr.add_argument("--as-of", required=True)
    fr.add_argument("--missed-releases", type=int, default=0)

    en = sub.add_parser("encapsulate", help="encapsulate profiles, sources, benchmarks and recommendations")
    en.add_argument("--bundle-json", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "normalize":
        rows = json.loads(args.input.read_text(encoding="utf-8"))
        out = [normalize_harness_benchmark(r) for r in rows]
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    if args.command == "rank":
        rows = json.loads(args.input.read_text(encoding="utf-8"))
        norm = [normalize_harness_benchmark(r) if "total_harness_tokens" in r else r for r in rows]
        print(json.dumps(select_harness(
            norm,
            max_cost_per_verified_usd=args.max_cost_usd,
            max_harness_tax_ratio=args.max_tax_ratio,
            min_mcp_reliability=args.min_mcp_reliability,
        ), indent=2, sort_keys=True))
        return 0
    if args.command == "freshness":
        print(json.dumps(compute_freshness_decay(
            args.observed, args.as_of, missed_releases=args.missed_releases
        ), indent=2, sort_keys=True))
        return 0
    if args.command == "encapsulate":
        b = json.loads(args.bundle_json.read_text(encoding="utf-8"))
        print(json.dumps(encapsulate_feed(**b), indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
