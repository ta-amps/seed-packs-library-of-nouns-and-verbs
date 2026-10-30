"""The model's prices, greeks and implied volatility, checked against parity, finite differences and bounds."""

from __future__ import annotations

import itertools
import math
import unittest

from chain_measures import bsm

GRID = list(itertools.product(
    ("call", "put"),
    (35.0, 48.62, 62.0),          # underlying price
    (45.0, 50.0),                 # strike
    (7 / 365, 0.25, 1.5),         # years to expiry
    (0.0, 0.0393),                # rate
    (0.0, 0.012),                 # dividend yield
    (0.12, 0.34, 0.9),            # volatility
))


def simpson_cdf(x: float, steps: int = 20000) -> float:
    """The normal distribution function by numerical integration of the density, independent of erfc."""
    low = -12.0
    width = (x - low) / steps
    total = bsm.norm_pdf(low) + bsm.norm_pdf(x)
    for i in range(1, steps):
        total += (4 if i % 2 else 2) * bsm.norm_pdf(low + i * width)
    return total * width / 3


class Prices(unittest.TestCase):
    def test_normal_distribution_matches_numerical_integration(self) -> None:
        for x in (-3.1, -1.0, -0.2, 0.0, 0.4, 1.7, 2.9):
            self.assertAlmostEqual(bsm.norm_cdf(x), simpson_cdf(x), places=10)
        self.assertEqual(bsm.norm_cdf(0.0), 0.5)

    def test_put_call_parity(self) -> None:
        for _, s, k, t, r, q, sigma in GRID:
            call, put = bsm.price("call", s, k, t, r, q, sigma), bsm.price("put", s, k, t, r, q, sigma)
            self.assertAlmostEqual(call - put, s * math.exp(-q * t) - k * math.exp(-r * t), places=10)

    def test_the_european_call_formula_without_dividends(self) -> None:
        # C = S N(d) - K e^(-rt) N(d - sigma sqrt(t)), with d = (ln(S/K) + (r + sigma^2/2) t) / (sigma sqrt(t))
        s, k, t, r, sigma = 48.62, 50.0, 0.25, 0.0393, 0.34
        d = (math.log(s / k) + (r + sigma * sigma / 2) * t) / (sigma * math.sqrt(t))
        expected = s * bsm.norm_cdf(d) - k * math.exp(-r * t) * bsm.norm_cdf(d - sigma * math.sqrt(t))
        self.assertAlmostEqual(bsm.price("call", s, k, t, r, 0.0, sigma), expected, places=12)

    def test_prices_stay_inside_their_bounds(self) -> None:
        for kind, s, k, t, r, q, sigma in GRID:
            low, high = bsm.bounds(kind, s, k, t, r, q)
            value = bsm.price(kind, s, k, t, r, q, sigma)
            self.assertGreaterEqual(value, low - 1e-12)
            self.assertLess(value, high)

    def test_bad_inputs_are_refused(self) -> None:
        for args in (("swap", 50, 50, 0.1, 0, 0, 0.2), ("call", 0, 50, 0.1, 0, 0, 0.2), ("call", 50, 50, 0, 0, 0, 0.2),
                     ("call", 50, 50, 0.1, 0, 0, 0), ("put", 50, -1, 0.1, 0, 0, 0.2)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                bsm.price(*args)


class Greeks(unittest.TestCase):
    def test_every_greek_matches_a_finite_difference_of_the_price(self) -> None:
        for kind, s, k, t, r, q, sigma in GRID:
            if t < 0.05 and sigma < 0.2:
                continue  # too sharp near expiry for a central difference at this step
            g = bsm.greeks(kind, s, k, t, r, q, sigma)
            p = lambda s_=s, t_=t, r_=r, v_=sigma: bsm.price(kind, s_, k, t_, r_, q, v_)  # noqa: E731
            hs, hv, ht, hr = s * 1e-4, 1e-5, 1e-6, 1e-6
            with self.subTest(kind=kind, s=s, k=k, t=t, r=r, q=q, sigma=sigma):
                self.assertAlmostEqual(g["price"], p(), places=12)
                self.assertAlmostEqual(g["delta"], (p(s_=s + hs) - p(s_=s - hs)) / (2 * hs), places=6)
                self.assertAlmostEqual(g["gamma"], (p(s_=s + hs) - 2 * p() + p(s_=s - hs)) / (hs * hs), places=4)
                self.assertAlmostEqual(g["vega_per_point"], (p(v_=sigma + hv) - p(v_=sigma - hv)) / (2 * hv) / 100, places=6)
                self.assertAlmostEqual(g["theta_per_day"], -(p(t_=t + ht) - p(t_=t - ht)) / (2 * ht) / 365, places=6)
                self.assertAlmostEqual(g["rho_per_point"], (p(r_=r + hr) - p(r_=r - hr)) / (2 * hr) / 100, places=6)

    def test_signs_and_ranges(self) -> None:
        for kind, s, k, t, r, q, sigma in GRID:
            g = bsm.greeks(kind, s, k, t, r, q, sigma)
            if kind == "call":
                self.assertTrue(0 <= g["delta"] <= math.exp(-q * t))
            else:
                self.assertTrue(-math.exp(-q * t) <= g["delta"] <= 0)
            self.assertGreater(g["gamma"], 0)
            self.assertGreater(g["vega_per_point"], 0)

    def test_calls_and_puts_share_gamma_and_vega(self) -> None:
        call, put = bsm.greeks("call", 48.62, 50, 0.3, 0.0393, 0.012, 0.34), bsm.greeks("put", 48.62, 50, 0.3, 0.0393, 0.012, 0.34)
        self.assertAlmostEqual(call["gamma"], put["gamma"], places=14)
        self.assertAlmostEqual(call["vega_per_point"], put["vega_per_point"], places=14)
        self.assertAlmostEqual(call["delta"] - put["delta"], math.exp(-0.012 * 0.3), places=14)


class ImpliedVolatility(unittest.TestCase):
    def test_round_trip(self) -> None:
        for kind, s, k, t, r, q, sigma in GRID:
            target = bsm.price(kind, s, k, t, r, q, sigma)
            low, _ = bsm.bounds(kind, s, k, t, r, q)
            if target - low < 1e-6:
                continue  # numerically at the bound: volatility cannot be told apart there
            solved, reason = bsm.implied_vol(kind, target, s, k, t, r, q)
            with self.subTest(kind=kind, s=s, k=k, t=t, sigma=sigma):
                self.assertIsNone(reason)
                self.assertAlmostEqual(solved, sigma, places=5)

    def test_prices_outside_the_bounds_have_no_volatility(self) -> None:
        s, k, t, r, q = 48.62, 45.0, 0.1, 0.0393, 0.012
        low, high = bsm.bounds("call", s, k, t, r, q)
        self.assertEqual(bsm.implied_vol("call", low - 0.01, s, k, t, r, q), (None, "at_or_below_lower_bound"))
        self.assertEqual(bsm.implied_vol("call", low, s, k, t, r, q), (None, "at_or_below_lower_bound"))
        self.assertEqual(bsm.implied_vol("call", high, s, k, t, r, q), (None, "at_or_above_upper_bound"))
        self.assertEqual(bsm.implied_vol("put", 0.0, s, k, t, r, q), (None, "at_or_below_lower_bound"))

    def test_a_price_beyond_the_search_range_is_reported(self) -> None:
        s, k, t, r, q = 48.62, 50.0, 0.05, 0.0, 0.0
        too_high = bsm.price("call", s, k, t, r, q, bsm.IV_HIGH) + 0.5
        self.assertLess(too_high, bsm.bounds("call", s, k, t, r, q)[1])
        self.assertEqual(bsm.implied_vol("call", too_high, s, k, t, r, q), (None, "outside_search_range"))

    def test_the_same_inputs_give_the_same_answer(self) -> None:
        first = bsm.implied_vol("put", 2.31, 48.62, 50, 0.2, 0.0393, 0.012)
        self.assertEqual(first, bsm.implied_vol("put", 2.31, 48.62, 50, 0.2, 0.0393, 0.012))


if __name__ == "__main__":
    unittest.main()
