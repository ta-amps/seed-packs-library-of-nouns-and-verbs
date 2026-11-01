"""Unit and conformance tests for constructible_node."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from constructible_node import (
    DomainAgnosticNamingGate,
    ZeroHardcodedValuesAstGate,
    load_default_grid_spec,
    run_bundle,
)


WORKED_BUNDLE = {
    "substrate": {
        "entities": [
            {
                "entity_id": "ENT-101",
                "cohort_id": "COHORT-COASTAL",
                "hazard_index": 0.42,
                "feature_vector": [0.9, 0.2, 0.8],
                "tags": ["resilient_roof", "elevated_grade"],
            },
            {
                "entity_id": "ENT-102",
                "cohort_id": "COHORT-COASTAL",
                "hazard_index": 0.78,
                "feature_vector": [0.85, 0.3, 0.75],
                "tags": ["floodway_adjacent", "unreinforced_frame"],
            },
            {
                "entity_id": "ENT-103",
                "cohort_id": "COHORT-COASTAL",
                "hazard_index": 0.31,
                "feature_vector": [0.88, 0.25, 0.82],
                "tags": ["resilient_roof", "solar_ready"],
            },
        ],
        "actors": [
            {"actor_id": "ACT-A1", "tags": ["coastal_specialist", "resilient_roof"]},
            {"actor_id": "ACT-A2", "tags": ["floodway_adjacent"]},
        ],
        "series": {
            "ENT-101": [1.1, 1.25, 1.4, 1.55]
        },
    },
    "envelopes": [
        {
            "actor_id": "ACT-REQ-1",
            "intent_kind": "point_lookup",
            "entity_id": "ENT-101",
            "query_text": "Return verified baseline attributes for ENT-101",
            "operating_preset": "full_20_stage_frontier_supernode",
        },
        {
            "actor_id": "ACT-REQ-2",
            "intent_kind": "point_lookup",
            "entity_id": "ENT-101",
            "query_text": "Return verified baseline attributes for ENT-101",
            "operating_preset": "full_20_stage_frontier_supernode",
        },
        {
            "actor_id": "ACT-REQ-1",
            "intent_kind": "cohort_percentile",
            "entity_id": "ENT-101",
            "query_text": "Compare hazard cohort percentile with updated drift feed",
            "operating_preset": "full_20_stage_frontier_supernode",
        },
        {
            "actor_id": "ACT-REQ-1",
            "intent_kind": "appetite_exclusion_match",
            "cohort_id": "COHORT-COASTAL",
            "appetite_vector": [0.9, 0.2, 0.8],
            "negative_tags": ["floodway_adjacent"],
            "query_text": "Match appetite entities and peer actors excluding floodway_adjacent",
            "operating_preset": "full_20_stage_frontier_supernode",
            "require_narrative_synthesis": True,
        },
        {
            "actor_id": "ACT-REQ-1",
            "intent_kind": "ols_trend",
            "entity_id": "ENT-101",
            "temporal_horizon": "multi_epoch_series",
            "query_text": "Compute longitudinal trajectory slope for ENT-101",
            "operating_preset": "full_20_stage_frontier_supernode",
        },
        {
            "actor_id": "ACT-REQ-3",
            "intent_kind": "ad_hoc_summary",
            "entity_id": "ENT-103",
            "query_text": "Delegate simple summary to pi harness cell",
            "operating_preset": "minimal_cli_harness_delegate",
            "harness_cell": "pi_fast_delegator",
        },
        {
            "actor_id": "ACT-REQ-4",
            "intent_kind": "cross_shock_elasticity",
            "entity_id": "ENT-101",
            "query_text": "Compute unserved cross-shock elasticity metric",
            "operating_preset": "full_20_stage_frontier_supernode",
            "harness_cell": "opencode_structured_builder",
        },
        {
            "actor_id": "ACT-REQ-5",
            "intent_kind": "cross_shock_elasticity",
            "entity_id": "ENT-102",
            "query_text": "Compute unserved cross-shock elasticity metric",
            "operating_preset": "full_20_stage_frontier_supernode",
            "harness_cell": "opencode_structured_builder",
        },
        {
            "actor_id": "ACT-REQ-6",
            "intent_kind": "cross_shock_elasticity",
            "entity_id": "ENT-103",
            "query_text": "Compute unserved cross-shock elasticity metric",
            "operating_preset": "full_20_stage_frontier_supernode",
            "harness_cell": "opencode_structured_builder",
        },
    ],
    "post_spinout_envelope": {
        "actor_id": "ACT-REQ-7",
        "intent_kind": "cross_shock_elasticity",
        "entity_id": "ENT-102",
        "query_text": "Compute cross-shock elasticity after spinout block admission",
        "operating_preset": "full_20_stage_frontier_supernode",
    },
    "auto_admit_verified_spinout": True,
    "magic_code_sample": "def bad_timeout(x: int) -> int:\n    return x + 45\n",
    "industry_coupled_sample": "class MortgagePipeline:\n    pass\n",
}


class TestConstructibleNode(unittest.TestCase):
    def test_worked_bundle_recomputes_receipt_and_spinout_acceleration(self) -> None:
        receipt = run_bundle(WORKED_BUNDLE)
        expected = {
            "all_persona_panels_passed": True,
            "cache_short_circuits": 1,
            "engine_ast_violations": 0,
            "excluded_tag_leaks": 0,
            "fresh_resource_hydrations": 2,
            "post_spinout_rung": "rung_2_typed_code_blocks",
            "post_spinout_tokens": 0,
            "sample_domain_naming_violations": 1,
            "sample_magic_ast_violations": 1,
            "spinout_verbs_proposed": 1,
            "total_envelopes_executed": 10,
            "zero_token_executions": 5,
        }
        self.assertEqual(receipt, expected)

    def test_package_passes_ast_and_domain_agnostic_gates(self) -> None:
        spec = load_default_grid_spec()
        pkg_dir = Path(__file__).resolve().parent.parent / "constructible_node"
        for py_path in sorted(pkg_dir.glob("*.py")):
            src = py_path.read_text(encoding="utf-8")
            self.assertEqual(ZeroHardcodedValuesAstGate.scan_source(src, str(py_path)), [])
            self.assertEqual(
                DomainAgnosticNamingGate.scan_source(src, list(spec["banned_domain_terms"]), str(py_path)),
                [],
            )

    def test_source_json_example_matches_recomputed_receipt_when_present(self) -> None:
        source_json = Path(__file__).resolve().parents[2] / "source.json"
        if not source_json.is_file():
            return
        doc = json.loads(source_json.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n for n in doc["nouns"]}
        bundle_val = dict(nouns["example.constructible-node-bundle"]["value"])
        bundle_val.pop("shows", None)
        bundle_val.pop("source", None)
        recomputed = run_bundle(bundle_val)
        recorded = nouns["example.constructible-node-receipt"]["value"]["instance"]
        self.assertEqual(recomputed, recorded)


if __name__ == "__main__":
    unittest.main()
