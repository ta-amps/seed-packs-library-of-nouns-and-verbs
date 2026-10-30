"""Release evidence: manifest rows, file verification and the receipts ledger."""

from __future__ import annotations

import copy
import hashlib
import unittest

from explainer_checks.release import check_ledger, file_entry, missing_receipts, verify_manifest

FILES = {"explainer-20s.vtt": b"WEBVTT\n\n", "explainer-20s.srt": b"1\n"}


def read(path: str) -> bytes:
    if path not in FILES:
        raise FileNotFoundError(path)
    return FILES[path]


MANIFEST = {"files": [file_entry(path, data, "webvtt" if path.endswith(".vtt") else "srt", "text/plain")
                      for path, data in FILES.items()], "released": False}
RECEIPT = "a" * 64
LEDGER = {
    "steps": [
        {"step": "plan-cut", "ready_outcome": "cut_planned", "outcome": "cut_planned", "receipt": RECEIPT},
        {"step": "time-captions", "ready_outcome": "captions_timed", "outcome": "captions_timed", "receipt": "b" * 64},
    ],
    "every_step_has_receipt": True,
}


class Manifest(unittest.TestCase):
    def test_rows_carry_size_and_digest(self) -> None:
        row = file_entry("a.vtt", b"WEBVTT\n", "webvtt", "text/vtt")
        self.assertEqual(row, {"path": "a.vtt", "role": "webvtt", "media_type": "text/vtt", "bytes": 7,
                               "sha256": hashlib.sha256(b"WEBVTT\n").hexdigest()})

    def test_matching_files_pass(self) -> None:
        self.assertEqual(verify_manifest(MANIFEST, read), [])

    def test_changed_missing_duplicate_and_released_are_named(self) -> None:
        changed = copy.deepcopy(MANIFEST)
        changed["files"][0]["sha256"] = "0" * 64
        changed["files"][1]["bytes"] = 99
        changed["files"].append({"path": "gone.mp4", "role": "master", "media_type": "video/mp4", "bytes": 1,
                                 "sha256": "1" * 64})
        changed["files"].append(dict(changed["files"][1]))
        changed["released"] = True
        problems = verify_manifest(changed, read)
        for words in ("SHA-256 differs", "99", "cannot be read", "listed twice", "released false"):
            with self.subTest(words=words):
                self.assertTrue(any(words in p for p in problems), problems)


class Ledger(unittest.TestCase):
    def test_a_complete_ledger_passes(self) -> None:
        self.assertEqual(check_ledger(LEDGER), [])
        self.assertEqual(missing_receipts(LEDGER, ["plan-cut"]), [])

    def test_missing_receipts_wrong_outcomes_and_a_wrong_flag_are_named(self) -> None:
        ledger = copy.deepcopy(LEDGER)
        ledger["steps"][1].update(receipt=None, outcome="blocked")
        problems = check_ledger(ledger)
        self.assertIn("time-captions: no receipt with its ready outcome", problems)
        self.assertIn("every_step_has_receipt disagrees with the steps", problems)
        ledger["every_step_has_receipt"] = False
        self.assertEqual(check_ledger(ledger), ["time-captions: no receipt with its ready outcome"])
        self.assertEqual(missing_receipts(ledger, ["plan-cut", "time-captions", "render"]), ["time-captions", "render"])

    def test_a_malformed_receipt_and_a_repeated_step_are_named(self) -> None:
        ledger = copy.deepcopy(LEDGER)
        ledger["steps"][0]["receipt"] = "not-a-receipt"
        ledger["steps"].append(copy.deepcopy(LEDGER["steps"][1]))
        ledger["every_step_has_receipt"] = False
        problems = check_ledger(ledger)
        self.assertIn("plan-cut: no receipt with its ready outcome", problems)
        self.assertIn("time-captions: step listed twice", problems)


if __name__ == "__main__":
    unittest.main()
