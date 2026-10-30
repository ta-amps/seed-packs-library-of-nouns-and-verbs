"""Implied volatility rank and percentile under this pack's one stated definition."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from chain_measures import history_problems, iv_rank


def series(values: list[float], start: date = date(2026, 1, 1)) -> list[dict]:
    return [{"date": (start + timedelta(days=i)).isoformat(), "iv": v} for i, v in enumerate(values)]


class Rank(unittest.TestCase):
    def test_rank_and_percentile(self) -> None:
        result = iv_rank(series([0.20, 0.30, 0.25, 0.40, 0.35]), lookback=5, min_observations=3)
        self.assertEqual(result["rank"], 75.0)          # (0.35 - 0.20) / (0.40 - 0.20)
        self.assertEqual(result["percentile"], 75.0)    # 3 of the 4 earlier values are below 0.35
        self.assertEqual((result["low"], result["high"]), (0.20, 0.40))
        self.assertEqual((result["low_date"], result["high_date"]), ("2026-01-01", "2026-01-04"))
        self.assertEqual((result["current"], result["current_date"]), (0.35, "2026-01-05"))
        self.assertIsNone(result["reason"])

    def test_only_the_lookback_counts(self) -> None:
        result = iv_rank(series([0.90, 0.20, 0.30, 0.25]), lookback=3, min_observations=3)
        self.assertEqual((result["low"], result["high"], result["observations"]), (0.20, 0.30, 3))
        self.assertEqual(result["rank"], 50.0)
        self.assertEqual(result["first_date"], "2026-01-02")

    def test_the_current_value_at_the_extremes(self) -> None:
        self.assertEqual(iv_rank(series([0.30, 0.25, 0.20]), 3, 3)["rank"], 0.0)
        top = iv_rank(series([0.20, 0.25, 0.30]), 3, 3)
        self.assertEqual((top["rank"], top["percentile"]), (100.0, 100.0))

    def test_ties_are_not_counted_below(self) -> None:
        self.assertEqual(iv_rank(series([0.30, 0.30, 0.20, 0.30]), 4, 4)["percentile"], 33.3)

    def test_unknown_with_a_reason(self) -> None:
        short = iv_rank(series([0.2, 0.3]), lookback=252, min_observations=200)
        self.assertEqual((short["rank"], short["percentile"], short["reason"]), (None, None, "too_few_observations"))
        flat = iv_rank(series([0.3, 0.3, 0.3]), 3, 3)
        self.assertEqual((flat["rank"], flat["reason"]), (None, "flat_history"))

    def test_bad_histories_and_settings_are_refused(self) -> None:
        self.assertTrue(history_problems([{"date": "2026-01-02", "iv": 0.3}, {"date": "2026-01-02", "iv": 0.3}]))
        self.assertTrue(history_problems([{"date": "2026-13-01", "iv": 0.3}]))
        self.assertTrue(history_problems([{"date": "2026-01-01", "iv": -0.1}]))
        self.assertTrue(history_problems([{"date": "2026-01-01", "iv": "0.3"}]))
        with self.assertRaises(ValueError):
            iv_rank([{"date": "2026-01-02", "iv": 0.3}, {"date": "2026-01-01", "iv": 0.3}], 2, 2)
        with self.assertRaises(ValueError):
            iv_rank(series([0.2, 0.3]), lookback=2, min_observations=3)


if __name__ == "__main__":
    unittest.main()
