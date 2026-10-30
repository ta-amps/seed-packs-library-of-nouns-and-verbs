"""The report's verdict follows from its rows: a failure fails, a missing or unrun check is incomplete."""

from __future__ import annotations

import unittest

from video_qa_checks.report import NOT_APPROVAL, REQUIRED, compile_report, verdict

PLAN = {"duration_s": 12.0, "fps": 30, "holds": [[9.0, 10.5, "end card"]]}
MEDIA = {"file": "example.mp4", "bytes": 1, "sha256": "0" * 64}


def rows(**results: str) -> list[dict]:
    return [{"check": name, "result": results.get(name, "pass"), "findings": []} for name in REQUIRED]


class Verdict(unittest.TestCase):
    def test_order_of_outcomes(self) -> None:
        self.assertEqual(verdict(rows()), "pass")
        self.assertEqual(verdict(rows(cut_cadence="warn")), "pass_with_warnings")
        self.assertEqual(verdict(rows(legibility="not_run")), "incomplete")
        self.assertEqual(verdict(rows(legibility="not_run", clipping="fail")), "fail")
        self.assertEqual(verdict(rows()[:-1]), "incomplete")

    def test_the_report_counts_and_names_what_is_missing(self) -> None:
        report = compile_report(MEDIA, PLAN, rows(loudness="warn")[:-1])
        self.assertEqual(report["counts"], {"pass": 7, "warn": 1, "fail": 0, "not_run": 0})
        self.assertEqual(report["missing_checks"], ["legibility"])
        self.assertEqual(report["verdict"], "incomplete")
        self.assertEqual(report["plan"], {"duration_s": 12.0, "fps": 30, "holds": 1, "pauses": 0, "black": 0})
        self.assertEqual(report["not_approval"], NOT_APPROVAL)

    def test_a_check_reported_twice_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            compile_report(MEDIA, PLAN, rows() + rows()[:1])


if __name__ == "__main__":
    unittest.main()
