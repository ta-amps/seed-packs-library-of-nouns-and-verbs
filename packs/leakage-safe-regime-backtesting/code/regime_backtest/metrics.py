"""Regime-stratified Spearman Rank IC / ICIR, turnover costs and multiple-testing Deflated Sharpe Ratio."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

EULER_MASCHERONI = 0.5772156649015329


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(float(v) for v in values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    i = 0
    n = len(indexed)
    while i < n:
        j = i
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = 0.5 * (i + j) + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def spearman_rank_ic(predictions: Sequence[float], outcomes: Sequence[float]) -> float:
    """Compute tie-aware Spearman rank correlation coefficient across cross-sectional units."""
    if len(predictions) != len(outcomes) or len(predictions) < 2:
        return 0.0
    rx = _average_ranks(predictions)
    ry = _average_ranks(outcomes)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if vx <= 1e-12 or vy <= 1e-12:
        return 0.0
    return cov / (vx * vy)


def compute_regime_ic_summary(
    bars: Sequence[Mapping[str, Any]],
    *,
    low_vol_ceiling: float = 0.012,
    high_vol_floor: float = 0.025,
) -> dict[str, Any]:
    """Compute overall and causal volatility-regime stratified Rank IC and ICIR."""
    buckets: dict[str, list[float]] = {
        "all": [],
        "low_vol": [],
        "mid_vol": [],
        "high_vol": [],
    }
    for bar in bars:
        ic = spearman_rank_ic(bar["predictions"], bar["realized_outcomes"])
        vol = float(bar["causal_realized_vol"])
        buckets["all"].append(ic)
        if vol <= low_vol_ceiling:
            buckets["low_vol"].append(ic)
        elif vol >= high_vol_floor:
            buckets["high_vol"].append(ic)
        else:
            buckets["mid_vol"].append(ic)

    summary: dict[str, Any] = {}
    for name, vals in buckets.items():
        if not vals:
            summary[name] = {"count": 0, "mean_rank_ic": 0.0, "std_rank_ic": 0.0, "rank_icir": 0.0}
            continue
        mean_ic = sum(vals) / len(vals)
        if len(vals) >= 2:
            var_ic = sum((v - mean_ic) ** 2 for v in vals) / (len(vals) - 1)
            std_ic = math.sqrt(var_ic)
        else:
            std_ic = 0.0
        icir = (mean_ic / std_ic) if std_ic > 1e-12 else 0.0
        summary[name] = {
            "count": len(vals),
            "mean_rank_ic": round(mean_ic, 6),
            "std_rank_ic": round(std_ic, 6),
            "rank_icir": round(icir, 6),
        }
    return summary


def account_turnover_costs(
    weight_snapshots: Sequence[Sequence[float]],
    realized_outcomes: Sequence[Sequence[float]],
    *,
    cost_bps: float = 10.0,
) -> dict[str, Any]:
    """Compute gross periodic made-up scores, L1 weight turnover, linear cost drag and net series."""
    if len(weight_snapshots) != len(realized_outcomes) or not weight_snapshots:
        raise ValueError("weight_snapshots and realized_outcomes must be non-empty and equal length")

    n_units = len(weight_snapshots[0])
    prev_w = [0.0] * n_units
    gross_series: list[float] = []
    net_series: list[float] = []
    turnovers: list[float] = []
    cost_rate = float(cost_bps) * 1e-4

    for weights, outcomes in zip(weight_snapshots, realized_outcomes):
        if len(weights) != n_units or len(outcomes) != n_units:
            raise ValueError("inconsistent cross-sectional dimension")
        gross = sum(float(w) * float(r) for w, r in zip(weights, outcomes))
        turnover = sum(abs(float(w) - pw) for w, pw in zip(weights, prev_w))
        cost = turnover * cost_rate
        gross_series.append(round(gross, 8))
        net_series.append(round(gross - cost, 8))
        turnovers.append(round(turnover, 8))
        prev_w = [float(w) for w in weights]

    return {
        "gross_series": gross_series,
        "net_series": net_series,
        "mean_turnover": round(sum(turnovers) / len(turnovers), 6),
        "total_cost_drag": round(sum(gross_series) - sum(net_series), 6),
        "gross_cumulative": round(sum(gross_series), 6),
        "net_cumulative": round(sum(net_series), 6),
    }


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Acklam rational approximation for standard normal quantile in (0, 1)."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be strictly between 0 and 1")
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) / (
            ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


def deflated_sharpe_ratio(
    net_series: Sequence[float],
    *,
    num_trials: int = 1,
    cross_trial_sr_std: float = 0.15,
) -> dict[str, Any]:
    """Compute Bailey-Lopez de Prado Deflated Sharpe Ratio accounting for non-normality and multiple trials."""
    n = len(net_series)
    if n < 4:
        raise ValueError("net_series requires at least 4 observations")
    if num_trials < 1:
        raise ValueError("num_trials must be >= 1")

    vals = [float(x) for x in net_series]
    mean_v = sum(vals) / n
    var_v = sum((x - mean_v) ** 2 for x in vals) / (n - 1)
    std_v = math.sqrt(var_v)
    if std_v <= 1e-12:
        return {
            "observed_per_period_sr": 0.0,
            "expected_max_null_sr": 0.0,
            "deflated_sharpe_prob": 0.0,
            "skewness": 0.0,
            "kurtosis": 3.0,
        }

    sr_hat = mean_v / std_v
    m3 = sum(((x - mean_v) / std_v) ** 3 for x in vals) / n
    m4 = sum(((x - mean_v) / std_v) ** 4 for x in vals) / n

    if num_trials == 1:
        sr_zero = 0.0
    else:
        z1 = _norm_ppf(1.0 - 1.0 / float(num_trials))
        z2 = _norm_ppf(1.0 - 1.0 / (float(num_trials) * math.e))
        expected_max_z = (1.0 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2
        sr_zero = float(cross_trial_sr_std) * expected_max_z

    denom_var = max(1e-9, (1.0 - m3 * sr_hat + ((m4 - 1.0) / 4.0) * (sr_hat ** 2)) / float(n - 1))
    z_dsr = (sr_hat - sr_zero) / math.sqrt(denom_var)
    prob = _norm_cdf(z_dsr)

    return {
        "observed_per_period_sr": round(sr_hat, 6),
        "expected_max_null_sr": round(sr_zero, 6),
        "deflated_sharpe_prob": round(prob, 6),
        "skewness": round(m3, 6),
        "kurtosis": round(m4, 6),
    }
