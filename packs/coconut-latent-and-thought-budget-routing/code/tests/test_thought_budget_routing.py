"""Unit tests for coconut-latent-and-thought-budget-routing (including AST magic-literal gate)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from thought_budget_routing import (
    AdaptiveReasoningBudgetRouter,
    LatentStateSketchCompressor,
    NodeGrid,
    OverthinkingLoopDetector,
    ZeroHardcodedValuesAstGate,
    scan_directory_for_hardcoded_values,
)
from thought_budget_routing.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "thought_budget_routing"


class ThoughtBudgetRoutingTests(unittest.TestCase):
    def test_zero_hardcoded_values_ast_gate_clean(self) -> None:
        violations = scan_directory_for_hardcoded_values(PKG_DIR)
        self.assertEqual(violations, [], f"Unexpected magic literals: {violations}")
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"])
        self.assertGreaterEqual(report["files_scanned"], 6)

        bad_scan = ZeroHardcodedValuesAstGate.scan_source("def bad_budget() -> int:\n    return 512\n")
        self.assertFalse(bad_scan["passed"])

    def test_node_grid_constraints_and_auto_expansion(self) -> None:
        grid = NodeGrid()
        self.assertFalse(
            grid.is_applicable(
                {
                    "direct_score_ceiling": 0.3,
                    "sketch_score_ceiling": 0.45,
                    "checkpoint_score_ceiling": 0.78,
                    "latent_vector_dims": 16,
                    "loop_cosine_threshold": 0.9,
                    "loop_shingle_jaccard_threshold": 0.55,
                    "stagnation_window": 3,
                    "max_reasoning_tokens": 1024,
                }
            )
        )
        expanded, axes = grid.auto_expand_if_saturated({"max_reasoning_tokens": 2048})
        self.assertEqual(expanded.generation, 2)
        self.assertEqual(axes, ["max_reasoning_tokens:high->4096"])

    def test_adaptive_router_spans_all_four_regimes_and_enforces_latency_clamp(self) -> None:
        router = AdaptiveReasoningBudgetRouter(regime="balanced_checkpoint")
        tasks = [
            {
                "id": "trivial_lookup",
                "dependency_depth": 0,
                "branching_factor": 1,
                "ambiguity_distribution": [1.0, 0.0],
                "constraint_count": 0,
            },
            {
                "id": "bounded_transform",
                "dependency_depth": 2,
                "branching_factor": 3,
                "ambiguity_distribution": [0.7, 0.3],
                "constraint_count": 2,
            },
            {
                "id": "stateful_multi_turn",
                "dependency_depth": 5,
                "branching_factor": 5,
                "ambiguity_distribution": [0.4, 0.35, 0.25],
                "constraint_count": 5,
                "multi_turn_state_carry": True,
            },
            {
                "id": "formal_invariant_audit",
                "dependency_depth": 8,
                "branching_factor": 7,
                "ambiguity_distribution": [0.25, 0.25, 0.25, 0.25],
                "constraint_count": 7,
                "requires_formal_proof": True,
            },
            {
                "id": "latency_clamped_deliberation",
                "dependency_depth": 8,
                "branching_factor": 7,
                "ambiguity_distribution": [0.25, 0.25, 0.25, 0.25],
                "constraint_count": 7,
                "requires_formal_proof": True,
                "latency_budget_ms": 650,
            },
        ]
        batch = router.route_batch(tasks)
        by_id = {d["id"]: d for d in batch["decisions"]}
        self.assertEqual(by_id["trivial_lookup"]["selected_regime"], "zero_step_direct")
        self.assertEqual(by_id["trivial_lookup"]["allocated_reasoning_tokens"], 0)
        self.assertEqual(by_id["bounded_transform"]["selected_regime"], "fast_sketch")
        self.assertEqual(by_id["stateful_multi_turn"]["selected_regime"], "compressed_state_checkpoint")
        self.assertEqual(by_id["formal_invariant_audit"]["selected_regime"], "full_deliberative_verify")
        self.assertEqual(
            by_id["latency_clamped_deliberation"]["selected_regime"], "compressed_state_checkpoint"
        )
        self.assertTrue(by_id["latency_clamped_deliberation"]["budget_clamped"])
        self.assertGreater(batch["token_savings_fraction"], 0.35)

    def test_latent_state_compressor_exceeds_3x_compression_with_full_invariant_recall(self) -> None:
        compressor = LatentStateSketchCompressor(regime="balanced_checkpoint")
        digest_a = "a" * 64
        digest_b = "b" * 64
        turns = [
            {
                "thought": (
                    "Let us carefully examine the initial request and reflect thoroughly on what we are "
                    "trying to accomplish here before jumping ahead. Basically we observe epoch=4 and "
                    "quorum_size >= 3 while reviewing the upstream manifest digest "
                    f"{digest_a}. CONSTRAINT: egress_mode == disabled; OBLIGATION: verify_replica_ack; "
                    "OBLIGATION: check_rollback_cursor. Thinking again about whether everything aligns."
                )
            },
            {
                "thought": (
                    "Continuing our careful deliberation and rechecking our earlier notes from the first "
                    "turn so we do not miss anything obvious. Meanwhile replica acknowledgement finished "
                    "cleanly, RESOLVED: verify_replica_ack, and we also pinned snapshot digest "
                    f"{digest_b} with retry_ceiling <= 2 and active_region=us_east."
                )
            },
            {
                "thought": (
                    "Summarizing and pondering the overall multi-turn reasoning trajectory one more time "
                    "to make sure our understanding remains coherent while keeping the open cursor check "
                    "front of mind before emitting the next state transition."
                )
            },
        ]
        gt = {
            "binding_constraints": [
                "egress_mode == disabled",
                "quorum_size >= 3",
                "retry_ceiling <= 2",
            ],
            "open_obligations": ["check_rollback_cursor"],
            "verified_hashes": [digest_a, digest_b],
        }
        res = compressor.compress_trace(turns, ground_truth=gt)
        self.assertGreater(res["compression_ratio"], 3.0)
        self.assertTrue(res["meets_compression_target"])
        self.assertEqual(res["binding_constraint_recall"], 1.0)
        self.assertEqual(res["open_obligation_recall"], 1.0)
        self.assertEqual(res["verified_hash_recall"], 1.0)
        self.assertNotIn("verify_replica_ack", res["checkpoint"]["open_obligations"])
        self.assertIn("verify_replica_ack", res["checkpoint"]["resolved_obligations"])
        self.assertEqual(len(res["checkpoint"]["latent_state_vector"]), 16)

    def test_overthinking_loop_detector_catches_cyclic_paraphrase_without_false_positive(self) -> None:
        detector = OverthinkingLoopDetector(regime="balanced_checkpoint")
        cyclic_steps = [
            "Initialize verifier state schema_rev=2 and CONSTRAINT: max_batch <= 16.",
            "Maybe we should recheck schema_rev and max_batch ordering across candidate batches again.",
            "Wait let us reconsider schema_rev and max_batch ordering across candidate batches carefully.",
            "Thinking again, we should recheck schema_rev and max_batch ordering across candidate batches.",
            "Yet another pass rechecking schema_rev and max_batch ordering across candidate batches.",
        ]
        loop_out = detector.inspect_trace(cyclic_steps)
        self.assertTrue(loop_out["loop_detected"])
        self.assertEqual(loop_out["trigger_step_index"], 3)
        self.assertEqual(loop_out["recommended_action"], "halt_and_emit_checkpoint")
        self.assertGreater(loop_out["tokens_saved_by_early_halt"], 15)

        productive_steps = [
            "Step one establishes partition_count=4 and CONSTRAINT: partition_count >= 2.",
            "Step two derives lease_ttl_sec=30 and OBLIGATION: validate_fencing_token.",
            "Step three verifies fencing witness and records RESOLVED: validate_fencing_token.",
        ]
        prod_out = detector.inspect_trace(productive_steps)
        self.assertFalse(prod_out["loop_detected"])

    def test_worked_example_recomputes_exact_receipt_and_cli_runs(self) -> None:
        source_path = PACK_DIR / "source.json"
        if not source_path.exists():
            return
        src = json.loads(source_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.thought-budget-routing-bundle"]
        expected = nouns["example.thought-budget-routing-receipt"]["instance"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, expected)

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "thought_budget_routing", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out, expected)


if __name__ == "__main__":
    unittest.main()
