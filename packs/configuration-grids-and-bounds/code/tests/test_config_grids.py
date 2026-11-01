"""Unit tests for configuration-grids-and-bounds (including self-conformance AST check)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from config_grids import (
    GridLedger,
    NodeGrid,
    OperationCostLedger,
    ZeroHardcodedValuesAstGate,
)
from config_grids.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
PKG_DIR = Path(__file__).resolve().parents[1] / "config_grids"


class ConfigGridsTests(unittest.TestCase):
    def test_package_itself_passes_zero_hardcoded_values_ast_gate(self) -> None:
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"], f"Unexpected magic literals in config_grids: {report}")

    def test_constraints_lifecycle_regime_and_boundary_auto_expansion(self) -> None:
        grid = NodeGrid()
        cells = grid.enumerate_cells()
        self.assertEqual(len(cells["represented"]), 72)
        self.assertEqual(len(cells["applicable"]), 48)

        # Inapplicable cell (support_deletes=True with binary_fuse) cannot advance
        ledger = GridLedger(grid)
        bad_res = ledger.transition(
            {
                "shim_max_chars": 1200,
                "probe_radius_bits": 1,
                "filter_strategy": "binary_fuse",
                "support_deletes": True,
            },
            "proposed",
            worker_id="w1",
            key_id="k1",
        )
        self.assertFalse(bad_res["ok"])
        self.assertEqual(bad_res["status_code"], 409)

        # Saturated cell triggers generation 2 expansion on shim_max_chars (2400 -> 4800)
        opt = {
            "shim_max_chars": 2400,
            "probe_radius_bits": 2,
            "filter_strategy": "cuckoo",
            "support_deletes": True,
        }
        next_grid, axes = grid.auto_expand_if_saturated(opt)
        self.assertEqual(next_grid.generation, 2)
        self.assertIn("shim_max_chars:high->4800", axes)
        self.assertIn("probe_radius_bits:high->4", axes)

    def test_worked_example_recomputes_exact_receipt(self) -> None:
        src_path = PACK_DIR / "source.json"
        if not src_path.exists():
            return
        src = json.loads(src_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        recomputed = run_bundle(nouns["example.config-grids-bundle"])
        self.assertEqual(recomputed, nouns["example.config-grids-receipt"]["instance"])


if __name__ == "__main__":
    unittest.main()
