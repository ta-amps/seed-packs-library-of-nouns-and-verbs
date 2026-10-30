"""Implied volatility rank and percentile of one named measure over its own history.

Providers define these differently, so this pack fixes one definition and names the measure every time:
the lookback is the most recent `lookback` observations, ending with the current one;
rank = (current - low) / (high - low) * 100 over the lookback, and percentile = the share of the earlier
lookback observations strictly below the current one, times 100. Both are rounded to one decimal.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def history_problems(observations: list[dict[str, Any]]) -> list[str]:
    """Dates must be ISO dates in strictly increasing order and every value a positive number."""
    problems = []
    previous = None
    for i, item in enumerate(observations):
        try:
            day = date.fromisoformat(item["date"])
        except (KeyError, TypeError, ValueError):
            problems.append(f"observation {i}: date is not an ISO date")
            continue
        value = item.get("iv")
        if type(value) not in (int, float) or not value > 0:
            problems.append(f"observation {i}: iv is not a positive number")
        if previous is not None and day <= previous:
            problems.append(f"observation {i}: dates are not strictly increasing")
        previous = day
    return problems


def iv_rank(observations: list[dict[str, Any]], lookback: int, min_observations: int) -> dict[str, Any]:
    """Rank and percentile of the last observation, or null values with the reason they are unknown."""
    if lookback < 2 or min_observations < 2 or min_observations > lookback:
        raise ValueError("lookback and min_observations must be at least 2, and min_observations at most lookback")
    problems = history_problems(observations)
    if problems:
        raise ValueError("; ".join(problems))
    window = observations[-lookback:]
    result: dict[str, Any] = {
        "observations": len(window),
        "first_date": window[0]["date"] if window else None,
        "current_date": window[-1]["date"] if window else None,
        "current": window[-1]["iv"] if window else None,
        "low": None, "low_date": None, "high": None, "high_date": None,
        "rank": None, "percentile": None, "reason": None,
    }
    if len(window) < min_observations:
        result["reason"] = "too_few_observations"
        return result
    lowest = min(window, key=lambda item: (item["iv"], item["date"]))
    highest = max(window, key=lambda item: (item["iv"], item["date"]))
    result.update(low=lowest["iv"], low_date=lowest["date"], high=highest["iv"], high_date=highest["date"])
    current = window[-1]["iv"]
    if highest["iv"] == lowest["iv"]:
        result["reason"] = "flat_history"
        return result
    earlier = [item["iv"] for item in window[:-1]]
    result["rank"] = round((current - lowest["iv"]) / (highest["iv"] - lowest["iv"]) * 100, 1)
    result["percentile"] = round(sum(1 for value in earlier if value < current) / len(earlier) * 100, 1)
    return result
