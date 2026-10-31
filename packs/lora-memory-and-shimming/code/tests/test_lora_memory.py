"""Unit tests for post-cutoff LoRA compilation, shim/weight routing, and bootstrap CI promotion gates."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from lora_memory.compiler import check_holdout_disjointness, compile_post_cutoff_pairs
from lora_memory.gates import evaluate_promotion_gate
from lora_memory.router import route_adaptation_strategy

PACK_SOURCE = Path(__file__).resolve().parents[2] / "source.json"


class LoraMemoryTest(unittest.TestCase):
    def test_compile_pairs_and_holdout_disjointness(self) -> None:
        objs = [
            {
                "id": "spec.sandbox-sdk-v1",
                "subject": "Cloudflare Sandbox SDK 1.0 session creation",
                "effective_date": "2026-10-15",
                "canonical_fact": "createSession accepts explicit memoryMiB and networkPolicy options",
                "superseded_claim": "createSession took positional boolean network flags",
                "scope_boundary": "unreleased multi-region GPU quotas",
            }
        ]
        pairs = compile_post_cutoff_pairs(objs)
        self.assertEqual([p["pair_kind"] for p in pairs], ["direct_fact", "supersession_guard", "scope_abstention"])

        clean_holdouts = ["Write a session startup call setting memoryMiB and networkPolicy."]
        disj = check_holdout_disjointness(pairs, clean_holdouts)
        self.assertTrue(disj["disjoint"])

        leaked_holdouts = [pairs[0]["prompt"]]
        leaked = check_holdout_disjointness(pairs, leaked_holdouts)
        self.assertFalse(leaked["disjoint"])

    def test_route_adaptation_strategy_modes(self) -> None:
        fast_churn = route_adaptation_strategy({
            "churn_half_life_days": 5,
            "queries_per_day": 5000,
            "shim_tokens_per_query": 1200,
            "training_equivalent_tokens": 2_000_000,
        })
        self.assertEqual(fast_churn["selected_strategy"], "prompt_context_shim")

        stable_high_vol = route_adaptation_strategy({
            "churn_half_life_days": 60,
            "queries_per_day": 500,
            "shim_tokens_per_query": 600,
            "training_equivalent_tokens": 2_000_000,
            "has_volatile_pins_plus_stable_syntax": False,
        })
        self.assertEqual(stable_high_vol["selected_strategy"], "lora_weight_update")

        hybrid = route_adaptation_strategy({
            "churn_half_life_days": 45,
            "queries_per_day": 500,
            "shim_tokens_per_query": 600,
            "training_equivalent_tokens": 2_000_000,
            "has_volatile_pins_plus_stable_syntax": True,
        })
        self.assertEqual(hybrid["selected_strategy"], "hybrid_shim_and_lora")

    def test_paired_bootstrap_promotion_gate(self) -> None:
        base = [0.40, 0.50, 0.30, 0.45, 0.35, 0.50, 0.40, 0.30, 0.45, 0.35] * 4
        cand = [0.65, 0.70, 0.55, 0.65, 0.60, 0.75, 0.60, 0.55, 0.70, 0.60] * 4
        ret_b = [0.80, 0.85, 0.75, 0.80, 0.90] * 8
        ret_c = [0.80, 0.84, 0.76, 0.80, 0.90] * 8
        halluc = [0] * 40

        passed = evaluate_promotion_gate(
            target_baseline=base,
            target_candidate=cand,
            retention_baseline=ret_b,
            retention_candidate=ret_c,
            candidate_hallucination_flags=halluc,
            seed=42,
        )
        self.assertTrue(passed["promote"])
        self.assertEqual(passed["failed_gates"], [])

        regressed = evaluate_promotion_gate(
            target_baseline=base,
            target_candidate=cand,
            retention_baseline=ret_b,
            retention_candidate=[v - 0.08 for v in ret_b],
            candidate_hallucination_flags=[1, 1, 0, 0] * 10,
            seed=42,
        )
        self.assertFalse(regressed["promote"])
        self.assertIn("general_retention_regression", regressed["failed_gates"])
        self.assertIn("hallucination_rate_exceeded", regressed["failed_gates"])

    def test_pack_worked_example_recomputes_exactly(self) -> None:
        source = json.loads(PACK_SOURCE.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in source["nouns"]}
        inp = nouns["example.post-cutoff-bundle"]
        expected = nouns["example.gate-decision"]["instance"]

        pairs = compile_post_cutoff_pairs(inp["task_objects"])
        disj = check_holdout_disjointness(pairs, inp["holdout_prompts"])
        route = route_adaptation_strategy(inp["routing_spec"])
        gate = evaluate_promotion_gate(**inp["holdout_eval"], seed=42)

        self.assertEqual(len(pairs), expected["compiled_pair_count"])
        self.assertEqual(disj["disjoint"], expected["holdout_disjoint"])
        self.assertEqual(route["selected_strategy"], expected["selected_strategy"])
        self.assertEqual(gate["promote"], expected["promote"])
        self.assertEqual(gate["target_gain"]["ci_low"], expected["target_gain_ci_low"])


if __name__ == "__main__":
    unittest.main()
