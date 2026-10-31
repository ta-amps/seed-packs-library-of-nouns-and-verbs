"""Unit tests for HarnessTax, Pareto frontier rankings, freshness decay, and encapsulated feed digests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from harness_feeds.feed import encapsulate_feed
from harness_feeds.metrics import (
    compute_cost_per_verified_task,
    compute_harness_tax,
    normalize_harness_benchmark,
)
from harness_feeds.pareto import compute_freshness_decay, pareto_frontier, select_harness

PACK_SOURCE = Path(__file__).resolve().parents[2] / "source.json"


class HarnessFeedsTest(unittest.TestCase):
    def test_harness_tax_and_cost_per_verified_task(self) -> None:
        tax = compute_harness_tax(145000, 100000)
        self.assertEqual(tax["overhead_tokens"], 45000)
        self.assertAlmostEqual(tax["tax_ratio"], 0.45, places=4)
        self.assertAlmostEqual(tax["multiplier"], 1.45, places=4)

        cost = compute_cost_per_verified_task(36.0, 45, 60)
        self.assertAlmostEqual(cost["solve_rate"], 0.75, places=4)
        self.assertAlmostEqual(cost["cost_per_attempt_usd"], 0.60, places=4)
        self.assertAlmostEqual(cost["cost_per_verified_task_usd"], 0.80, places=4)

    def test_pareto_frontier_and_selection_constraints(self) -> None:
        runs = [
            {
                "harness_id": "harness-square",
                "setup_complete": True,
                "solve_rate": 0.72,
                "cost_per_verified_task_usd": 0.85,
                "harness_tax_ratio": 0.38,
                "mcp_reliability": 0.98,
            },
            {
                "harness_id": "pi",
                "setup_complete": True,
                "solve_rate": 0.66,
                "cost_per_verified_task_usd": 0.42,
                "harness_tax_ratio": 0.16,
                "mcp_reliability": 0.95,
            },
            {
                "harness_id": "dominated-runner",
                "setup_complete": True,
                "solve_rate": 0.60,
                "cost_per_verified_task_usd": 1.20,
                "harness_tax_ratio": 0.75,
                "mcp_reliability": 0.91,
            },
        ]
        frontier = pareto_frontier(runs)
        self.assertEqual(frontier, ["harness-square", "pi"])

        sel = select_harness(runs, max_cost_per_verified_usd=0.60, min_mcp_reliability=0.92)
        self.assertEqual(sel["selected_harness_id"], "pi")
        rejected_ids = {r["harness_id"] for r in sel["rejected"]}
        self.assertEqual(rejected_ids, {"dominated-runner", "harness-square"})

    def test_freshness_decay_and_release_drift(self) -> None:
        fresh = compute_freshness_decay("2026-10-28", "2026-10-30", half_life_days=21.0, missed_releases=0)
        self.assertEqual(fresh["status"], "fresh")
        self.assertGreater(fresh["freshness_score"], 0.90)

        stale = compute_freshness_decay("2026-08-15", "2026-10-30", half_life_days=21.0, missed_releases=3)
        self.assertEqual(stale["status"], "stale")
        self.assertLess(stale["freshness_score"], 0.15)

    def test_encapsulated_feed_digest_determinism_and_pack_agreement(self) -> None:
        source = json.loads(PACK_SOURCE.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in source["nouns"]}

        raw_runs = nouns["example.raw-harness-runs"]["runs"]
        norm = [normalize_harness_benchmark(r) for r in raw_runs]
        ranking = select_harness(norm, max_cost_per_verified_usd=1.25, min_mcp_reliability=0.92)
        self.assertEqual(ranking["pareto_frontier"], nouns["recommendation.pareto-selection"]["pareto_frontier"])
        self.assertEqual(ranking["selected_harness_id"], nouns["recommendation.pareto-selection"]["selected_harness_id"])

        profiles = [
            {"slug": slug, **nouns[slug]}
            for slug in ("profile.harness-square", "profile.opencode", "profile.pi", "profile.muse-code")
        ]
        sources = [{"slug": "source.open-harness-releases", **nouns["source.open-harness-releases"]}]
        benchmarks = [{"slug": "benchmark.normalized-matrix", "harness_id": "matrix", **nouns["benchmark.normalized-matrix"]}]
        recs = [{"slug": "recommendation.pareto-selection", **nouns["recommendation.pareto-selection"]}]

        enc1 = encapsulate_feed(
            feed_id="feed.agent-harnesses",
            as_of_date="2026-10-30",
            profiles=profiles,
            sources=sources,
            benchmarks=benchmarks,
            recommendations=recs,
        )
        enc2 = encapsulate_feed(
            feed_id="feed.agent-harnesses",
            as_of_date="2026-10-30",
            profiles=list(reversed(profiles)),
            sources=sources,
            benchmarks=benchmarks,
            recommendations=recs,
        )
        self.assertEqual(enc1["feed_digest_sha256"], enc2["feed_digest_sha256"])
        self.assertEqual(enc1["feed_digest_sha256"], nouns["feed.agent-harnesses"]["encapsulated_digest_sha256"])
        self.assertEqual(enc1["child_count"], nouns["feed.agent-harnesses"]["child_count"])


if __name__ == "__main__":
    unittest.main()
