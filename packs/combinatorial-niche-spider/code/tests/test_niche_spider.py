"""Unit and worked-example tests for combinatorial-niche-spider."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from niche_spider import (
    advance_cell_page_cursor,
    advance_spider_frontier_and_waves,
    benchmark_query_families,
    build_rotating_domain_paths,
    evaluate_refresh_and_movers,
    mint_combinatorial_niche_catalog,
    score_candidate_axes,
    verify_curated_admission_independently,
)
from niche_spider.__main__ import run_bundle

SOURCE_JSON = Path(__file__).resolve().parents[2] / "source.json"


class NicheSpiderTests(unittest.TestCase):
    def test_recomputes_worked_example_from_source_json(self) -> None:
        source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n for n in source["nouns"]}
        bundle = nouns["example.niche-spider-bundle"]["value"]
        expected = nouns["example.niche-spider-receipt"]["value"]["instance"]
        actual = run_bundle(bundle)
        self.assertEqual(actual, expected)

    def test_page_cursor_advances_without_repeating_and_caps_at_max(self) -> None:
        cat = mint_combinatorial_niche_catalog(
            domains=["ocr-and-document-ai", "blender-and-3d", "privacy-tools"],
            custom_phrases=["retro game preservation"],
        )
        self.assertGreater(cat["cell_count"], 100)
        cell = cat["cells"][0]
        seen_pages = []
        for _ in range(6):
            step = advance_cell_page_cursor(cell)
            seen_pages.append(step["fetched_page"])
            cell = step["updated_cell"]
        self.assertEqual(seen_pages, [1, 2, 3, 4, 5, None])

    def test_rotating_paths_and_negative_guards_filter_interview_junk(self) -> None:
        paths = build_rotating_domain_paths("game-design", "level design", cycle_index=1)
        self.assertEqual(len(paths), 8)
        self.assertTrue(any(p["family"] == "license_free" and "Apache-2.0" in p["query"] for p in paths))
        junk = score_candidate_axes({
            "repo": "example/low-level-design-interview",
            "description": "Low-level design interview preparation and leetcode solutions",
            "topics": ["interview", "java"],
            "domain_terms": ["level design", "greybox"],
            "stars": 4200,
            "forks": 900,
            "license": "MIT",
        })
        self.assertFalse(junk["on_topic"])
        self.assertEqual(junk["composite"], 0.0)

        real_gem = score_candidate_axes({
            "repo": "clinic-tools/intake-ocr-workbench",
            "description": "Offline handwritten intake OCR toolkit and table parser for community clinics",
            "topics": ["intake-ocr", "paddleocr", "nonprofit"],
            "domain_terms": ["intake", "ocr", "table"],
            "stars": 6,
            "forks": 2,
            "age_days": 5,
            "days_since_push": 1,
            "independent_query_hits": 3,
            "license": "CC0-1.0",
            "has_docs_or_templates": True,
        })
        self.assertTrue(real_gem["on_topic"])
        self.assertEqual(real_gem["axes"]["freeness"], 100.0)
        self.assertGreater(real_gem["axes"]["rarity"], 80.0)
        self.assertEqual(real_gem["axes"]["commonality"], 75.0)

    def test_anti_stall_and_distinct_reviewer_gate(self) -> None:
        stalled = advance_spider_frontier_and_waves(
            qualifying_finds=[],
            frontier_queue=[],
            visited_targets=set(),
            completed_runs=24,
        )
        self.assertEqual(stalled["allowed_spider_depth"], 5)
        self.assertIn("template->boilerplate", stalled["anti_stall_mutations"])

        refresh = evaluate_refresh_and_movers(
            known_repos=[
                {"repo": "org/a", "stars": 10, "pushed_at": "2026-10-01", "last_checked_epoch": 1.0},
                {"repo": "org/gone", "stars": 4, "pushed_at": "2026-10-02", "last_checked_epoch": 2.0},
            ],
            fresh_observations={
                "org/a": {"http_status": 200, "stars": 19, "pushed_at": "2026-10-31"},
                "org/gone": {"http_status": 404},
            },
        )
        self.assertEqual(refresh["mover_count"], 1)
        self.assertEqual(refresh["gone_repos"], ["org/gone"])

        bench = benchmark_query_families([
            {"family": "license_free", "query": '"OCR" license:MIT', "hits": 10, "on_topic_hits": 8},
            {"family": "broad_wave", "query": '"design" topic:web', "hits": 50, "on_topic_hits": 1},
        ])
        self.assertIn("broad_wave", bench["retired_families"])
        self.assertIn('"OCR" license:MIT', bench["champion_queries"])

        blocked = verify_curated_admission_independently(
            curator_worker_id="w1",
            curator_key_id="k1",
            reviewer_worker_id="w1",
            reviewer_key_id="k2",
            scored_candidates=[],
        )
        self.assertEqual(blocked["status_code"], 409)


if __name__ == "__main__":
    unittest.main()
