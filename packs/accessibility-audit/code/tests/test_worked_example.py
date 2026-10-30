"""Recompute this pack's worked examples from source.json, and keep the pack's nouns equal to the code."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from a11y_checks import RULES, check_pair, lint, rule_ids

PACKS = Path(__file__).resolve().parents[3]
SOURCE = json.loads((PACKS / "accessibility-audit" / "source.json").read_text(encoding="utf-8"))
NOUNS = {noun["slug"]: noun["value"] for noun in SOURCE["nouns"]}


class WorkedExamples(unittest.TestCase):
    def test_contrast_example_matches_this_tool(self) -> None:
        value = NOUNS["example.contrast"]
        for pair in value["pairs"]:
            expected = value["expected"][pair["id"]]
            normal = check_pair(pair["foreground"], pair["background"], size_px=16)
            large = check_pair(pair["foreground"], pair["background"], size_px=24)
            self.assertEqual(normal["ratio"], expected["ratio"], pair["id"])
            self.assertEqual(normal["passes"], expected["normal_text"], pair["id"])
            self.assertEqual(large["passes"], expected["large_text"], pair["id"])

    def test_a_token_can_pass_in_one_theme_and_fail_in_the_other(self) -> None:
        expected = NOUNS["example.contrast"]["expected"]
        self.assertTrue(expected["muted-text-light"]["normal_text"])
        self.assertFalse(expected["muted-text-dark"]["normal_text"])

    def test_structure_example_recomputes(self) -> None:
        for page in NOUNS["example.structure-lint"]["pages"]:
            report = lint(page["html"])
            self.assertEqual(rule_ids(report), page["expected_rules"], page["id"])
            self.assertEqual(report["failures"], page["expected_failures"], page["id"])
            self.assertEqual(report["advisories"], page["expected_advisories"], page["id"])
        clean = next(p for p in NOUNS["example.structure-lint"]["pages"] if p["id"] == "clean")
        self.assertEqual(clean["expected_rules"], [])

    def test_structure_rules_noun_equals_the_linter(self) -> None:
        rows = {row["id"]: {k: row[k] for k in ("sc", "name", "level", "conformance")} for row in NOUNS["structure-rules"]["rules"]}
        self.assertEqual(rows, {rid: {k: spec[k] for k in ("sc", "name", "level", "conformance")} for rid, spec in RULES.items()})

    def test_quoted_ratios_in_findings_are_true(self) -> None:
        good = [f["finding"] for f in NOUNS["audit-checks"]["golden_fixtures"] if f["label"] == "known_good"]
        contrast = next(f for f in good if f["sc"] == "1.4.3")
        self.assertTrue(contrast["measured"].startswith(f"{check_pair('#6b7280', '#0f172a')['ratio']:.2f}:1"))
        self.assertIn(f"{check_pair('#9ca3af', '#0f172a')['ratio']:.2f}:1", contrast["suggested_fix"])
        report = NOUNS["example.audit-report"]["instance"]
        quoted = next(f for f in report["findings"] if f["sc"] == "1.4.3")
        self.assertEqual(quoted["measured"], contrast["measured"])

    def test_checklist_covers_the_criteria_the_rules_cite(self) -> None:
        listed = {row["sc"] for row in NOUNS["wcag-checklist"]["criteria"]}
        self.assertLessEqual({spec["sc"] for spec in RULES.values()}, listed)
        for sc in ("2.1.1", "2.4.7", "2.4.11", "1.4.3", "1.4.11", "1.1.1", "1.2.2", "1.2.5", "1.4.10", "2.5.8", "2.2.2", "3.1.1"):
            self.assertIn(sc, listed)
        self.assertNotIn("4.1.1", listed, "4.1.1 Parsing is obsolete in WCAG 2.2")


if __name__ == "__main__":
    unittest.main()
