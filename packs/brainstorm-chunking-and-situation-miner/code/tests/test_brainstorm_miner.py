"""Unit tests for brainstorm_miner."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from brainstorm_miner import (
    chunk_canonical_blocks,
    collapse_duplicate_blocks,
    mine_brainstorm_text,
    shingle_jaccard,
    split_repeated_pastes,
)

SAMPLE_RUBRIC_BLOCK = """Scoring Methodology
Calibrated to the official evaluation rubric weights (0-10 scale)
Impact
30% (3.0 pts)
Evaluates problem specificity, target user clarity, domain alignment, and whether the repository was built within the active window.

Open AI Tooling
25% (2.5 pts)
Measures verified usage of open models and SDKs, multimodal pipelines (SAM, audio/speech), or custom fine-tuned open weights.

Technical Depth
20% (2.0 pts)
Checks commit cadence, modular source tree structure, automated test suites, CI workflows, and Dockerfiles.

Demo Completeness
25% (2.5 pts)
Verifies public web deployment links and recorded video walkthroughs referenced in repository documentation."""


class BrainstormMinerTests(unittest.TestCase):
    def test_14x_inline_concatenated_paste_collapses_to_one(self) -> None:
        # Simulate pasting 14 times with space-only join (no blank line between pastes)
        inline_14x = " ".join([SAMPLE_RUBRIC_BLOCK] * 14) + "\n"
        blocks = split_repeated_pastes(inline_14x)
        self.assertEqual(len(blocks), 14)
        dedup = collapse_duplicate_blocks(blocks)
        self.assertEqual(dedup["raw_block_count"], 14)
        self.assertEqual(dedup["unique_block_count"], 1)
        self.assertEqual(dedup["compression_ratio"], "14:1")
        self.assertEqual(dedup["canonical_blocks"][0]["occurrences"], 14)

    def test_interleaved_two_document_pastes_collapse_to_two(self) -> None:
        doc_b = (
            "Agent Security Checklist\n"
            "Before opening an untrusted repository, scan rule files and MCP configs for invisible "
            "Unicode tag characters, shell hooks, built-in name shadowing, and authority spoofing."
        )
        combined = " ".join([SAMPLE_RUBRIC_BLOCK] * 4 + [doc_b] * 5)
        blocks = split_repeated_pastes(combined)
        self.assertEqual(len(blocks), 9)
        dedup = collapse_duplicate_blocks(blocks)
        self.assertEqual(dedup["unique_block_count"], 2)
        counts = sorted(b["occurrences"] for b in dedup["canonical_blocks"])
        self.assertEqual(counts, [4, 5])

    def test_shingle_near_duplicate_collapse(self) -> None:
        variant = SAMPLE_RUBRIC_BLOCK.replace("walkthroughs referenced", "walkthrough links cited")
        sim = shingle_jaccard(SAMPLE_RUBRIC_BLOCK, variant)
        self.assertGreater(sim, 0.85)
        dedup = collapse_duplicate_blocks([SAMPLE_RUBRIC_BLOCK, variant], near_dup_threshold=0.80)
        self.assertEqual(dedup["unique_block_count"], 1)
        self.assertEqual(dedup["canonical_blocks"][0]["near_duplicate_matches"], 1)

    def test_chunking_extracts_preamble_and_four_weighted_pillars(self) -> None:
        dedup = collapse_duplicate_blocks([SAMPLE_RUBRIC_BLOCK])
        chunks = chunk_canonical_blocks(dedup["canonical_blocks"])
        self.assertEqual(len(chunks), 5)
        weighted = [c for c in chunks if "weight_pct" in c]
        self.assertEqual(len(weighted), 4)
        self.assertAlmostEqual(sum(c["weight_pct"] for c in weighted), 100.0)
        self.assertTrue(all(len(c["text_sha256"]) == 64 for c in chunks))

    def test_situation_extraction_and_gap_ranking(self) -> None:
        report = mine_brainstorm_text(" ".join([SAMPLE_RUBRIC_BLOCK] * 3))
        self.assertEqual(report["deduplication"]["compression_ratio"], "3:1")
        self.assertGreaterEqual(len(report["situations"]), 4)
        gaps = report["ranked_category_gaps"]
        self.assertEqual(gaps[0]["category_id"], "cat.submission-rubric-and-repo-readiness")
        self.assertGreater(gaps[0]["gap_score"], 0.0)

    def test_trailing_unique_epilogue_preserved(self) -> None:
        epilogue = (
            "Unique Followup Situation\n"
            "Operators also need segmentation mask alignment with speech word timestamps in video demos."
        )
        raw = f"{SAMPLE_RUBRIC_BLOCK} {SAMPLE_RUBRIC_BLOCK}\n\n{epilogue}"
        blocks = split_repeated_pastes(raw)
        dedup = collapse_duplicate_blocks(blocks)
        self.assertEqual(dedup["unique_block_count"], 2)

    def test_cli_determinism(self) -> None:
        code_dir = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "raw.txt"
            inp.write_text(" ".join([SAMPLE_RUBRIC_BLOCK] * 5), encoding="utf-8")
            r1 = subprocess.run(
                [sys.executable, "-m", "brainstorm_miner", "mine", str(inp)],
                cwd=code_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            r2 = subprocess.run(
                [sys.executable, "-m", "brainstorm_miner", "mine", str(inp)],
                cwd=code_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(r1.stdout, r2.stdout)
            parsed = json.loads(r1.stdout)
            self.assertEqual(parsed["deduplication"]["compression_ratio"], "5:1")


if __name__ == "__main__":
    unittest.main()
