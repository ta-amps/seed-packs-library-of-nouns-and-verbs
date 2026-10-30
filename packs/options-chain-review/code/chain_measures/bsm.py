"""Black-Scholes-Merton prices, greeks and implied volatility for European options, standard library only.

S is the underlying price, K the strike, T the time to expiry in years, r the continuously compounded
risk-free rate, q the continuous dividend yield and sigma the volatility, all as decimals. Theta is per
calendar day (per year divided by 365), vega and rho are per percentage point (per 1.00 divided by 100).
These are model values for a European option. American-style options can differ, so a difference from
a data provider's value is recorded as a difference, never as the provider's error.
"""

from __future__ import annotations

import math

KINDS = ("call", "put")
SQRT2 = math.sqrt(2.0)
SQRT_2PI = math.sqrt(2.0 * math.pi)
# Implied volatility search range and stopping rule. Bisection is slow but needs no derivative and always
# gives the same answer for the same inputs.
IV_LOW = 1e-4
IV_HIGH = 5.0
IV_TOLERANCE = 1e-10
IV_MAX_ITERATIONS = 200


def norm_cdf(x: float) -> float:
    """The standard normal distribution function, from the complementary error function."""
    return 0.5 * math.erfc(-x / SQRT2)


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _require(kind: str, s: float, k: float, t: float, sigma: float | None = None) -> None:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, not {kind!r}")
    if not (s > 0 and k > 0 and t > 0):
        raise ValueError("the underlying price, strike and time to expiry must be positive")
    if sigma is not None and not sigma > 0:
        raise ValueError("volatility must be positive")


def d1_d2(s: float, k: float, t: float, r: float, q: float, sigma: float) -> tuple[float, float]:
    vol_t = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / vol_t
    return d1, d1 - vol_t


def price(kind: str, s: float, k: float, t: float, r: float, q: float, sigma: float) -> float:
    _require(kind, s, k, t, sigma)
    d1, d2 = d1_d2(s, k, t, r, q, sigma)
    held, paid = s * math.exp(-q * t), k * math.exp(-r * t)
    if kind == "call":
        return held * norm_cdf(d1) - paid * norm_cdf(d2)
    return paid * norm_cdf(-d2) - held * norm_cdf(-d1)


def greeks(kind: str, s: float, k: float, t: float, r: float, q: float, sigma: float) -> dict[str, float]:
    """Price, delta, gamma, theta per calendar day, vega per volatility point and rho per rate point."""
    _require(kind, s, k, t, sigma)
    d1, d2 = d1_d2(s, k, t, r, q, sigma)
    df_q, df_r, root_t = math.exp(-q * t), math.exp(-r * t), math.sqrt(t)
    density = norm_pdf(d1)
    gamma = df_q * density / (s * sigma * root_t)
    vega = s * df_q * density * root_t
    decay = -s * df_q * density * sigma / (2.0 * root_t)
    if kind == "call":
        delta = df_q * norm_cdf(d1)
        theta = decay - r * k * df_r * norm_cdf(d2) + q * s * df_q * norm_cdf(d1)
        rho = k * t * df_r * norm_cdf(d2)
    else:
        delta = -df_q * norm_cdf(-d1)
        theta = decay + r * k * df_r * norm_cdf(-d2) - q * s * df_q * norm_cdf(-d1)
        rho = -k * t * df_r * norm_cdf(-d2)
    return {
        "price": price(kind, s, k, t, r, q, sigma),
        "delta": delta,
        "gamma": gamma,
        "theta_per_day": theta / 365.0,
        "vega_per_point": vega / 100.0,
        "rho_per_point": rho / 100.0,
    }


def bounds(kind: str, s: float, k: float, t: float, r: float, q: float) -> tuple[float, float]:
    """The no-arbitrage range a European option price lies strictly inside for any positive volatility."""
    _require(kind, s, k, t)
    held, paid = s * math.exp(-q * t), k * math.exp(-r * t)
    if kind == "call":
        return max(0.0, held - paid), held
    return max(0.0, paid - held), paid


def implied_vol(kind: str, target: float, s: float, k: float, t: float, r: float, q: float) -> tuple[float | None, str | None]:
    """The volatility at which the model price equals target, by bisection, or None with the reason."""
    lower, upper = bounds(kind, s, k, t, r, q)
    if not target > lower:
        return None, "at_or_below_lower_bound"
    if not target < upper:
        return None, "at_or_above_upper_bound"
    if target < price(kind, s, k, t, r, q, IV_LOW) or target > price(kind, s, k, t, r, q, IV_HIGH):
        return None, "outside_search_range"
    low, high = IV_LOW, IV_HIGH
    for _ in range(IV_MAX_ITERATIONS):
        middle = 0.5 * (low + high)
        if price(kind, s, k, t, r, q, middle) < target:
            low = middle
        else:
            high = middle
        if high - low < IV_TOLERANCE:
            break
    return 0.5 * (low + high), None
