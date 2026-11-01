"""CLI entrypoint for offline combinatorial niche forging, spider simulation and 8-axis evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluator import (
    benchmark_query_families,
    score_candidate_axes,
    verify_curated_admission_independently,
)
from .forge import advance_cell_page_cursor, mint_combinatorial_niche_catalog
from .spider import advance_spider_frontier_and_waves, evaluate_refresh_and_movers


def run_bundle(doc: dict) -> dict:
    catalog = mint_combinatorial_niche_catalog(
        domains=doc["domains"],
        custom_phrases=doc.get("custom_phrases", []),
        max_intents=int(doc.get("max_intents", 2)),
        max_angles=int(doc.get("max_angles", 1)),
        max_verticals=int(doc.get("max_verticals", 1)),
    )
    cursor_step = advance_cell_page_cursor(catalog["cells"][0])
    scored = [score_candidate_axes(c) for c in doc["candidates"]]
    spider = advance_spider_frontier_and_waves(
        qualifying_finds=[
            {**cand, "on_topic": sc["on_topic"]}
            for cand, sc in zip(doc["candidates"], scored)
        ],
        frontier_queue=doc["frontier_queue"],
        visited_targets=set(doc.get("visited_targets", [])),
        completed_runs=int(doc.get("completed_runs", 16)),
    )
    refresh = evaluate_refresh_and_movers(
        doc["known_repos"],
        doc["fresh_observations"],
    )
    family_bench = benchmark_query_families(doc["query_logs"])
    self_check = verify_curated_admission_independently(
        curator_worker_id="worker.spider-a",
        curator_key_id="tsk_spider_a",
        reviewer_worker_id="worker.spider-a",
        reviewer_key_id="tsk_spider_a",
        scored_candidates=scored,
    )
    distinct_check = verify_curated_admission_independently(
        curator_worker_id="worker.spider-a",
        curator_key_id="tsk_spider_a",
        reviewer_worker_id="worker.reviewer-b",
        reviewer_key_id="tsk_reviewer_b",
        scored_candidates=scored,
    )
    return {
        "domain_count": catalog["domain_count"],
        "minted_cells": catalog["cell_count"],
        "first_cell_next_cursor": cursor_step["updated_cell"]["page_cursor"],
        "allowed_spider_depth": spider["allowed_spider_depth"],
        "enqueued_edges": spider["enqueued_edge_count"],
        "proposed_wave_verbs": len(spider["proposed_wave_verbs"]),
        "on_topic_candidates": sum(1 for s in scored if s["on_topic"]),
        "movers_detected": refresh["mover_count"],
        "gone_detected": refresh["gone_count"],
        "retired_noisy_families": family_bench["retired_families"],
        "self_approval_blocked": not self_check["approved"] and self_check["status_code"] == 409,
        "distinct_review_admitted": distinct_check["admitted_repos"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="niche_spider")
    parser.add_argument("--bundle", type=Path, required=True, help="JSON bundle for combinatorial niche spider evaluation.")
    args = parser.parse_args(argv)
    doc = json.loads(args.bundle.read_text(encoding="utf-8"))
    out = run_bundle(doc)
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
