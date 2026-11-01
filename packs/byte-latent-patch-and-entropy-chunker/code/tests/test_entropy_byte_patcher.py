"""Unit tests for byte-latent-patch-and-entropy-chunker (including AST magic-literal gate)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from entropy_byte_patcher import (
    DynamicByteEntropyPatcher,
    NodeGrid,
    SurpriseProportionalBudgetAllocator,
    ZeroHardcodedValuesAstGate,
    scan_directory_for_hardcoded_values,
)
from entropy_byte_patcher.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "entropy_byte_patcher"


def _sample_corpus() -> list[str]:
    return [
        "FRAME_SYNC::status=verified::mode=deterministic::",
        "FRAME_SYNC::status=verified::mode=deterministic::",
        "FRAME_SYNC::status=verified::mode=deterministic::",
        "FRAME_SYNC::status=verified::mode=deterministic::",
        "                         ",
    ]


class EntropyBytePatcherTests(unittest.TestCase):
    def test_zero_hardcoded_values_ast_gate_clean(self) -> None:
        violations = scan_directory_for_hardcoded_values(PKG_DIR)
        self.assertEqual(violations, [], f"Unexpected magic literals: {violations}")
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"])
        self.assertGreaterEqual(report["files_scanned"], 6)

        bad_scan = ZeroHardcodedValuesAstGate.scan_source("def bad_alpha() -> float:\n    return 256.0\n")
        self.assertFalse(bad_scan["passed"])

    def test_node_grid_constraints_and_auto_expansion(self) -> None:
        grid = NodeGrid()
        self.assertFalse(
            grid.is_applicable(
                {
                    "global_entropy_threshold": 2.2,
                    "delta_spike_threshold": 0.6,
                    "min_patch_bytes": 4,
                    "max_patch_bytes": 32,
                    "context_order": 2,
                    "prior_concentration": 0.25,
                    "total_inspection_budget": 64,
                    "min_slots_per_patch": 0,
                }
            )
        )
        expanded, axes = grid.auto_expand_if_saturated({"max_patch_bytes": 64})
        self.assertEqual(expanded.generation, 2)
        self.assertEqual(axes, ["max_patch_bytes:high->128"])

    def test_dynamic_entropy_patcher_lossless_and_Adapts_patch_lengths_to_entropy(self) -> None:
        patcher = DynamicByteEntropyPatcher(regime="balanced_entropy_patch")
        patcher.fit_corpus(_sample_corpus())

        stream = (
            "FRAME_SYNC::status=verified::mode=deterministic::"
            "Xq9!kZ7#vP2@mR8$"
            "FRAME_SYNC::status=verified::mode=deterministic::"
        )
        seg = patcher.segment_stream(stream, online_update=False)
        self.assertTrue(seg["reconstructed_exact"])
        self.assertEqual(seg["total_bytes"], len(stream.encode("utf-8")))

        patches = seg["patches"]
        for p in patches[:-1]:
            self.assertGreaterEqual(p["byte_length"], 4)
            self.assertLessEqual(p["byte_length"], 32)

        low_entropy_lengths = [
            p["byte_length"] for p in patches if p["mean_entropy_bits"] < 2.8
        ]
        high_entropy_lengths = [
            p["byte_length"] for p in patches if p["mean_entropy_bits"] >= 2.8
        ]
        self.assertTrue(low_entropy_lengths)
        self.assertTrue(high_entropy_lengths)
        self.assertGreater(
            sum(low_entropy_lengths) / len(low_entropy_lengths),
            sum(high_entropy_lengths) / len(high_entropy_lengths),
        )

    def test_surprise_proportional_allocator_concentrates_budget_on_high_surprise_patches(self) -> None:
        patcher = DynamicByteEntropyPatcher(regime="balanced_entropy_patch")
        patcher.fit_corpus(_sample_corpus())
        stream = (
            "FRAME_SYNC::status=verified::mode=deterministic::"
            "Xq9!kZ7#vP2@mR8$"
            "FRAME_SYNC::status=verified::mode=deterministic::"
        )
        seg = patcher.segment_stream(stream, online_update=False)
        allocator = SurpriseProportionalBudgetAllocator(regime="balanced_entropy_patch")
        alloc = allocator.allocate_budget(seg["patches"])
        self.assertEqual(
            sum(a["surprise_slots"] for a in alloc["allocations"]),
            alloc["total_budget"],
        )
        self.assertGreater(
            alloc["high_entropy_surprise_budget_share"],
            alloc["high_entropy_byte_budget_share"],
        )
        self.assertGreater(alloc["high_entropy_focus_gain"], 0.15)

    def test_corruption_robustness_resyncs_boundaries_better_than_fixed_stride(self) -> None:
        corpus = _sample_corpus()
        allocator = SurpriseProportionalBudgetAllocator(regime="balanced_entropy_patch")

        clean = (
            "Q7#FRAME_SYNC::status=verified::mode=deterministic::"
            "K9@FRAME_SYNC::status=verified::mode=deterministic::"
            "Z3!FRAME_SYNC::status=verified::mode=deterministic::"
        )
        # Prefix byte insertion ("X") shifts every downstream fixed-stride 8-byte chunk by +1 byte,
        # whereas dynamic entropy patching re-anchors immediately at the next entropy transition.
        corrupted = "X" + clean

        bench = allocator.benchmark_corruption_robustness(
            clean, corrupted, calibration_corpus=corpus, online_update=False
        )
        self.assertTrue(bench["clean_reconstructed_exact"])
        self.assertTrue(bench["corrupted_reconstructed_exact"])
        self.assertGreater(
            bench["dynamic_preserved_patch_fraction"],
            bench["fixed_stride_preserved_chunk_fraction"],
        )
        self.assertGreater(bench["boundary_resync_gain"], 0.5)

    def test_worked_example_recomputes_exact_receipt_and_cli_runs(self) -> None:
        source_path = PACK_DIR / "source.json"
        if not source_path.exists():
            return
        src = json.loads(source_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.entropy-byte-patcher-bundle"]
        expected = nouns["example.entropy-byte-patcher-receipt"]["instance"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, expected)

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "entropy_byte_patcher", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out, expected)


if __name__ == "__main__":
    unittest.main()
