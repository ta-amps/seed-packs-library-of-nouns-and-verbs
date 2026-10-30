"""The pre-registered rule: promotion, each guard, integrity, optional splits and refusals."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from promotion_check import check_rule, decide

PACK = Path(__file__).resolve().parents[2]
NOUNS = {n["slug"]: n["value"] for n in json.loads((PACK / "source.json").read_text(encoding="utf-8"))["nouns"]}
RULE = NOUNS["rule.tool-call-specialist-v1"]["instance"]
ROUND_2 = NOUNS["example.evaluations"]["round_2"]
INTEGRITY = {"no_contamination": True, "frozen_base_unchanged": True, "adapter_reload_equivalent": True,
             "holdout_digests_match": True}


def run(candidate: dict, champion: dict, base: dict, integrity: dict = INTEGRITY) -> dict:
    return decide(RULE, candidate, champion, base, integrity)


def failed(decision: dict) -> list[str]:
    return [c["check"] for c in decision["checks"] if c["passed"] is False]


class Rule(unittest.TestCase):
    def test_the_real_rule_is_usable(self) -> None:
        self.assertEqual(check_rule(RULE), [])

    def test_unusable_rules_are_named(self) -> None:
        cases = {
            "unsupported": lambda r: r.update(version=2),
            "promotion.effects is missing": lambda r: r["promotion"].pop("effects"),
            "resamples": lambda r: r["promotion"]["paired_bootstrap"].update(resamples=10),
            "confidence": lambda r: r["promotion"]["paired_bootstrap"].update(confidence=1.5),
            "fixed string": lambda r: r["promotion"]["paired_bootstrap"].update(seed=""),
            "known split": lambda r: r["promotion"]["no_regression"][0].update(split="holdout"),
        }
        for words, mutate in cases.items():
            rule = copy.deepcopy(RULE)
            mutate(rule)
            with self.subTest(words=words):
                self.assertTrue(any(words in p for p in check_rule(rule)), check_rule(rule))
                with self.assertRaises(ValueError):
                    decide(rule, ROUND_2["candidate"], ROUND_2["champion"], ROUND_2["base"], INTEGRITY)


class Decisions(unittest.TestCase):
    def test_a_guard_keeps_the_champion_against_a_real_looking_gain(self) -> None:
        decision = run(ROUND_2["candidate"], ROUND_2["champion"], ROUND_2["base"])
        self.assertEqual(decision["outcome"], "keep_champion")
        self.assertGreater(decision["paired_test"]["lower"], 0)
        self.assertEqual(failed(decision), ["test schema validity does not drop more than 0.02"])

    def test_without_the_guard_failure_it_promotes(self) -> None:
        candidate = copy.deepcopy(ROUND_2["candidate"])
        candidate["test"]["aggregate"]["schema_valid_rate"] = 0.8
        decision = run(candidate, ROUND_2["champion"], ROUND_2["base"])
        self.assertEqual(decision["outcome"], "promote_candidate")
        self.assertEqual(failed(decision), [])
        self.assertIn("private", decision["effects"])

    def test_an_integrity_failure_keeps_the_champion(self) -> None:
        candidate = copy.deepcopy(ROUND_2["candidate"])
        candidate["test"]["aggregate"]["schema_valid_rate"] = 0.8
        decision = run(candidate, ROUND_2["champion"], ROUND_2["base"], {**INTEGRITY, "adapter_reload_equivalent": False})
        self.assertEqual(decision["outcome"], "keep_champion")
        self.assertEqual(failed(decision), ["integrity: adapter_reload_equivalent"])

    def test_an_optional_split_may_be_missing_but_a_required_one_may_not(self) -> None:
        candidate = copy.deepcopy(ROUND_2["candidate"])
        candidate["test"]["aggregate"]["schema_valid_rate"] = 0.8
        candidate.pop("fresh")
        decision = run(candidate, ROUND_2["champion"], ROUND_2["base"])
        fresh = next(c for c in decision["checks"] if "fresh holdout" in c["check"])
        self.assertIsNone(fresh["passed"])
        self.assertEqual(decision["outcome"], "promote_candidate")
        candidate.pop("sanity")
        decision = run(candidate, ROUND_2["champion"], ROUND_2["base"])
        self.assertEqual(decision["outcome"], "keep_champion")
        self.assertIn("sanity accuracy does not drop more than 0.05 against the champion", failed(decision))

    def test_too_small_a_gain_fails_the_minimum(self) -> None:
        candidate = copy.deepcopy(ROUND_2["champion"])
        decision = run(candidate, ROUND_2["champion"], ROUND_2["base"])
        self.assertEqual(decision["paired_test"]["delta"], 0)
        self.assertIn("test exact_match_strict improves by at least 0.03", failed(decision))
        self.assertIn("paired bootstrap lower bound above zero", failed(decision))

    def test_rows_must_be_the_same_frozen_rows(self) -> None:
        candidate = copy.deepcopy(ROUND_2["candidate"])
        candidate["test"]["ids_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            run(candidate, ROUND_2["champion"], ROUND_2["base"])
        candidate["test"].pop("ids_sha256")
        champion = copy.deepcopy(ROUND_2["champion"])
        champion["test"].pop("ids_sha256")
        with self.assertRaises(ValueError):
            run(candidate, champion, ROUND_2["base"])


if __name__ == "__main__":
    unittest.main()
