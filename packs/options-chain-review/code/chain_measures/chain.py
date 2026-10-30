"""Measures, liquidity screens and roll candidates for one options chain snapshot.

Everything here describes and compares. Nothing ranks a contract, recommends a roll, sizes a position or
prices an order: a roll candidate's mid_difference is the difference of two quoted mids at one snapshot,
not a price anyone could trade at. Values the data provider gave are kept as given; recomputed values
and their differences sit beside them.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from . import bsm
from .ivrank import history_problems, iv_rank

MODEL = "black_scholes_merton_european"
GREEKS = ("delta", "gamma", "theta_per_day", "vega_per_point")
SCREENS = ("two_sided", "spread", "open_interest", "volume", "quote_age")
SECONDS_PER_YEAR = 365 * 86400


def parse_time(text: str) -> datetime:
    """An ISO 8601 UTC time such as 2026-10-30T19:30:00Z; Python 3.10 reads the Z only as +00:00."""
    if not isinstance(text, str):
        raise ValueError(f"not a timestamp: {text!r}")
    value = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    if value.tzinfo is None:
        raise ValueError(f"timestamp has no time zone: {text!r}")
    return value


def _number(value: Any) -> bool:
    return type(value) in (int, float)


def _round(value: float, places: int) -> float:
    """Round half to even, as Python does, and never return a negative zero."""
    return round(value, places) + 0.0


def check_snapshot(request: dict[str, Any], snapshot: dict[str, Any], history: dict[str, Any]) -> list[str]:
    """Problems that stop a review before any measure is computed: terms, scope, timestamps and shape."""
    problems: list[str] = []
    source = snapshot.get("source", {})
    if not source.get("terms_read_on"):
        problems.append("source: the date its terms were read is missing")
    if source.get("brokerage_connection") is not False:
        problems.append("source: a brokerage or trading account connection is never used")
    if source.get("storage_permitted") is not True:
        problems.append("source: its terms do not permit storing this snapshot in the requester's scope")
    if source.get("access") == "licensed_api" and source.get("automated_access_permitted") is not True:
        problems.append("source: its terms do not permit automated access")
    symbol = request["underlying"]["symbol"]
    if snapshot["underlying"].get("symbol") != symbol:
        problems.append("underlying: not the requested symbol")
    taken = parse_time(snapshot["snapshot_at"])
    try:
        quoted = parse_time(snapshot["underlying"]["quote_time"])
        if quoted > taken:
            problems.append("underlying: quote time is after the snapshot time")
        elif (taken - quoted).total_seconds() > request["screens"]["max_quote_age_seconds"]:
            problems.append("underlying: its price is older than max_quote_age_seconds; capture a fresh snapshot")
    except (KeyError, ValueError):
        problems.append("underlying: quote time is missing or malformed")
    window = request["strike_window"]
    seen: set[str] = set()
    for row in snapshot["contracts"]:
        name = row.get("symbol", "?")
        if name in seen:
            problems.append(f"{name}: listed twice")
        seen.add(name)
        if row.get("type") not in bsm.KINDS:
            problems.append(f"{name}: type is call or put")
        if row.get("expiry") not in request["expiries"]:
            problems.append(f"{name}: expiry not requested")
        if not (_number(row.get("strike")) and window["min"] <= row["strike"] <= window["max"]):
            problems.append(f"{name}: strike outside the requested window")
        try:
            if parse_time(row["quote_time"]) > taken:
                problems.append(f"{name}: quote time is after the snapshot time")
            if parse_time(row["expires_at"]) <= taken:
                problems.append(f"{name}: already expired at the snapshot time")
        except (KeyError, ValueError):
            problems.append(f"{name}: quote time or expiration time is missing or malformed")
        for field in ("bid", "ask"):
            if not (_number(row.get(field)) and row[field] >= 0):
                problems.append(f"{name}: {field} is a number at least 0")
        for field in ("volume", "open_interest"):
            if not (type(row.get(field)) is int and row[field] >= 0):
                problems.append(f"{name}: {field} is a whole number at least 0")
    if history.get("symbol") != symbol or history.get("measure") != request["iv_history"]["measure"]:
        problems.append("iv history: not the requested symbol and measure")
    problems += [f"iv history: {item}" for item in history_problems(history.get("observations", []))]
    return problems


def contract_measures(row: dict[str, Any], spot: float, taken: datetime, rate: float, dividend: float,
                      tolerances: dict[str, float]) -> dict[str, Any]:
    t = (parse_time(row["expires_at"]) - taken).total_seconds() / SECONDS_PER_YEAR
    bid, ask = row["bid"], row["ask"]
    two_sided = bid > 0 and ask > bid
    mid = _round((bid + ask) / 2, 4) if two_sided else None
    out: dict[str, Any] = {
        "symbol": row["symbol"], "type": row["type"], "strike": row["strike"], "expiry": row["expiry"],
        "quote_time": row["quote_time"],
        "quote_age_seconds": int((taken - parse_time(row["quote_time"])).total_seconds()),
        "days_to_expiry": (date.fromisoformat(row["expiry"]) - taken.date()).days,
        "years_to_expiry": _round(t, 6),
        "bid": bid, "ask": ask, "two_sided": two_sided, "mid": mid,
        "spread": _round(ask - bid, 4),
        "spread_pct_of_mid": _round((ask - bid) / mid * 100, 2) if mid else None,
        "open_interest": row["open_interest"], "volume": row["volume"],
        "provider_iv": row.get("provider_iv"),
        "iv_from_mid": None, "iv_from_mid_reason": "no_two_sided_quote" if mid is None else None,
        "iv_difference": None,
        "provider_greeks": row.get("provider_greeks"),
        "recomputed_greeks": None, "greek_differences": None, "flags": [],
    }
    if mid is not None:
        solved, reason = bsm.implied_vol(row["type"], mid, spot, row["strike"], t, rate, dividend)
        out["iv_from_mid_reason"] = reason
        if solved is not None:
            out["iv_from_mid"] = _round(solved, 4)
            if _number(row.get("provider_iv")):
                out["iv_difference"] = _round(row["provider_iv"] - solved, 4)
                if abs(out["iv_difference"]) > tolerances["iv"]:
                    out["flags"].append("iv_differs")
    if _number(row.get("provider_iv")) and row["provider_iv"] > 0:
        model = bsm.greeks(row["type"], spot, row["strike"], t, rate, dividend, row["provider_iv"])
        out["recomputed_greeks"] = {"price": _round(model["price"], 4), **{g: _round(model[g], 4) for g in GREEKS}}
        given = row.get("provider_greeks") or {}
        if all(_number(given.get(g)) for g in GREEKS):
            out["greek_differences"] = {g: _round(given[g] - model[g], 4) for g in GREEKS}
            out["flags"] += [f"{g}_differs" for g in GREEKS if abs(out["greek_differences"][g]) > tolerances[g]]
    return out


def measures(request: dict[str, Any], snapshot: dict[str, Any], history: dict[str, Any]) -> dict[str, Any]:
    """Every number the review may cite, computed from the snapshot, the history and the request's assumptions."""
    problems = check_snapshot(request, snapshot, history)
    if problems:
        raise ValueError("; ".join(problems))
    taken = parse_time(snapshot["snapshot_at"])
    spot = snapshot["underlying"]["price"]
    rate = request["assumptions"]["rate"]["value"]
    dividend = request["assumptions"]["dividend_yield"]["value"]
    rows = [contract_measures(row, spot, taken, rate, dividend, request["tolerances"]) for row in snapshot["contracts"]]
    flags: dict[str, int] = {}
    for row in rows:
        for flag in row["flags"]:
            flags[flag] = flags.get(flag, 0) + 1
    settings = request["iv_history"]
    rank = iv_rank(history["observations"], settings["lookback_observations"], settings["min_observations"])
    return {
        "model": MODEL,
        "snapshot_at": snapshot["snapshot_at"],
        "underlying": dict(snapshot["underlying"]),
        "underlying_quote_age_seconds": int((taken - parse_time(snapshot["underlying"]["quote_time"])).total_seconds()),
        "rate": rate,
        "dividend_yield": dividend,
        "contracts": rows,
        "flag_counts": dict(sorted(flags.items())),
        "iv_rank": {"measure": history["measure"], **rank},
    }


def screen(request: dict[str, Any], measured: dict[str, Any]) -> dict[str, Any]:
    """Apply the person's liquidity screens to every contract; none is dropped, every failure is named."""
    limits = request["screens"]
    results = []
    for row in measured["contracts"]:
        failed = []
        if not row["two_sided"]:
            failed.append("two_sided")
        if row["spread_pct_of_mid"] is None or row["spread_pct_of_mid"] > limits["max_spread_pct_of_mid"]:
            failed.append("spread")
        if row["open_interest"] < limits["min_open_interest"]:
            failed.append("open_interest")
        if row["volume"] < limits["min_volume"]:
            failed.append("volume")
        if row["quote_age_seconds"] > limits["max_quote_age_seconds"]:
            failed.append("quote_age")
        results.append({
            "symbol": row["symbol"],
            "passed": not failed,
            "failed": failed,
            "measured": {"two_sided": row["two_sided"], "spread_pct_of_mid": row["spread_pct_of_mid"],
                         "open_interest": row["open_interest"], "volume": row["volume"],
                         "quote_age_seconds": row["quote_age_seconds"]},
        })
    passed = sum(1 for item in results if item["passed"])
    return {"screens": dict(limits), "results": results, "passed": passed, "failed": len(results) - passed}


def _difference(a: Any, b: Any) -> float | None:
    return _round(a - b, 4) if _number(a) and _number(b) else None


def _greek(row: dict[str, Any], name: str) -> Any:
    return (row.get("provider_greeks") or {}).get(name)


def roll_candidates(request: dict[str, Any], measured: dict[str, Any], screened: dict[str, Any]) -> dict[str, Any]:
    """Contracts of the reference's type at the same strike and a later expiry, or at a different strike and the
    same or a later expiry, each compared with the reference. Ordered by expiry, then strike; never ranked."""
    by_symbol = {row["symbol"]: row for row in measured["contracts"]}
    results = {item["symbol"]: item for item in screened["results"]}
    if request["reference_contract"] not in by_symbol:
        raise ValueError("the reference contract is not in the snapshot")
    ref = by_symbol[request["reference_contract"]]

    def describe(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": row["symbol"], "expiry": row["expiry"], "strike": row["strike"],
            "days_to_expiry": row["days_to_expiry"], "mid": row["mid"],
            "delta": _greek(row, "delta"), "theta_per_day": _greek(row, "theta_per_day"),
            "vega_per_point": _greek(row, "vega_per_point"), "iv": row["provider_iv"],
            "open_interest": row["open_interest"], "volume": row["volume"],
            "spread_pct_of_mid": row["spread_pct_of_mid"],
            "screen_passed": results[row["symbol"]]["passed"], "failed_screens": results[row["symbol"]]["failed"],
        }

    def compare(row: dict[str, Any]) -> dict[str, Any]:
        item = describe(row)
        item.update(
            mid_difference=_difference(row["mid"], ref["mid"]),
            delta_difference=_difference(_greek(row, "delta"), _greek(ref, "delta")),
            theta_difference=_difference(_greek(row, "theta_per_day"), _greek(ref, "theta_per_day")),
            vega_difference=_difference(_greek(row, "vega_per_point"), _greek(ref, "vega_per_point")),
            iv_difference=_difference(row["provider_iv"], ref["provider_iv"]),
        )
        return item

    window = request["strike_window"]
    pool = sorted(
        (row for row in measured["contracts"]
         if row["symbol"] != ref["symbol"] and row["type"] == ref["type"] and row["expiry"] >= ref["expiry"]
         and window["min"] <= row["strike"] <= window["max"]),
        key=lambda row: (row["expiry"], row["strike"]),
    )
    return {
        "reference": describe(ref),
        "order": "expiry, then strike",
        "same_strike_later_expiry": [compare(row) for row in pool if row["strike"] == ref["strike"] and row["expiry"] > ref["expiry"]],
        "different_strike": [compare(row) for row in pool if row["strike"] != ref["strike"]],
    }
