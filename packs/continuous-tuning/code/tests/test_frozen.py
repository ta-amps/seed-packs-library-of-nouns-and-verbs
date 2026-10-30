"""Frozen test receipts and contamination counts."""

from __future__ import annotations

import copy
import hashlib
import unittest

from promotion_check import check_receipt, digest, jsonl, overlap_counts

ROWS = [{"id": "r1", "request": "Read feed a.", "label": {"tool": "read_feed"}},
        {"id": "r2", "request": "Rename bucket b.", "label": {"refusal": "no_matching_tool"}}]
RECEIPT = {"rows": 2, "registered_at": "2026-10-29T14:00:00Z", "jsonl_sha256": hashlib.sha256(jsonl(ROWS)).hexdigest(),
           "ids_sha256": digest(["r1", "r2"]),
           "contamination": {"exact": 0, "request": 0, "shape": 0, "held_out_family_rows": 0}}


class Receipts(unittest.TestCase):
    def test_canonical_lines(self) -> None:
        self.assertEqual(jsonl([{"b": 1, "a": "é"}]), '{"a":"é","b":1}\n'.encode())

    def test_a_pre_registered_receipt_passes(self) -> None:
        self.assertEqual(check_receipt(RECEIPT, ROWS, "2026-10-29T15:00:00Z"), [])
        self.assertEqual(check_receipt(RECEIPT, ROWS, "2026-10-29T10:30:00-04:00"), [])

    def test_each_problem_is_named(self) -> None:
        changed_rows = copy.deepcopy(ROWS)
        changed_rows[0]["request"] = "Read feed b."
        self.assertIn("jsonl_sha256 does not match the rows", check_receipt(RECEIPT, changed_rows, "2026-10-29T15:00:00Z"))
        self.assertIn("ids_sha256 does not match the ordered row ids", check_receipt(RECEIPT, ROWS[::-1], "2026-10-29T15:00:00Z"))
        late = check_receipt(RECEIPT, ROWS, "2026-10-29T13:59:00Z")
        self.assertIn("registered at or after the first scoring, so it is not pre-registered", late)
        self.assertTrue(check_receipt({**RECEIPT, "rows": 3}, ROWS, "2026-10-29T15:00:00Z"))
        dirty = {**RECEIPT, "contamination": {"exact": 0, "request": 0, "shape": 1, "held_out_family_rows": 0}}
        self.assertIn("contamination counts are not all zero", check_receipt(dirty, ROWS, "2026-10-29T15:00:00Z"))
        twice = [ROWS[0], ROWS[0]]
        self.assertIn("row ids repeat", check_receipt(RECEIPT, twice, "2026-10-29T15:00:00Z"))

    def test_times_need_a_zone(self) -> None:
        with self.assertRaises(ValueError):
            check_receipt(RECEIPT, ROWS, "2026-10-29T15:00:00")


class Contamination(unittest.TestCase):
    def test_overlaps_are_counted_per_kind(self) -> None:
        train = {"exact": ["e1", "e2"], "request": ["q1", "q2"], "shape": ["s1"]}
        held = {"exact": ["e9"], "request": ["q2"], "shape": ["s1", "s9"]}
        self.assertEqual(overlap_counts(train, held), {"exact": 0, "request": 1, "shape": 1})
        self.assertEqual(overlap_counts(train, {"exact": ["e8"]}), {"exact": 0, "request": 0, "shape": 0})


if __name__ == "__main__":
    unittest.main()
