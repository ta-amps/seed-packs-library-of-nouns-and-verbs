"""CLI entrypoint for hybrid RRF ranking, MinHash dedup/sanitization and 0/1 knapsack packing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .dedup_and_sanitize import sanitize_and_deduplicate
from .fusion import hybrid_rrf_rank
from .knapsack import pack_context_knapsack


def run_pipeline(bundle: dict[str, Any]) -> dict[str, Any]:
    """Run end-to-end RRF fusion -> sanitization + MinHash dedup -> 0/1 knapsack packing."""
    ranked = hybrid_rrf_rank(
        query=str(bundle["query"]),
        query_embedding=bundle["query_embedding"],
        candidates=bundle["candidates"],
        rrf_k=int(bundle.get("rrf_k", 60)),
    )
    cleaned = sanitize_and_deduplicate(
        ranked,
        near_dup_threshold=float(bundle.get("near_dup_threshold", 0.75)),
    )
    packed = pack_context_knapsack(
        cleaned["kept_chunks"],
        token_budget=int(bundle["token_budget"]),
        redundancy_lambda=float(bundle.get("redundancy_lambda", 0.35)),
    )
    return {
        "ranked_ids": [str(item["id"]) for item in ranked],
        "sanitized_chunk_ids": cleaned["sanitized_chunk_ids"],
        "dropped_chunk_ids": [str(item["id"]) for item in cleaned["dropped_chunks"]],
        "selected_ids": packed["selected_ids"],
        "total_tokens": packed["total_tokens"],
        "token_budget": packed["token_budget"],
        "total_adjusted_utility": packed["total_adjusted_utility"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hybrid RRF + MinHash + 0/1 context knapsack")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rank = sub.add_parser("rank", help="Rank candidates with BM25 + dense cosine RRF (k=60)")
    p_rank.add_argument("--input", required=True, type=Path)

    p_san = sub.add_parser("sanitize", help="Strip untrusted directives and prune MinHash near-duplicates")
    p_san.add_argument("--input", required=True, type=Path)

    p_pack = sub.add_parser("pack", help="Run full RRF + sanitize/dedup + 0/1 knapsack pipeline")
    p_pack.add_argument("--input", required=True, type=Path)

    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))

    if args.cmd == "rank":
        out = hybrid_rrf_rank(
            query=payload["query"],
            query_embedding=payload["query_embedding"],
            candidates=payload["candidates"],
            rrf_k=int(payload.get("rrf_k", 60)),
        )
    elif args.cmd == "sanitize":
        chunks = payload.get("ranked_chunks", payload.get("candidates", []))
        out = sanitize_and_deduplicate(
            chunks,
            near_dup_threshold=float(payload.get("near_dup_threshold", 0.75)),
        )
    else:
        out = run_pipeline(payload)

    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
