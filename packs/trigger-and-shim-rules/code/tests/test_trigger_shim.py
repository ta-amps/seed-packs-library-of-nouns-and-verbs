"""Unit tests for trigger-and-shim-rules (including self-conformance AST gate)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from trigger_shim import (
    ConversationDedupAndSubmodularKnapsack,
    HarnessTaxAndThreeRegimeRouter,
    ThreeTierTriggerEngine,
    WhichFitsCompatibilityMatcher,
    ZeroHardcodedValuesAstGate,
    recommend_which_fits,
)
from trigger_shim.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "trigger_shim"


class TriggerShimTests(unittest.TestCase):
    def test_package_passes_zero_hardcoded_values_ast_gate(self) -> None:
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"], f"Unexpected magic literals in trigger_shim: {report}")
        self.assertEqual(report["violation_count"], 0)

        bad_code = "class Bad:\n    LIMIT = 42\ndef f(x: int) -> int:\n    return x + 7\n"
        bad_report = ZeroHardcodedValuesAstGate.scan_source(bad_code, source_name="bad_sample.py")
        self.assertFalse(bad_report["passed"])
        self.assertEqual(bad_report["violation_count"], 2)

    def test_three_tier_trigger_engine_frame_isomorphism_veto_and_governance(self) -> None:
        engine = ThreeTierTriggerEngine()
        # Paraphrased query shares Role-Filler Frame (claim/acquire, lease/fencing, err_409)
        query = {
            "text": "worker renewal stalled on lock conflict 409",
            "tool_name": "store.cas_write",
            "role_frame": {
                "verb_frame": "acquire",
                "object_slot": "lock",
                "error_code_slot": "err_409",
            },
            "allow_direct_response": True,
        }
        rules = [
            {
                "rule_id": "frame_match_shim",
                "exemplar_text": "claim fencing token 409",
                "tool_globs": ["store.*"],
                "role_frame": {
                    "verb_frame": "claim",
                    "object_slot": "fencing",
                    "error_code_slot": "err_409",
                },
                "governance_status": "verified",
                "shim_tokens": 64,
            },
            {
                "rule_id": "conflicting_frame",
                "exemplar_text": "claim fencing token",
                "role_frame": {
                    "verb_frame": "claim",
                    "object_slot": "fencing",
                    "error_code_slot": "err_503",
                },
                "governance_status": "verified",
                "shim_tokens": 64,
            },
            {
                "rule_id": "vetoed_rule",
                "exemplar_text": "worker renewal stalled on lock conflict 409",
                "exclude_keywords": ["stalled"],
                "governance_status": "verified",
            },
            {
                "rule_id": "quarantined_rule",
                "exemplar_text": "worker renewal stalled on lock conflict 409",
                "governance_status": "quarantined",
            },
        ]
        res = engine.evaluate_all(query, rules)
        by_id = {ev["rule_id"]: ev for ev in res["evaluations"]}
        self.assertTrue(by_id["frame_match_shim"]["matched"])
        self.assertGreater(by_id["frame_match_shim"]["frame_bonus"], 0.0)
        self.assertEqual(by_id["conflicting_frame"]["frame_bonus"], 0.0)
        self.assertEqual(by_id["vetoed_rule"]["rejected_tier"], "tier1_exclude_veto")
        self.assertEqual(by_id["quarantined_rule"]["rejected_tier"], "tier3_quarantined_governance")

    def test_conversation_dedup_and_submodular_knapsack(self) -> None:
        knapsack = ConversationDedupAndSubmodularKnapsack({"token_budget": 160, "max_total_chars": 640})
        history = [
            "System turn 1:\n[PROVISION: prov.once@v1]\nInitial contract.",
            "Turn 2 error:\n[ERROR_SIG: sig_timeout]\n[PROVISION: prov.err_answered@v1]\nHandled.",
        ]
        provisions = [
            {
                "provision_id": "prov.once",
                "version": 1,
                "dedup_mode": "once_per_conversation",
                "utility": 0.99,
                "tokens": 40,
                "text": "Initial contract already in context.",
            },
            {
                "provision_id": "prov.err_answered",
                "version": 1,
                "dedup_mode": "on_error_signature",
                "error_signature": "sig_timeout",
                "utility": 0.95,
                "tokens": 40,
                "text": "Already shimmed after latest sig_timeout.",
            },
            {
                "provision_id": "prov.primary",
                "version": 1,
                "dedup_mode": "every_turn",
                "utility": 0.90,
                "tokens": 80,
                "text": "Verify CAS fencing token version before writing state envelope.",
            },
            {
                "provision_id": "prov.near_dup",
                "version": 1,
                "dedup_mode": "every_turn",
                "utility": 0.88,
                "tokens": 80,
                "text": "Verify CAS fencing token version before writing state envelope.",
            },
            {
                "provision_id": "prov.orthogonal",
                "version": 1,
                "dedup_mode": "once_per_conversation",
                "utility": 0.70,
                "tokens": 75,
                "text": "Bound retry jitter and preserve deterministic idempotency keys.",
            },
        ]
        packed = knapsack.pack_provisions(
            provisions,
            history,
            current_error_signature="sig_timeout",
        )
        # prov.once and prov.err_answered are deduplicated; prov.near_dup is discounted by redundancy penalty,
        # so prov.primary + prov.orthogonal win under the 160-token ceiling!
        self.assertEqual(packed["selected_provision_ids"], ["prov.primary", "prov.orthogonal"])
        self.assertLessEqual(packed["total_tokens"], 160)
        self.assertLessEqual(packed["total_chars"], 640)
        self.assertIn("[PROVISION: prov.primary@v1]", packed["injected_context"])

    def test_harness_tax_and_three_regime_router(self) -> None:
        router = HarnessTaxAndThreeRegimeRouter()
        tax = router.compute_harness_tax(
            prefix_tokens_p=1200,
            content_tokens_c=1200,
            slice_count_k=4,
            observed_skip_rate=0.65,
        )
        self.assertAlmostEqual(tax["break_even_skip_rate"], 0.6, places=6)
        self.assertTrue(tax["slicing_saves_tokens"])

        self.assertEqual(
            router.route_intervention_regime(
                {"is_deterministic_validator_or_parser": True, "shim_tokens": 100, "train_tokens": 10000}
            )["selected_regime"],
            "deterministic_code_shim",
        )
        self.assertEqual(
            router.route_intervention_regime(
                {
                    "requires_instant_revocation": True,
                    "churn_half_life_days": 60,
                    "shim_tokens": 200,
                    "train_tokens": 10000,
                    "expected_horizon_calls": 500,
                }
            )["selected_regime"],
            "ephemeral_context_shim",
        )
        self.assertEqual(
            router.route_intervention_regime(
                {
                    "churn_half_life_days": 60,
                    "shim_tokens": 200,
                    "train_tokens": 10000,
                    "expected_horizon_calls": 200,
                }
            )["selected_regime"],
            "peft_lora_adapter",
        )
        self.assertEqual(
            router.route_intervention_regime(
                {
                    "has_volatile_sha256_pins": True,
                    "churn_half_life_days": 45,
                    "shim_tokens": 200,
                    "train_tokens": 10000,
                    "expected_horizon_calls": 200,
                }
            )["selected_regime"],
            "hybrid_lora_plus_pointer_shim",
        )

    def test_which_fits_compatibility_matcher_refuses_contributor_training_on_non_public(self) -> None:
        workload = {
            "data_privacy_tier": "internal",
            "churn_half_life_days": 15.0,
            "requires_instant_revocation": True,
            "token_budget": 200,
            "slice_count_k": 3,
            "task_content_tokens_c": 900,
        }
        entries = [
            {
                "entry_id": "contrib_cloud",
                "max_privacy_tier": "confidential",
                "contributor_training_enabled": True,
                "supports_instant_revocation": True,
                "entry_token_overhead": 30,
                "harness_prefix_tokens_p": 200,
                "age_days": 1.0,
                "freshness_half_life_days": 30.0,
            },
            {
                "entry_id": "public_only_feed",
                "max_privacy_tier": "public",
                "contributor_training_enabled": False,
                "supports_instant_revocation": True,
                "entry_token_overhead": 30,
                "harness_prefix_tokens_p": 200,
                "age_days": 1.0,
                "freshness_half_life_days": 30.0,
            },
            {
                "entry_id": "isolated_fast_shim",
                "max_privacy_tier": "confidential",
                "contributor_training_enabled": False,
                "supports_instant_revocation": True,
                "entry_token_overhead": 50,
                "harness_prefix_tokens_p": 300,
                "age_days": 2.0,
                "freshness_half_life_days": 30.0,
                "optimal_half_life_days": 15.0,
            },
        ]
        res = recommend_which_fits(workload, entries)
        self.assertEqual(res["pareto_winners"], ["isolated_fast_shim"])
        disq = {d["entry_id"]: d["disqualified_reasons"] for d in res["disqualified"]}
        self.assertIn("contributor_training_refused_for_non_public_data", disq["contrib_cloud"])
        self.assertIn("insufficient_privacy_tier", disq["public_only_feed"])

    def test_worked_example_and_cli_roundtrip(self) -> None:
        src_path = PACK_DIR / "source.json"
        if not src_path.exists():
            return
        src = json.loads(src_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.trigger-shim-bundle"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, nouns["example.trigger-shim-receipt"]["instance"])

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "trigger_shim", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out, recomputed)


if __name__ == "__main__":
    unittest.main()
