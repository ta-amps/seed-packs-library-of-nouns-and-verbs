"""Unit tests for SIRA Noun Enrichment, RA-RFT Analogy Index, Herma Shim Compiler and DGM-H Verifier."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from sira_rag import (
    BENCHMARK_QUERIES_60,
    STRUCTURAL_FRAMES_12,
    DgmHIndependentVerifier,
    HermaShimCompiler,
    MrSearchReflector,
    RaRftAnalogyIndex,
    SiraNounEnricher,
    run_79_pack_benchmark,
    run_worked_example,
)


def _sample_mini_bundle() -> dict:
    return {
        "query": "Hospital compounding pharmacy requires independent pharmacists from separate shifts so nobody signs off their own syringe batch",
        "structural_frames": ["independent-two-step-review"],
        "mini_packs": [
            {
                "pack_id": "budget-table-summary",
                "title": "Budget table summary",
                "summary": "A collection of nouns and verbs for summarizing city budget tables.",
                "nouns": [{"slug": "pack", "category": "noun.skill_pack", "role": "pack", "title": "Budget pack"}],
                "verbs": [{"slug": "summarize", "kind": "verb.situate", "title": "Summarize budget", "outcome": "Table"}],
            },
            {
                "pack_id": "two-step-kit-review",
                "title": "Two-step kit review",
                "summary": "A collection of nouns and verbs for drafting and reviewing public-good kits.",
                "nouns": [
                    {
                        "slug": "guardrail.distinct",
                        "category": "noun.skill_pack",
                        "role": "guardrail",
                        "title": "Guardrail: drafter cannot self-approve",
                    }
                ],
                "verbs": [
                    {
                        "slug": "review-kit",
                        "kind": "verb.verify_gate",
                        "review": "distinct_reviewer",
                        "title": "Verify kit with distinct reviewer",
                        "outcome": "Independent approval receipt",
                    }
                ],
            },
            {
                "pack_id": "audio-loudness-gate",
                "title": "Audio loudness gate",
                "summary": "A collection of nouns and verbs for checking broadcast LUFS loudness.",
                "nouns": [{"slug": "spec", "category": "noun.benchmark_suite", "role": "spec", "title": "LUFS spec"}],
                "verbs": [{"slug": "check-lufs", "kind": "verb.verify_gate", "title": "Check LUFS", "outcome": "LUFS report"}],
            },
            {
                "pack_id": "folder-hash-mover",
                "title": "Folder hash mover",
                "summary": "A collection of nouns and verbs for moving large folders safely by hash.",
                "nouns": [{"slug": "rules", "category": "noun.reflex_procedure", "role": "rules", "title": "Move rules"}],
                "verbs": [{"slug": "move", "kind": "verb.ingest", "title": "Move files", "outcome": "Hash manifest"}],
            },
        ],
        "episodes": [
            {
                "episode_id": "EP-01",
                "query": "independent pharmacists separate shifts sign off separation of duties",
                "target_pack_id": "two-step-kit-review",
                "structural_frame": "independent-two-step-review",
                "baseline_rounds": 4,
                "exploratory_tokens": 2400,
                "single_shot_tokens": 410,
                "went_wrong": ["Surface title lacked pharmacy vocabulary; needed structural frame match."],
            }
        ],
    }


class SiraSelfLearningRagTests(unittest.TestCase):
    def test_structural_frames_include_all_five_core_isomorphisms(self) -> None:
        required = {
            "split-sensitive-vs-public",
            "exclusive-lease-fencing",
            "independent-two-step-review",
            "cas-promotion",
            "zero-token-memoized-reuse",
        }
        self.assertTrue(required.issubset(set(STRUCTURAL_FRAMES_12)))

    def test_enricher_and_analogy_index_beat_lexical_on_cross_domain_query(self) -> None:
        bundle = _sample_mini_bundle()
        res = run_worked_example(bundle)
        self.assertEqual(res["baseline_top1"], "audio-loudness-gate")
        self.assertEqual(res["sira_rartf_top1"], "two-step-kit-review")
        self.assertEqual(res["compiled_shim_count"], 1)
        self.assertTrue(res["self_verification_rejected"])
        self.assertTrue(res["distinct_verification_approved"])

    def test_herma_shim_evaluates_under_2ms_and_dgmh_blocks_self_approval(self) -> None:
        bundle = _sample_mini_bundle()
        compiler = HermaShimCompiler()
        rules = compiler.compile_rules(bundle["episodes"])
        shim_hit = compiler.evaluate_shim("require independent pharmacists separate shifts sign off", rules)
        self.assertTrue(shim_hit["within_2ms_budget"])
        self.assertLess(shim_hit["latency_ms"], 2.0)
        self.assertIn("two-step-kit-review", shim_hit["boost_packs"])

        reflector = MrSearchReflector()
        props = reflector.propose_improvements(
            bundle["episodes"],
            proposer_worker_id="worker-same",
            proposer_key_id="key-same",
        )
        verifier = DgmHIndependentVerifier()
        refused = verifier.verify_proposal(
            props[0],
            verifier_worker_id="worker-same",
            verifier_key_id="key-other",
        )
        self.assertFalse(refused["approved_for_owner_review"])
        self.assertEqual(refused["http_status_equivalent"], 409)
        self.assertIn("self_verification_forbidden_proposer_equals_verifier", refused["failed_checks"])

    def test_real_packs_benchmark_improves_recall_mrr_and_stays_under_2ms(self) -> None:
        packs_dir = Path(__file__).resolve().parents[3]
        self.assertEqual(len(BENCHMARK_QUERIES_60), 60)
        report = run_79_pack_benchmark(packs_dir)
        base = report["arms"]["baseline_lexical"]
        sira = report["arms"]["sira_enriched"]
        full = report["arms"]["sira_rartf_mrsearch"]
        self.assertEqual(report["corpus_size_packs"], 79)
        self.assertGreater(sira["recall_at_1"], base["recall_at_1"] + 0.25)
        self.assertGreater(full["recall_at_1"], sira["recall_at_1"])
        self.assertGreater(full["mrr"], sira["mrr"])
        self.assertGreater(full["mrr"], base["mrr"] + 0.20)
        self.assertEqual(full["avg_search_rounds"], 1.0)
        self.assertGreater(base["avg_search_rounds"], 2.8)
        self.assertTrue(report["headline_deltas"]["all_queries_under_2ms"])
        self.assertTrue(report["herma_shim_compilation"]["within_2ms_budget"])

    def test_source_json_worked_example_recomputes_identically(self) -> None:
        source_path = Path(__file__).resolve().parents[2] / "source.json"
        if not source_path.exists():
            return
        source = json.loads(source_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in source["nouns"]}
        bundle = nouns["example.sira-analogy-bundle"]
        expected = nouns["example.sira-analogy-receipt"]["instance"]
        self.assertEqual(run_worked_example(bundle), expected)


if __name__ == "__main__":
    unittest.main()
