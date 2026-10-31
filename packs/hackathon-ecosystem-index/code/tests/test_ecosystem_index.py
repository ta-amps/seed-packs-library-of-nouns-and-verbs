"""Unit tests for Task & Task-Object decomposition, BM25, facet scoring, RRF (k=60), and pack agreement."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from ecosystem_index.decompose import PROVENANCE_TAG, decompose_repository, sanitize_text
from ecosystem_index.search import BM25Index, hybrid_search, reciprocal_rank_fusion

PACK_SOURCE = Path(__file__).resolve().parents[2] / "source.json"


class EcosystemIndexTest(unittest.TestCase):
    def test_sanitize_em_dash_and_decompose_repo(self) -> None:
        self.assertNotIn("\u2014", sanitize_text("Vision segmentation \u2014 fast masks"))
        rec = decompose_repository({
            "repo": "example-org/vision-mask-bench",
            "track": "Track 2",
            "domain": "Multimodal Vision & Video (SAM)",
            "meta_stack": ["sam", "weights", "spark"],
            "primary_language": "Python",
            "license": "MIT",
            "scan_status": "ok",
            "head_sha": "1234567890abcdef1234567890abcdef12345678",
            "tests_present": True,
            "mcp_adopted": True,
            "readme_first_paragraph": "Segment video frames with local SAM masks \u2014 verify UI bounds.",
            "verb_items": [
                {"category": "test_check", "kind": "cli_command", "name": "verify-masks"},
                {"category": "agent_tool", "kind": "mcp_tool", "name": "segment_frame"},
            ],
            "noun_counts": {"code": 12, "tool": 2, "model": 1, "test_evaluation": 4},
        })
        self.assertEqual(rec["provenance"], PROVENANCE_TAG)
        self.assertNotIn("\u2014", rec["summary"])
        self.assertTrue(all(t["verification_status"] == "candidate_unverified" for t in rec["tasks"]))
        verb_cats = {t["verb_category"] for t in rec["tasks"]}
        self.assertIn("verb.verify_gate", verb_cats)
        self.assertIn("verb.probe_source", verb_cats)
        noun_cats = {o["noun_category"] for o in rec["task_objects"]}
        self.assertIn("noun.code_node", noun_cats)
        self.assertIn("noun.mcp_server", noun_cats)

    def test_bm25_and_rrf_k60_hybrid_search(self) -> None:
        r1 = decompose_repository({
            "repo": "org-alpha/sam-video-inspector",
            "track": "Track 2",
            "domain": "Multimodal Vision & Video (SAM)",
            "meta_stack": ["sam", "weights"],
            "tests_present": True,
            "mcp_adopted": True,
            "readme_first_paragraph": "Frame segmentation and mask collision checks for video streams.",
            "verb_counts": {"test_check": 3, "agent_tool": 2},
            "noun_counts": {"code": 10, "model": 2},
        })
        r2 = decompose_repository({
            "repo": "org-beta/sql-ledger-sync",
            "track": "Track 1",
            "domain": "Developer Tooling, Infra & Security",
            "meta_stack": ["code"],
            "tests_present": True,
            "readme_first_paragraph": "Schema migration lint and SQL ledger checksum tool.",
            "verb_counts": {"test_check": 2},
            "noun_counts": {"code": 8},
        })
        r3 = decompose_repository({
            "repo": "org-gamma/llama-voice-tutor",
            "track": "Track 1",
            "domain": "Education & Coaching",
            "meta_stack": ["llama", "meta_api"],
            "readme_first_paragraph": "Interactive spoken language practice with Llama prompts.",
            "verb_counts": {"run_serve": 1},
            "noun_counts": {"prompt": 5},
        })

        bm = BM25Index([r1, r2, r3]).rank("video mask segmentation")
        self.assertEqual(bm[0][0], "org-alpha/sam-video-inspector")
        self.assertGreater(bm[0][1], 0.0)

        # Direct check on RRF k=60 math: rank 1 in both lists => 2 / 61 = 0.032787
        fused = reciprocal_rank_fusion([[("a", 2.5), ("b", 1.0)], [("a", 3.0), ("b", 0.5)]], k=60)
        self.assertEqual(fused[0][0], "a")
        self.assertAlmostEqual(fused[0][1], round(2.0 / 61.0, 6), places=6)

        hits = hybrid_search(
            [r1, r2, r3],
            "video segmentation mask",
            preferred_stack=["sam"],
            preferred_domain="Vision",
            rrf_k=60,
            top_k=2,
        )
        self.assertEqual(hits[0]["repo"], "org-alpha/sam-video-inspector")
        self.assertAlmostEqual(hits[0]["rrf_score"], round(2.0 / 61.0, 6), places=6)

    def test_pack_worked_example_recomputes_exactly(self) -> None:
        source = json.loads(PACK_SOURCE.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in source["nouns"]}
        raw_repos = nouns["example.raw-repo-scans"]["repositories"]
        decomposed = [decompose_repository(r) for r in raw_repos]
        q = nouns["example.raw-repo-scans"]["search_query"]
        hits = hybrid_search(
            decomposed,
            q["query"],
            preferred_stack=q["preferred_stack"],
            preferred_domain=q["preferred_domain"],
            rrf_k=60,
            top_k=3,
        )
        expected = nouns["example.search-results"]["instance"]
        self.assertEqual([h["repo"] for h in hits], expected["ranked_repos"])
        self.assertEqual(hits[0]["rrf_score"], expected["top_rrf_score"])


if __name__ == "__main__":
    unittest.main()
