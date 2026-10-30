"""Draws and bootstraps match values recorded from Tessera's examples/continuous_tuning at commit 2e7d6ab.

The expected numbers below were produced on 2026-10-30 by running Tessera's own Draw and paired_bootstrap
(examples/continuous_tuning/task.py and promotion.py at 2e7d6ab4d7e084a413ba0c3c83cebc10d81c9a98) on the
same inputs. They pin this port to that implementation.
"""

from __future__ import annotations

import unittest

from promotion_check import Draw, canonical, digest, paired_bootstrap

SEED = "tool-call-specialist.promotion.v1"


class Draws(unittest.TestCase):
    def test_draws_match_tesseras(self) -> None:
        draw = Draw("paired-bootstrap", SEED, 150)
        self.assertEqual([draw.below(150) for _ in range(8)], [143, 35, 1, 115, 45, 39, 103, 92])
        draw = Draw("paired-bootstrap", SEED, 40)
        self.assertEqual([draw.below(40) for _ in range(8)], [25, 30, 37, 21, 34, 9, 11, 4])

    def test_canonical_json(self) -> None:
        self.assertEqual(canonical({"b": 1, "a": [0.0, "é"]}), '{"a":[0.0,"é"],"b":1}'.encode())
        self.assertNotEqual(digest({"x": 0.0}), digest({"x": 0}))


class Bootstraps(unittest.TestCase):
    def test_bootstraps_match_tesseras(self) -> None:
        cand = [i % 3 != 0 for i in range(150)]
        champ = [i % 5 == 0 or i % 7 == 0 for i in range(150)]
        self.assertEqual(paired_bootstrap(cand, champ, 2000, SEED, 0.95),
                         {"delta": 0.353333, "lower": 0.246667, "upper": 0.46, "improved_rows": 69, "regressed_rows": 16})
        cand = [i % 4 != 1 for i in range(40)]
        champ = [i % 4 in (0, 2) or i == 1 for i in range(40)]
        self.assertEqual(paired_bootstrap(cand, champ, 2000, SEED, 0.95),
                         {"delta": 0.225, "lower": 0.075, "upper": 0.375, "improved_rows": 10, "regressed_rows": 1})
        self.assertEqual(paired_bootstrap(cand, champ, 1000, "another-seed", 0.9),
                         {"delta": 0.225, "lower": 0.1, "upper": 0.35, "improved_rows": 10, "regressed_rows": 1})

    def test_integers_and_booleans_are_the_same_rows(self) -> None:
        cand = [i % 4 != 1 for i in range(40)]
        champ = [i % 4 in (0, 2) or i == 1 for i in range(40)]
        self.assertEqual(paired_bootstrap([int(x) for x in cand], [int(x) for x in champ], 500, SEED, 0.95),
                         paired_bootstrap(cand, champ, 500, SEED, 0.95))

    def test_unpaired_rows_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            paired_bootstrap([1, 0], [1], 100, SEED, 0.95)
        with self.assertRaises(ValueError):
            paired_bootstrap([], [], 100, SEED, 0.95)


if __name__ == "__main__":
    unittest.main()
