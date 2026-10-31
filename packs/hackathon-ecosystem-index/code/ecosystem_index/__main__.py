"""CLI entry point for ecosystem_index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .decompose import decompose_repository
from .search import hybrid_search


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ecosystem_index")
    sub = parser.add_subparsers(dest="command", required=True)

    dc = sub.add_parser("decompose", help="decompose raw repository metadata JSON into Task & Task-Object records")
    dc.add_argument("--input", required=True, type=Path)
    dc.add_argument("--out", type=Path)

    sr = sub.add_parser("search", help="run hybrid BM25 + facet RRF (k=60) search over a catalog JSON")
    sr.add_argument("--catalog", required=True, type=Path)
    sr.add_argument("--query", required=True)
    sr.add_argument("--stack", nargs="*", default=[])
    sr.add_argument("--domain", default=None)
    sr.add_argument("--track", default=None)
    sr.add_argument("--top-k", type=int, default=5)

    args = parser.parse_args(argv)
    if args.command == "decompose":
        raw_list = json.loads(args.input.read_text(encoding="utf-8"))
        out = [decompose_repository(r) for r in raw_list]
        payload = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
        return 0
    if args.command == "search":
        doc = json.loads(args.catalog.read_text(encoding="utf-8"))
        records = doc["projects"] if isinstance(doc, dict) and "projects" in doc else doc
        hits = hybrid_search(
            records,
            args.query,
            preferred_stack=args.stack,
            preferred_domain=args.domain,
            preferred_track=args.track,
            top_k=args.top_k,
        )
        print(json.dumps(hits, indent=2, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
