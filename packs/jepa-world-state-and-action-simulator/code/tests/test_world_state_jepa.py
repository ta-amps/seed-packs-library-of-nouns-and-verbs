"""Unit tests and mechanical AST conformance gate for world_state_jepa."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from world_state_jepa import (
    ActionConditionedStatePredictor,
    CounterfactualRolloutPlanner,
    EpistemicEnergyAnomalyGate,
    NodeGrid,
    ZeroHardcodedValuesAstGate,
    load_default_grid_spec,
    scan_directory_for_hardcoded_values,
)
from world_state_jepa.__main__ import run_bundle

CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "world_state_jepa"
PACK_DIR = CODE_DIR.parent


class TestWorldStateJepa(unittest.TestCase):
    def test_zero_hardcoded_values_ast_gate(self) -> None:
        violations = scan_directory_for_hardcoded_values(PKG_DIR)
        self.assertEqual(violations, [], f"AST magic literal violations: {violations}")
        summary = ZeroHardcodedValuesAstGate().scan_paths([PKG_DIR])
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["violation_count"], 0)

    def test_grid_constraints_and_regime_defaults(self) -> None:
        spec = load_default_grid_spec()
        grid = NodeGrid(spec)
        prod_cell = grid.resolve_regime("production_fenced_execution")
        self.assertTrue(grid.is_applicable(prod_cell))
        sandbox_cell = grid.resolve_regime("read_only_sandbox_planning")
        self.assertTrue(grid.is_applicable(sandbox_cell))
        invalid_cell = dict(sandbox_cell)
        invalid_cell["allow_irreversible_actions"] = True
        self.assertFalse(grid.is_applicable(invalid_cell))
        enumerated = grid.enumerate_cells()
        self.assertGreater(len(enumerated["represented"]), len(enumerated["applicable"]))

    def test_lease_conflict_and_horizon_clamping(self) -> None:
        predictor = ActionConditionedStatePredictor()
        s0 = predictor.encode_observation({
            "leases": {"rec-shared": {"holder": "worker-owner", "epoch": 3}},
            "resource_quotas": {"compute_units": 0.9},
            "record_digests": {"rec-shared": {"version": 1, "semantic_payload": "s1"}},
            "capability_taints": [],
        })
        contended = predictor.predict_transition(
            s0,
            {"op": "acquire_lease", "actor_id": "worker-other", "target_key": "rec-shared"},
        )
        self.assertFalse(contended["invariants_hold"])
        self.assertFalse(contended["predicted_state"].invariant_predicates["lease_fenced"])
        planner = CounterfactualRolloutPlanner(predictor=predictor, max_rollout_horizon=1)
        self.assertEqual(planner.max_rollout_horizon, 2)

    def test_predictor_blocks_unfenced_tainted_and_stale_cas_writes(self) -> None:
        predictor = ActionConditionedStatePredictor()
        s0 = predictor.encode_observation({
            "leases": {},
            "resource_quotas": {"compute_units": 0.8},
            "record_digests": {"rec-1": {"version": 2, "semantic_payload": "v2"}},
            "capability_taints": ["untrusted_input"],
        })
        bad_commit = predictor.predict_transition(
            s0,
            {
                "action_id": "bad-1",
                "op": "commit_cas_write",
                "actor_id": "worker-a",
                "target_key": "rec-1",
                "expected_version": 1,
                "quota_deltas": {"compute_units": -0.95},
            },
        )
        self.assertFalse(bad_commit["invariants_hold"])
        inv = bad_commit["predicted_state"].invariant_predicates
        self.assertFalse(inv["lease_fenced"])
        self.assertFalse(inv["taint_isolated"])
        self.assertFalse(inv["cas_version_monotonic"])
        self.assertFalse(inv["quota_non_negative"])
        self.assertEqual(bad_commit["predicted_state"].record_digests["rec-1"]["version"], 2)

    def test_epistemic_energy_invariance_to_surface_jitter_and_review_vs_rollback(self) -> None:
        predictor = ActionConditionedStatePredictor()
        gate = EpistemicEnergyAnomalyGate()

        s_clean = predictor.encode_observation({
            "leases": {"rec-1": {"holder": "worker-a", "epoch": 1}},
            "resource_quotas": {"compute_units": 0.8},
            "record_digests": {"rec-1": {"version": 1, "semantic_payload": "payload_x"}},
            "capability_taints": [],
            "surface_timestamp_ms": 100,
        })
        s_jitter = predictor.encode_observation({
            "leases": {"rec-1": {"holder": "worker-a", "epoch": 1}},
            "resource_quotas": {"compute_units": 0.8},
            "record_digests": {"rec-1": {"version": 1, "semantic_payload": "  payload_x \n\t"}},
            "capability_taints": [],
            "surface_timestamp_ms": 999999,
            "extra_log_banner": "ignored-by-representation-encoder",
        })
        res_jitter = gate.evaluate_surprise(s_clean, s_jitter)
        self.assertEqual(res_jitter["total_surprise_energy"], 0.0)
        self.assertEqual(res_jitter["decision"], "continue")

        # Moderate quota drift -> require_review
        s_drift = predictor.encode_observation({
            "leases": {"rec-1": {"holder": "worker-a", "epoch": 1}},
            "resource_quotas": {"compute_units": 0.4},
            "record_digests": {"rec-1": {"version": 1, "semantic_payload": "payload_x"}},
            "capability_taints": [],
        })
        res_drift = gate.evaluate_surprise(s_clean, s_drift)
        self.assertEqual(res_drift["decision"], "require_review")

        # Stolen lease + unpredicted taint -> trigger_rollback
        s_hijack = predictor.encode_observation({
            "leases": {"rec-1": {"holder": "worker-rogue", "epoch": 2}},
            "resource_quotas": {"compute_units": 0.8},
            "record_digests": {"rec-1": {"version": 1, "semantic_payload": "payload_x"}},
            "capability_taints": ["untrusted_input"],
        })
        res_hijack = gate.evaluate_surprise(s_clean, s_hijack)
        self.assertEqual(res_hijack["decision"], "trigger_rollback")
        self.assertGreaterEqual(res_hijack["total_surprise_energy"], gate.rollback_energy_threshold)

    def test_counterfactual_rollout_planner_ranks_clean_trajectory_first(self) -> None:
        source_doc = json.loads((PACK_DIR / "source.json").read_text(encoding="utf-8"))
        bundle_noun = next(
            n for n in source_doc["nouns"] if n["slug"] == "example.world-state-jepa-bundle"
        )
        predictor = ActionConditionedStatePredictor()
        planner = CounterfactualRolloutPlanner(predictor=predictor)
        s0 = predictor.encode_observation(bundle_noun["value"]["initial_observation"])
        ranked = planner.rank_candidates(
            initial_state=s0,
            candidates=bundle_noun["value"]["candidate_sequences"],
            goal=bundle_noun["value"]["goal"],
        )
        self.assertEqual(ranked["recommended_sequence_id"], "plan-fenced-sanitized-clean")
        self.assertEqual(ranked["feasible_count"], 2)
        self.assertFalse(ranked["ranked_sequences"][-1]["feasible"])
        self.assertEqual(ranked["ranked_sequences"][-1]["sequence_id"], "plan-reckless-unfenced")

    def test_worked_example_bundle_and_cli_match_receipt(self) -> None:
        source_doc = json.loads((PACK_DIR / "source.json").read_text(encoding="utf-8"))
        bundle_noun = next(
            n for n in source_doc["nouns"] if n["slug"] == "example.world-state-jepa-bundle"
        )
        receipt_noun = next(
            n for n in source_doc["nouns"] if n["slug"] == "example.world-state-jepa-receipt"
        )
        bundle_payload = dict(bundle_noun["value"])
        expected_receipt = receipt_noun["value"]["instance"]

        recomputed = run_bundle(bundle_payload)
        self.assertEqual(recomputed, expected_receipt)

        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle_path = Path(tmp_dir) / "bundle.json"
            bundle_path.write_text(json.dumps(bundle_payload), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "world_state_jepa", "--bundle", str(bundle_path)],
                cwd=str(CODE_DIR),
                check=True,
                capture_output=True,
                text=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out, expected_receipt)


if __name__ == "__main__":
    unittest.main()
