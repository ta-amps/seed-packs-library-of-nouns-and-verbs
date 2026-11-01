"""Unit tests for probabilistic-filters-and-sketches (including ZeroHardcodedValuesAstGate self-scan)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from probabilistic_sketches import (
    BlockedBloomFilter,
    ConservativeCountMinHeavyKeeperHll,
    CuckooFilter,
    MinHashLshDecontaminator,
    MultiProbeSimHashLshExpander,
    StaticXorFingerprintFilter,
    ZeroHardcodedValuesAstGate,
    benchmark_simhash_recall,
)
from probabilistic_sketches.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "probabilistic_sketches"


class ProbabilisticSketchesTests(unittest.TestCase):
    def test_package_itself_passes_zero_hardcoded_values_ast_gate(self) -> None:
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"], f"Unexpected magic literals in probabilistic_sketches: {report}")
        self.assertGreaterEqual(report["files_scanned"], 6)

        bad_scan = ZeroHardcodedValuesAstGate.scan_source("def bad_bits(x: int) -> int:\n    return x & 255\n")
        self.assertFalse(bad_scan["passed"])
        self.assertEqual(bad_scan["violation_count"], 1)

    def test_blocked_bloom_filter_zero_false_negatives_union_and_fpr(self) -> None:
        bf_a = BlockedBloomFilter(num_blocks=32, block_bits=512, num_hashes=6)
        bf_b = BlockedBloomFilter(num_blocks=32, block_bits=512, num_hashes=6)
        keys_a = [f"https://example.invalid/doc/a-{i}" for i in range(400)]
        keys_b = [f"https://example.invalid/doc/b-{i}" for i in range(400)]
        for k in keys_a:
            bf_a.add(k)
        for k in keys_b:
            bf_b.add(k)
        combined = bf_a.union(bf_b)
        self.assertTrue(all(combined.contains(k) for k in keys_a + keys_b))

        negatives = [f"https://example.invalid/absent/{i}" for i in range(1000)]
        emp_fpr = combined.estimate_empirical_fpr(negatives)
        theo_fpr = combined.theoretical_fpr()
        self.assertLess(emp_fpr, 0.05)
        self.assertLess(abs(emp_fpr - theo_fpr), 0.03)

    def test_cuckoo_filter_insert_o1_delete_and_compact_serialization(self) -> None:
        items = [f"https://example.invalid/repo/org-{i:04d}/project-{i:04d}" for i in range(600)]
        gone = items[:100]
        live = items[100:]
        cf = CuckooFilter(capacity=len(items))
        for item in items:
            self.assertTrue(cf.insert(item))
        self.assertTrue(all(cf.contains(item) for item in items))

        for g in gone:
            self.assertTrue(cf.delete(g))
        self.assertTrue(all(cf.contains(item) for item in live))
        self.assertGreaterEqual(sum(1 for g in gone if not cf.contains(g)), 99)

        b64 = cf.to_base64()
        restored = CuckooFilter.from_base64(b64)
        self.assertEqual(restored.count, len(live))
        self.assertTrue(all(restored.contains(item) for item in live))

    def test_static_xor_fingerprint_filter_compact_bits_per_key_and_zero_fn(self) -> None:
        edges = [f"node:{i}->node:{i + 1}" for i in range(1200)]
        xf = StaticXorFingerprintFilter(edges)
        self.assertTrue(all(xf.contains(e) for e in edges))
        bpk = xf.bits_per_key()
        self.assertGreaterEqual(bpk, 9.0)
        self.assertLessEqual(bpk, 10.5)
        absent_hits = sum(1 for i in range(1000) if xf.contains(f"absent:{i}"))
        self.assertLess(absent_hits, 20)

    def test_multiprobe_simhash_lsh_recovers_pigeonhole_and_d24_recall(self) -> None:
        expander = MultiProbeSimHashLshExpander()
        sig_a = expander.compute_simhash128("deterministic cache line blocked bloom filter double hashing")
        sig_b = expander.compute_simhash128("deterministic cache line blocked bloom filter kirsch double hashing")
        self.assertLessEqual(expander.hamming_distance_hex(sig_a, sig_b), 28)

        exact_keys = expander.expand_probe_keys(sig_a, probe_radius_bits=0)
        one_bit_keys = expander.expand_probe_keys(sig_a, probe_radius_bits=1)
        two_bit_keys = expander.expand_probe_keys(sig_a, probe_radius_bits=2, two_bit_budget=40)
        self.assertEqual(len(exact_keys), 8)
        self.assertEqual(len(one_bit_keys), 136)
        self.assertEqual(len(two_bit_keys), 176)

        expander.index_signature("doc-a", sig_a)
        self.assertIn("doc-a", expander.query_candidates(sig_a, probe_radius_bits=0))

        bench = benchmark_simhash_recall(distances=[8, 16, 24], trials_per_distance=200, seed=42)
        self.assertFalse(bench["pigeonhole_1flip_per_band_exact_hit"])
        self.assertTrue(bench["pigeonhole_1flip_per_band_1bit_hit"])
        d24 = bench["recall_by_hamming_distance"]["24"]
        self.assertGreater(d24["multiprobe_1bit_recall"], d24["exact_0bit_recall"] + 0.45)

    def test_minhash_lsh_decontaminator_flags_near_duplicate_holdout(self) -> None:
        dec = MinHashLshDecontaminator()
        dec.index_holdout(
            "eval-01",
            "Construct a deterministic 3-wise peeling order xor fingerprint filter with zero false negatives",
        )
        res = dec.scan_candidates([
            {
                "id": "train-leak",
                "text": "Construct a deterministic 3-wise peeling order xor fingerprint filter with 0 false negatives",
            },
            {
                "id": "train-distinct",
                "text": "Clause balanced caption wrapping avoids trailing articles and single word orphans",
            },
        ])
        self.assertEqual(res["contaminated_count"], 1)
        self.assertEqual(res["contaminated"][0]["candidate_id"], "train-leak")
        self.assertEqual(res["clean_ids"], ["train-distinct"])

    def test_conservative_count_min_heavykeeper_and_hyperloglog(self) -> None:
        sk = ConservativeCountMinHeavyKeeperHll()
        sk.observe("elephant-alpha", 120)
        sk.observe("elephant-beta", 65)
        for i in range(200):
            sk.observe(f"mouse-{i}", 1)

        self.assertGreaterEqual(sk.estimate_frequency("elephant-alpha"), 120)
        self.assertLessEqual(sk.estimate_frequency("elephant-alpha"), 125)
        top = sk.top_k()
        self.assertEqual(top[0]["key"], "elephant-alpha")
        self.assertEqual(top[1]["key"], "elephant-beta")

        est_card = sk.estimate_cardinality()
        # True distinct = 202
        self.assertGreater(est_card, 165.0)
        self.assertLess(est_card, 240.0)

    def test_worked_example_recomputes_exact_receipt_and_cli_runs(self) -> None:
        src = json.loads((PACK_DIR / "source.json").read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.probabilistic-sketches-bundle"]
        expected = nouns["example.probabilistic-sketches-receipt"]["instance"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, expected)

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "probabilistic_sketches", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out, expected)


if __name__ == "__main__":
    unittest.main()
