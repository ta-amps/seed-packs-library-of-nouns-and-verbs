"""Unit tests for dora-spinquant-and-adapter-merging (including AST magic-literal gate)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from adapter_quant_and_merge import (
    FastWalshHadamardOutlierRotator,
    NodeGrid,
    SubspaceInterferenceAndMergeRouter,
    WeightDecomposedLoraAnalyzer,
    ZeroHardcodedValuesAstGate,
    load_default_grid_spec,
    scan_directory_for_hardcoded_values,
)
from adapter_quant_and_merge.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "adapter_quant_and_merge"


class AdapterQuantAndMergeTests(unittest.TestCase):
    def test_zero_hardcoded_values_ast_gate_clean(self) -> None:
        self.assertEqual(scan_directory_for_hardcoded_values(PKG_DIR), [])
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"], f"Unexpected magic literals: {report}")
        self.assertGreaterEqual(report["files_scanned"], 6)

        bad = ZeroHardcodedValuesAstGate.scan_source("def leak_magic(x: float) -> float:\n    return x * 0.25 + 7\n")
        self.assertFalse(bad["passed"])
        self.assertEqual(bad["violation_count"], 2)

    def test_node_grid_constraints_and_regime_clamping(self) -> None:
        grid = NodeGrid(load_default_grid_spec())
        cells = grid.enumerate_cells()
        self.assertGreater(len(cells["represented"]), len(cells["applicable"]))
        edge_cell = grid.resolve_regime("low_bit_edge_serving")
        self.assertEqual(edge_cell["quant_bits"], 4)
        self.assertTrue(edge_cell["enable_hadamard_rotation"])
        self.assertTrue(grid.is_applicable(edge_cell))
        invalid_4bit = {**edge_cell, "enable_hadamard_rotation": False}
        self.assertFalse(grid.is_applicable(invalid_4bit))

    def test_fwht_orthogonality_and_exact_round_trip(self) -> None:
        rotator = FastWalshHadamardOutlierRotator(rotation_seed=99, quant_bits=4)
        matrix = rotator.generate_heavy_tailed_channel_matrix(rows=8, cols=32, outlier_channels=2, outlier_scale=20.0)
        rotated = rotator.rotate_matrix(matrix)
        recovered = rotator.inverse_rotate_matrix(rotated)

        # Verify Frobenius energy preservation (Parseval identity) and exact inverse recovery
        orig_energy = sum(val * val for row in matrix for val in row)
        rot_energy = sum(val * val for row in rotated for val in row)
        self.assertAlmostEqual(orig_energy, rot_energy, places=9)
        self.assertLess(rotator.reconstruction_mse(matrix, recovered), 1e-24)

    def test_spinquant_suppresses_kurtosis_and_reduces_4bit_mse_over_10x(self) -> None:
        rotator = FastWalshHadamardOutlierRotator(rotation_seed=1729, quant_bits=4)
        matrix = rotator.generate_heavy_tailed_channel_matrix(
            rows=16, cols=64, outlier_channels=1, outlier_scale=32.0, seed=42
        )
        metrics = rotator.evaluate_quantization(matrix, bits=4)
        self.assertLess(metrics["rotated_max_to_rms"], metrics["unrotated_max_to_rms"] * 0.25)
        self.assertGreater(metrics["unrotated_excess_kurtosis"], 80.0)
        self.assertLess(abs(metrics["rotated_excess_kurtosis"]), 3.0)
        self.assertGreater(metrics["mse_reduction_factor"], 10.0)

    def test_per_tensor_vs_per_row_quantization_supported(self) -> None:
        rotator = FastWalshHadamardOutlierRotator(quant_bits=4, quant_granularity="per_tensor")
        matrix = rotator.generate_heavy_tailed_channel_matrix(rows=8, cols=16, outlier_channels=1, outlier_scale=16.0)
        q_tensor = rotator.quantize_dequantize(matrix, bits=4, granularity="per_tensor")
        q_row = rotator.quantize_dequantize(matrix, bits=4, granularity="per_row")
        self.assertLessEqual(rotator.reconstruction_mse(matrix, q_row), rotator.reconstruction_mse(matrix, q_tensor))

    def test_dora_weight_decomposition_and_directional_synthesis(self) -> None:
        analyzer = WeightDecomposedLoraAnalyzer()
        base_w = [
            [3.0, 0.0],
            [4.0, 2.0],
            [0.0, 0.0],
        ]
        decomp = analyzer.decompose_columns(base_w)
        self.assertAlmostEqual(decomp["magnitudes"][0], 5.0, places=6)
        self.assertAlmostEqual(decomp["magnitudes"][1], 2.0, places=6)

        # Pure orthogonal directional update on row 2
        lora_b = [[0.0], [0.0], [5.0]]
        lora_a = [[1.0, 0.0]]
        composed = analyzer.compose_dora_weights(base_w, lora_b, lora_a, learned_magnitudes=[5.0, 2.0], lora_scale=1.0)
        re_decomp = analyzer.decompose_columns(composed)
        self.assertAlmostEqual(re_decomp["magnitudes"][0], 5.0, places=6)
        self.assertAlmostEqual(re_decomp["magnitudes"][1], 2.0, places=6)

        analysis = analyzer.analyze_low_rank_update(
            base_w, lora_b, lora_a, learned_magnitudes=[5.0, 2.0], lora_scale=1.0
        )
        self.assertAlmostEqual(analysis["mean_relative_magnitude_delta"], 0.0, places=6)
        self.assertGreater(analysis["mean_directional_cosine_delta"], 0.14)
        self.assertGreater(analysis["directional_to_magnitude_ratio"], 1000.0)

    def test_ties_router_static_merge_vs_dynamic_co_resident_switch(self) -> None:
        router = SubspaceInterferenceAndMergeRouter()
        disjoint_a = [[0.9, 0.0], [0.0, 0.0]]
        disjoint_b = [[0.0, 0.0], [0.0, -0.8]]
        res_low = router.route_adapters([disjoint_a, disjoint_b])
        self.assertEqual(res_low["max_abs_frobenius_cosine"], 0.0)
        self.assertEqual(res_low["sign_conflict_density"], 0.0)
        self.assertEqual(res_low["recommended_strategy"], "ties_static_merge")

        conflict_a = [[0.9, -0.7], [0.6, -0.5]]
        conflict_b = [[-0.8, 0.75], [-0.55, 0.45]]
        res_high = router.route_adapters([conflict_a, conflict_b])
        self.assertGreater(res_high["max_abs_frobenius_cosine"], 0.95)
        self.assertEqual(res_high["sign_conflict_density"], 1.0)
        self.assertEqual(res_high["recommended_strategy"], "dynamic_co_resident_switch")

    def test_worked_example_recomputes_exact_receipt_and_cli_runs(self) -> None:
        src = json.loads((PACK_DIR / "source.json").read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.adapter-quant-merge-bundle"]
        expected = nouns["example.adapter-quant-merge-receipt"]["instance"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, expected)

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "adapter_quant_and_merge", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(json.loads(proc.stdout), expected)


if __name__ == "__main__":
    unittest.main()
