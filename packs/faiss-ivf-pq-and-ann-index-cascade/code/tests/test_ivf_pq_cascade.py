"""Unit tests and mechanical AST conformance gate for ivf_pq_cascade."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ivf_pq_cascade import (
    NodeGrid,
    ProductQuantizedIvfIndex,
    ZeroHardcodedValuesAstGate,
    benchmark_ivf_pq_regimes,
    exact_knn,
    generate_clustered_corpus,
    load_default_grid_spec,
    scan_directory_for_hardcoded_values,
)
from ivf_pq_cascade.__main__ import run_bundle

CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "ivf_pq_cascade"
PACK_DIR = CODE_DIR.parent


class TestIvfPqCascade(unittest.TestCase):
    def test_zero_hardcoded_values_ast_gate(self) -> None:
        violations = scan_directory_for_hardcoded_values(PKG_DIR)
        self.assertEqual(violations, [], f"AST magic literal violations: {violations}")
        summary = ZeroHardcodedValuesAstGate().scan_paths([PKG_DIR])
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["violation_count"], 0)

    def test_grid_constraints_and_regime_resolution(self) -> None:
        spec = load_default_grid_spec()
        grid = NodeGrid(spec)
        fast_cell = grid.resolve_regime("fast_compact")
        high_cell = grid.resolve_regime("high_recall")
        self.assertTrue(grid.is_applicable(fast_cell))
        self.assertTrue(grid.is_applicable(high_cell))

        bad_rerank = dict(fast_cell)
        bad_rerank["use_exact_rerank"] = False
        bad_rerank["rerank_top_r"] = 20
        self.assertFalse(grid.is_applicable(bad_rerank))

        bad_probe = dict(high_cell)
        bad_probe["nlist"] = 4
        bad_probe["nprobe"] = 8
        self.assertFalse(grid.is_applicable(bad_probe))

    def test_uint8_pq_code_storage_and_memory_compression(self) -> None:
        corpus = generate_clustered_corpus()
        idx = ProductQuantizedIvfIndex(regime_name="fast_compact").fit(
            corpus["vectors"], corpus["doc_ids"]
        )
        mem = idx.memory_footprint()
        self.assertEqual(mem["pq_code_bytes_per_vector"], 4)
        self.assertEqual(mem["compression_ratio_vs_float64"], 64.0)
        self.assertEqual(mem["compression_ratio_vs_float32"], 32.0)
        self.assertEqual(mem["total_pq_payload_bytes"], 192 * 4)

        total_entries = 0
        for inv_list in idx.inverted_lists:
            for _, pq_bytes in inv_list:
                self.assertIsInstance(pq_bytes, bytes)
                self.assertEqual(len(pq_bytes), 4)
                total_entries += 1
        self.assertEqual(total_entries, 192)

    def test_non_divisible_dimension_rejected(self) -> None:
        idx = ProductQuantizedIvfIndex(regime_name="high_recall")
        with self.assertRaises(ValueError):
            idx.fit([[1.0, 2.0, 3.0, 4.0, 5.0]])

    def test_exact_rerank_improves_or_matches_adc_recall(self) -> None:
        corpus = generate_clustered_corpus()
        vectors = corpus["vectors"]
        doc_ids = corpus["doc_ids"]
        queries = corpus["queries"]

        idx_no_rerank = ProductQuantizedIvfIndex(
            regime_name="high_recall",
            cell_overrides={"use_exact_rerank": False, "rerank_top_r": 0},
        ).fit(vectors, doc_ids)
        idx_rerank = ProductQuantizedIvfIndex(regime_name="high_recall").fit(vectors, doc_ids)

        hits_adc = 0
        hits_rerank = 0
        for q_vec in queries:
            gt = set(exact_knn(vectors, doc_ids, q_vec, top_k=5))
            r_adc = {h["doc_id"] for h in idx_no_rerank.search(q_vec, top_k=5)["hits"]}
            r_rer = {h["doc_id"] for h in idx_rerank.search(q_vec, top_k=5)["hits"]}
            hits_adc += len(gt & r_adc)
            hits_rerank += len(gt & r_rer)

        self.assertGreaterEqual(hits_rerank, hits_adc)
        self.assertEqual(hits_rerank, len(queries) * 5)

    def test_high_recall_beats_fast_compact_recall(self) -> None:
        corpus = generate_clustered_corpus()
        report = benchmark_ivf_pq_regimes(
            corpus["vectors"],
            corpus["queries"],
            doc_ids=corpus["doc_ids"],
            top_k=5,
        )
        fast = report["regimes"]["fast_compact"]
        high = report["regimes"]["high_recall"]
        self.assertGreater(fast["compression_ratio_vs_float64"], high["compression_ratio_vs_float64"])
        self.assertGreater(high["recall_at_k"], fast["recall_at_k"])
        self.assertEqual(high["recall_at_k"], 1.0)

    def test_worked_example_bundle_and_cli_match_receipt(self) -> None:
        source_doc = json.loads((PACK_DIR / "source.json").read_text(encoding="utf-8"))
        bundle_noun = next(
            n for n in source_doc["nouns"] if n["slug"] == "example.ivf-pq-cascade-bundle"
        )
        receipt_noun = next(
            n for n in source_doc["nouns"] if n["slug"] == "example.ivf-pq-cascade-receipt"
        )
        bundle_payload = dict(bundle_noun["value"])
        expected_receipt = receipt_noun["value"]["instance"]

        recomputed = run_bundle(bundle_payload)
        self.assertEqual(recomputed, expected_receipt)

        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle_path = Path(tmp_dir) / "bundle.json"
            bundle_path.write_text(json.dumps(bundle_payload), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "ivf_pq_cascade", "--bundle", str(bundle_path)],
                cwd=str(CODE_DIR),
                check=True,
                capture_output=True,
                text=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out, expected_receipt)


if __name__ == "__main__":
    unittest.main()
