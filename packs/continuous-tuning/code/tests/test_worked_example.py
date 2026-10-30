"""Recompute this pack's worked example from source.json: the receipt, both decisions and the rule's digest."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from promotion_check import check_receipt, decide, digest

PACK = Path(__file__).resolve().parents[2]
NOUNS = {n["slug"]: n["value"] for n in json.loads((PACK / "source.json").read_text(encoding="utf-8"))["nouns"]}
RULE_NOUN = NOUNS["rule.tool-call-specialist-v1"]
RULE = RULE_NOUN["instance"]
EVALS = NOUNS["example.evaluations"]


class WorkedExample(unittest.TestCase):
    def test_the_rule_digest_is_the_published_one(self) -> None:
        self.assertEqual(digest(RULE), "bf0fa821717c2400faab77652f067ea85f2616eea329c6e139af33a423e4b3b7")
        self.assertEqual(RULE_NOUN["rule_sha256"], digest(RULE))
        self.assertEqual(RULE_NOUN["source"]["commit"], "2e7d6ab4d7e084a413ba0c3c83cebc10d81c9a98")

    def test_a_copy_with_integer_zeros_digests_differently(self) -> None:
        text = json.dumps(RULE).replace("0.0,", "0,").replace("0.0}", "0}")
        self.assertNotEqual(digest(json.loads(text)), digest(RULE))

    def test_the_receipt_is_real_and_registered_before_the_first_scoring(self) -> None:
        receipt = NOUNS["example.frozen-test-receipt"]
        rows = NOUNS["example.frozen-test-rows"]["rows"]
        self.assertEqual(check_receipt(receipt["instance"], rows, receipt["first_scored_at"]), [])
        self.assertEqual(sum(1 for row in rows if "refusal" in row["label"]), receipt["instance"]["refusals"])

    def test_both_decisions_are_recomputed_exactly(self) -> None:
        for round_name, slug in (("round_1", "example.decision-round-1"), ("round_2", "example.decision-round-2")):
            inputs = EVALS[round_name]
            with self.subTest(round=round_name):
                got = decide(RULE, inputs["candidate"], inputs["champion"], inputs["base"], inputs["integrity"])
                self.assertEqual(json.loads(json.dumps(got)), NOUNS[slug]["instance"])
        self.assertEqual(NOUNS["example.decision-round-1"]["instance"]["outcome"], "promote_candidate")
        self.assertEqual(NOUNS["example.decision-round-2"]["instance"]["outcome"], "keep_champion")

    def test_aggregates_agree_with_the_rows(self) -> None:
        for round_name in ("round_1", "round_2"):
            for model in ("candidate", "champion", "base"):
                test = EVALS[round_name][model]["test"]
                with self.subTest(round=round_name, model=model):
                    self.assertEqual(len(test["exact"]), 40)
                    self.assertEqual(test["aggregate"]["exact_match_strict"], round(sum(test["exact"]) / 40, 6))
        self.assertEqual(EVALS["round_2"]["champion"]["test"], EVALS["round_1"]["candidate"]["test"],
                         "round 1's promoted candidate is round 2's champion")

    def test_the_tool_card_names_this_code(self) -> None:
        card = NOUNS["tool.promotion-check"]
        self.assertEqual(card["code"], {"$code": "continuous-tuning"})
        for command in card["commands"]:
            self.assertTrue(re.match(r"python -m promotion_check (decide|bootstrap|receipt|digest) ", command))


if __name__ == "__main__":
    unittest.main()
