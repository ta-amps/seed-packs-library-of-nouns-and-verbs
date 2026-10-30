"""Snapshot checks, measures, screens and roll candidates on a small synthetic chain."""

from __future__ import annotations

import copy
import unittest
from datetime import date, timedelta

from chain_measures import bsm, check_snapshot, measures, parse_time, roll_candidates, screen

SNAP = "2026-10-30T19:30:00Z"


def contract(expiry: str, strike: float, sigma: float, spread: float, oi: int = 500, volume: int = 50,
             quote_time: str = "2026-10-30T19:29:50Z", delta_shift: float = 0.0, one_sided: bool = False) -> dict:
    """A call quoted around its model price, so volatility from the mid lands near the provider's."""
    t = (parse_time(f"{expiry}T21:00:00Z") - parse_time(SNAP)).total_seconds() / (365 * 86400)
    g = bsm.greeks("call", 100.0, strike, t, 0.04, 0.0, sigma)
    bid, ask = round(g["price"] - spread / 2, 2), round(g["price"] + spread / 2, 2)
    if one_sided:
        bid = 0.0
    return {
        "symbol": f"TEST.X {expiry[2:4]}{expiry[5:7]}{expiry[8:10]}C{int(strike * 1000):08d}", "type": "call",
        "strike": strike, "expiry": expiry, "expires_at": f"{expiry}T21:00:00Z", "bid": bid, "ask": ask,
        "last": bid, "volume": volume, "open_interest": oi, "quote_time": quote_time, "provider_iv": sigma,
        "provider_greeks": {"delta": round(g["delta"] + delta_shift, 4), "gamma": round(g["gamma"], 4),
                            "theta_per_day": round(g["theta_per_day"], 4), "vega_per_point": round(g["vega_per_point"], 4)},
    }


def fixture() -> tuple[dict, dict, dict]:
    request = {
        "underlying": {"name": "Test (synthetic)", "symbol": "TEST.X"},
        "reference_contract": "TEST.X 261120C00100000",
        "expiries": ["2026-11-20", "2026-12-18"],
        "strike_window": {"min": 95.0, "max": 105.0},
        "screens": {"min_open_interest": 100, "min_volume": 10, "max_spread_pct_of_mid": 10.0, "max_quote_age_seconds": 120},
        "tolerances": {"delta": 0.02, "gamma": 0.005, "theta_per_day": 0.005, "vega_per_point": 0.01, "iv": 0.01},
        "assumptions": {"rate": {"value": 0.04, "source": "synthetic", "as_of": "2026-10-29"},
                        "dividend_yield": {"value": 0.0, "source": "synthetic", "as_of": "2026-10-29"}},
        "iv_history": {"measure": "30-day at-the-money implied volatility", "lookback_observations": 5, "min_observations": 5},
    }
    snapshot = {
        "source": {"provider": "synthetic", "product": "synthetic", "access": "requester_export_file",
                   "terms_read_on": "2026-10-30", "automated_access_permitted": False, "storage_permitted": True,
                   "redistribution_permitted": False, "viewers": "requester_only", "delay_minutes": 15,
                   "brokerage_connection": False},
        "snapshot_at": SNAP,
        "retrieved_at": "2026-10-30T19:31:00Z",
        "underlying": {"symbol": "TEST.X", "price": 100.0, "price_field": "last", "quote_time": "2026-10-30T19:29:58Z"},
        "contracts": [
            contract("2026-11-20", 100.0, 0.30, 0.10),
            contract("2026-12-18", 100.0, 0.29, 0.15),
            contract("2026-11-20", 105.0, 0.28, 0.15, delta_shift=0.05),
            contract("2026-12-18", 95.0, 0.31, 0.40, oi=40, volume=0, quote_time="2026-10-30T19:20:00Z", one_sided=True),
        ],
    }
    days = [date(2026, 10, 26) + timedelta(days=i) for i in range(5)]
    history = {"symbol": "TEST.X", "measure": "30-day at-the-money implied volatility", "provider": "synthetic",
               "observations": [{"date": d.isoformat(), "iv": v} for d, v in zip(days, (0.25, 0.31, 0.28, 0.27, 0.30))]}
    return request, snapshot, history


class Snapshot(unittest.TestCase):
    def test_a_clean_snapshot_has_no_problems(self) -> None:
        self.assertEqual(check_snapshot(*fixture()), [])

    def test_each_stopping_problem_is_named(self) -> None:
        cases = {
            "brokerage": lambda r, s, h: s["source"].update(brokerage_connection=True),
            "storing": lambda r, s, h: s["source"].update(storage_permitted=False),
            "terms": lambda r, s, h: s["source"].update(terms_read_on=""),
            "automated": lambda r, s, h: s["source"].update(access="licensed_api"),
            "requested symbol": lambda r, s, h: s["underlying"].update(symbol="OTHER.X"),
            "older than": lambda r, s, h: s["underlying"].update(quote_time="2026-10-30T19:00:00Z"),
            "expiry not requested": lambda r, s, h: s["contracts"][0].update(expiry="2027-01-15"),
            "strike outside": lambda r, s, h: s["contracts"][0].update(strike=120.0),
            "after the snapshot": lambda r, s, h: s["contracts"][0].update(quote_time="2026-10-30T19:45:00Z"),
            "missing or malformed": lambda r, s, h: s["contracts"][0].pop("quote_time"),
            "listed twice": lambda r, s, h: s["contracts"].append(copy.deepcopy(s["contracts"][0])),
            "whole number": lambda r, s, h: s["contracts"][0].update(volume=1.5),
            "symbol and measure": lambda r, s, h: h.update(measure="10-day realized volatility"),
            "strictly increasing": lambda r, s, h: h["observations"].reverse(),
        }
        for words, change in cases.items():
            request, snapshot, history = fixture()
            change(request, snapshot, history)
            problems = check_snapshot(request, snapshot, history)
            with self.subTest(problem=words):
                self.assertTrue(any(words in p for p in problems), problems)

    def test_measures_refuse_a_snapshot_with_problems(self) -> None:
        request, snapshot, history = fixture()
        snapshot["source"]["brokerage_connection"] = True
        with self.assertRaises(ValueError):
            measures(request, snapshot, history)


class Measures(unittest.TestCase):
    def setUp(self) -> None:
        self.request, self.snapshot, self.history = fixture()
        self.measured = measures(self.request, self.snapshot, self.history)
        self.rows = {row["symbol"]: row for row in self.measured["contracts"]}

    def test_mid_spread_and_ages(self) -> None:
        row = self.rows["TEST.X 261120C00100000"]
        self.assertEqual((row["mid"], row["spread"], row["spread_pct_of_mid"]), (2.99, 0.1, 3.34))
        self.assertEqual((row["quote_age_seconds"], row["days_to_expiry"]), (10, 21))
        self.assertEqual(self.measured["underlying_quote_age_seconds"], 2)

    def test_recomputed_greeks_match_the_provider_and_flag_a_difference(self) -> None:
        self.assertEqual(self.rows["TEST.X 261120C00100000"]["flags"], [])
        shifted = self.rows["TEST.X 261120C00105000"]
        self.assertEqual(shifted["flags"], ["delta_differs"])
        self.assertEqual(shifted["greek_differences"]["delta"], 0.05)
        self.assertEqual(self.measured["flag_counts"], {"delta_differs": 1})

    def test_volatility_from_the_mid_is_close_to_the_provider_value(self) -> None:
        row = self.rows["TEST.X 261218C00100000"]
        self.assertIsNone(row["iv_from_mid_reason"])
        self.assertLess(abs(row["iv_difference"]), 0.01)

    def test_a_one_sided_quote_has_no_mid_and_no_volatility(self) -> None:
        row = self.rows["TEST.X 261218C00095000"]
        self.assertEqual((row["two_sided"], row["mid"], row["spread_pct_of_mid"]), (False, None, None))
        self.assertEqual((row["iv_from_mid"], row["iv_from_mid_reason"]), (None, "no_two_sided_quote"))

    def test_the_rank_uses_the_named_history(self) -> None:
        rank = self.measured["iv_rank"]
        self.assertEqual(rank["measure"], "30-day at-the-money implied volatility")
        self.assertEqual((rank["rank"], rank["percentile"]), (83.3, 75.0))

    def test_no_negative_zeros(self) -> None:
        for row in self.measured["contracts"]:
            for value in (row["greek_differences"] or {}).values():
                self.assertFalse(value == 0 and str(value).startswith("-"), row["symbol"])


class ScreensAndCandidates(unittest.TestCase):
    def setUp(self) -> None:
        self.request, snapshot, history = fixture()
        self.measured = measures(self.request, snapshot, history)
        self.screened = screen(self.request, self.measured)

    def test_every_contract_is_listed_with_its_failures(self) -> None:
        results = {item["symbol"]: item["failed"] for item in self.screened["results"]}
        self.assertEqual(len(results), 4)
        self.assertEqual(results["TEST.X 261120C00100000"], [])
        self.assertEqual(results["TEST.X 261120C00105000"], ["spread"])
        self.assertEqual(results["TEST.X 261218C00095000"], ["two_sided", "spread", "open_interest", "volume", "quote_age"])
        self.assertEqual((self.screened["passed"], self.screened["failed"]), (2, 2))

    def test_candidates_are_grouped_ordered_and_compared(self) -> None:
        found = roll_candidates(self.request, self.measured, self.screened)
        self.assertEqual(found["order"], "expiry, then strike")
        self.assertEqual([c["symbol"] for c in found["same_strike_later_expiry"]], ["TEST.X 261218C00100000"])
        self.assertEqual([c["symbol"] for c in found["different_strike"]], ["TEST.X 261120C00105000", "TEST.X 261218C00095000"])
        later = found["same_strike_later_expiry"][0]
        self.assertEqual(later["mid_difference"], round(later["mid"] - found["reference"]["mid"], 4))
        one_sided = found["different_strike"][1]
        self.assertEqual((one_sided["mid_difference"], one_sided["screen_passed"]), (None, False))
        for group in ("same_strike_later_expiry", "different_strike"):
            for item in found[group]:
                self.assertFalse({"rank", "score", "best"} & set(item))

    def test_an_unknown_reference_is_refused(self) -> None:
        self.request["reference_contract"] = "TEST.X 261120C00110000"
        with self.assertRaises(ValueError):
            roll_candidates(self.request, self.measured, self.screened)


if __name__ == "__main__":
    unittest.main()
