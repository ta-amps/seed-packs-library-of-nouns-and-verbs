"""CLI entry point for brainstorm_miner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .miner import (
    chunk_canonical_blocks,
    collapse_duplicate_blocks,
    mine_brainstorm_text,
    split_repeated_pastes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="brainstorm_miner", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dedup = sub.add_parser("dedup", help="Split inline/block repeats and collapse duplicates")
    p_dedup.add_argument("input_file", type=Path)
    p_dedup.add_argument("--near-dup-threshold", type=float, default=0.85)

    p_chunk = sub.add_parser("chunk", help="Deduplicate and emit content-addressed chunks")
    p_chunk.add_argument("input_file", type=Path)

    p_mine = sub.add_parser("mine", help="Deduplicate, chunk, extract situations, and score category gaps")
    p_mine.add_argument("input_file", type=Path)
    p_mine.add_argument("--near-dup-threshold", type=float, default=0.85)

    args = parser.parse_args(argv)
    raw_text = args.input_file.read_text(encoding="utf-8")

    if args.cmd == "dedup":
        blocks = split_repeated_pastes(raw_text)
        res = collapse_duplicate_blocks(blocks, near_dup_threshold=args.near_dup_threshold)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if args.cmd == "chunk":
        blocks = split_repeated_pastes(raw_text)
        dedup = collapse_duplicate_blocks(blocks)
        chunks = chunk_canonical_blocks(dedup["canonical_blocks"])
        print(json.dumps({"chunks": chunks, "count": len(chunks)}, indent=2, sort_keys=True))
        return 0

    report = mine_brainstorm_text(raw_text, near_dup_threshold=args.near_dup_threshold)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
