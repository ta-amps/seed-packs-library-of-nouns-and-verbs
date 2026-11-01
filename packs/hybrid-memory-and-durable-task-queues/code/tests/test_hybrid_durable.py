"""Unit tests for Seed Pack #111: hybrid-memory-and-durable-task-queues."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from hybrid_durable import (
    DomainAgnosticNamingGate,
    ZeroHardcodedValuesAstGate,
    evaluate_bundle,
    load_grid_spec,
)

PACK_ROOT = Path(__file__).resolve().parents[2]


class TestHybridMemoryAndDurableTaskQueues(unittest.TestCase):
    def test_ast_and_domain_agnostic_naming_gates(self) -> None:
        spec = load_grid_spec()
        engine_path = PACK_ROOT / "code" / "hybrid_durable" / "engine.py"
        src = engine_path.read_text(encoding="utf-8")
        self.assertEqual(ZeroHardcodedValuesAstGate.scan_source(src), [])
        self.assertEqual(
            DomainAgnosticNamingGate.scan_source(src, spec["forbidden_industry_tokens"]),
            [],
        )

    def test_worked_example_recomputes_exact_receipt(self) -> None:
        source_doc = json.loads((PACK_ROOT / "source.json").read_text(encoding="utf-8"))
        nouns = {n["slug"]: n for n in source_doc["nouns"]}
        bundle = nouns["example.hybrid-durable-bundle"]["value"]
        expected = nouns["example.hybrid-durable-receipt"]["value"]["instance"]
        actual = evaluate_bundle(bundle)
        self.assertEqual(actual, expected)

    def test_inline_lease_and_subspace_compression_invariants(self) -> None:
        source_doc = json.loads((PACK_ROOT / "source.json").read_text(encoding="utf-8"))
        nouns = {n["slug"]: n for n in source_doc["nouns"]}
        receipt = evaluate_bundle(nouns["example.hybrid-durable-bundle"]["value"])
        self.assertTrue(receipt["inline_lease_reclaimed"])
        self.assertTrue(receipt["self_review_blocked"])
        self.assertTrue(receipt["distinct_review_completed"])
        self.assertTrue(receipt["poison_routed_to_dead_letter"])
        self.assertEqual(receipt["replay_step_tokens"], 0)
        self.assertTrue(receipt["rating_idempotent_deduped"])
        self.assertGreater(receipt["prefix_tokens_saved"], 0)
        self.assertTrue(receipt["adapt_decompose_triggered"])
        self.assertGreater(receipt["memory_reduction_ratio"], 1.0)
        self.assertTrue(receipt["full_model_layers_covered"])


if __name__ == "__main__":
    unittest.main()
