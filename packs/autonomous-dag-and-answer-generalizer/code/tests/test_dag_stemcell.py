"""Unit and conformance tests for dag_stemcell."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from dag_stemcell import (
    DomainAgnosticNamingGate,
    ZeroHardcodedValuesAstGate,
    load_default_grid_spec,
    run_bundle,
)


WORKED_BUNDLE = {
    "surge_requirements": {
        "parallel_width": 8,
        "wave_depth": 7,
        "coalesce_batch": 6,
        "low_canary_rate": 0.02,
    },
    "decision_fork": {
        "quality_floor": 0.98,
        "latency_sla_ms": 48.0,
        "cost_ceiling_usd": 0.0095,
        "endpoint_a": {
            "option_id": "pure_waterfall",
            "expected_quality": 0.94,
            "expected_latency_ms": 120.0,
            "expected_cost_usd": 0.0028,
        },
        "endpoint_b": {
            "option_id": "pure_broadcast_race",
            "expected_quality": 0.975,
            "expected_latency_ms": 21.0,
            "expected_cost_usd": 0.0145,
        },
    },
    "evsi_utility_gains": [0.0042, 0.00005, 0.00002, 0.00001],
    "shapley_probe": {
        "edge_ms": {
            "v_ingest->v_alpha": 4.0,
            "v_ingest->v_beta_culprit": 38.0,
            "v_alpha->v_join": 2.0,
            "v_beta_culprit->v_join": 2.5,
        },
        "baseline_ms": 3.0,
        "expected_culprit": "v_ingest->v_beta_culprit",
    },
    "scatter_gather": {
        "values": [40.0, 80.0, 120.0, 160.0],
        "weights": [0.25, 0.25, 0.25, 0.25],
    },
    "cegis_stream": [
        {"quantity": 10.0, "unit_amount": 2.5},
        {"quantity": 4.0, "unit_amount": 7.5},
        {"quantity": 12.0, "unit_amount": 5.0, "attenuation_ratio": 0.2, "gain_factor": 1.5},
    ],
    "query_text": "Execute recalibration drift_6h surge_window synthesis across homogeneous tasks",
    "homogeneous_envelopes_count": 6,
    "magic_code_sample": "def bad_limit(x: int) -> int:\n    return x + 45\n",
    "industry_coupled_sample": "class MortgagePipeline:\n    pass\n",
}


class TestDagStemcellPack(unittest.TestCase):
    def test_worked_bundle_recomputes_exact_receipt(self) -> None:
        receipt = run_bundle(WORKED_BUNDLE)
        expected = {
            "blueprint_active_version_after_drift": 2,
            "canary_drift_demotions": 1,
            "coalesced_batch_k": 6,
            "distinct_dag_profiles_compiled": 7,
            "engine_ast_violations": 0,
            "ephemeral_retained": 0,
            "evsi_pruned_branches": 3,
            "final_grid_generation": 2,
            "fresh_delta_pulls": 2,
            "human_scalar_prompts_issued": 0,
            "maker_checker_violations": 0,
            "manifold_candidates_evaluated": 5,
            "sample_domain_naming_violations": 1,
            "sample_magic_ast_violations": 1,
            "shapley_culprit_matched": True,
            "sprawled_repos": 0,
            "subprocess_merged_value": 100.0,
        }
        self.assertEqual(receipt, expected)

    def test_package_passes_ast_and_domain_agnostic_gates(self) -> None:
        spec = load_default_grid_spec()
        pkg_dir = Path(__file__).resolve().parent.parent / "dag_stemcell"
        for py_path in sorted(pkg_dir.glob("*.py")):
            src = py_path.read_text(encoding="utf-8")
            self.assertEqual(
                ZeroHardcodedValuesAstGate.scan_source(
                    src,
                    spec["allowed_identity_numbers"],
                    str(py_path),
                ),
                [],
            )
            self.assertEqual(
                DomainAgnosticNamingGate.scan_source(
                    src,
                    spec["forbidden_industry_tokens"],
                    str(py_path),
                ),
                [],
            )

    def test_source_json_example_matches_recomputed_receipt_when_present(self) -> None:
        source_json = Path(__file__).resolve().parents[2] / "source.json"
        if not source_json.is_file():
            return
        doc = json.loads(source_json.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n for n in doc["nouns"]}
        bundle_val = dict(nouns["example.dag-stemcell-bundle"]["value"])
        bundle_val.pop("shows", None)
        bundle_val.pop("source", None)
        recomputed = run_bundle(bundle_val)
        recorded = nouns["example.dag-stemcell-receipt"]["value"]["instance"]
        self.assertEqual(recomputed, recorded)


if __name__ == "__main__":
    unittest.main()
