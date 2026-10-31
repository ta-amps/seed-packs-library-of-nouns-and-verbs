"""CLI entrypoint for purged walk-forward splits, regime Rank IC/ICIR, turnover costs and DSR."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .metrics import account_turnover_costs, compute_regime_ic_summary, deflated_sharpe_ratio
from .splits import generate_purged_walk_forward_splits, verify_split_hygiene


def run_validation_audit(bundle: dict[str, Any]) -> dict[str, Any]:
    """Run complete leakage-safe split audit, regime IC summary, turnover accounting and DSR check."""
    cfg = bundle["split_config"]
    splits = generate_purged_walk_forward_splits(
        n_bars=int(cfg["n_bars"]),
        min_train_bars=int(cfg["min_train_bars"]),
        test_bars=int(cfg["test_bars"]),
        step_bars=cfg.get("step_bars"),
        label_horizon_bars=int(cfg["label_horizon_bars"]),
        embargo_bars=int(cfg["embargo_bars"]),
    )
    hygiene = verify_split_hygiene(
        splits,
        label_horizon_bars=int(cfg["label_horizon_bars"]),
        embargo_bars=int(cfg["embargo_bars"]),
    )

    bars = bundle["out_of_sample_bars"]
    regime_ic = compute_regime_ic_summary(
        bars,
        low_vol_ceiling=float(bundle.get("low_vol_ceiling", 0.012)),
        high_vol_floor=float(bundle.get("high_vol_floor", 0.025)),
    )
    costs = account_turnover_costs(
        [b["weights"] for b in bars],
        [b["realized_outcomes"] for b in bars],
        cost_bps=float(bundle.get("cost_bps", 10.0)),
    )
    dsr = deflated_sharpe_ratio(
        costs["net_series"],
        num_trials=int(bundle.get("num_trials", 10)),
        cross_trial_sr_std=float(bundle.get("cross_trial_sr_std", 0.15)),
    )

    passes_hygiene_gate = (
        hygiene["leakage_free"]
        and regime_ic["all"]["mean_rank_ic"] > 0.0
        and costs["net_cumulative"] > 0.0
        and dsr["deflated_sharpe_prob"] >= float(bundle.get("min_dsr_prob", 0.90))
    )

    return {
        "leakage_free": hygiene["leakage_free"],
        "num_folds": hygiene["num_folds"],
        "overall_mean_rank_ic": regime_ic["all"]["mean_rank_ic"],
        "overall_rank_icir": regime_ic["all"]["rank_icir"],
        "regime_mean_ic": {
            "low_vol": regime_ic["low_vol"]["mean_rank_ic"],
            "mid_vol": regime_ic["mid_vol"]["mean_rank_ic"],
            "high_vol": regime_ic["high_vol"]["mean_rank_ic"],
        },
        "mean_turnover": costs["mean_turnover"],
        "net_cumulative": costs["net_cumulative"],
        "deflated_sharpe_prob": dsr["deflated_sharpe_prob"],
        "passes_hygiene_gate": passes_hygiene_gate,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Leakage-safe statistical validation hygiene (never financial or trading advice)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sp = sub.add_parser("splits", help="Generate and verify purged/embargoed walk-forward splits")
    p_sp.add_argument("--input", required=True, type=Path)

    p_au = sub.add_parser("audit", help="Run full split hygiene, regime IC/ICIR, turnover and DSR audit")
    p_au.add_argument("--input", required=True, type=Path)

    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))

    if args.cmd == "splits":
        cfg = payload.get("split_config", payload)
        splits = generate_purged_walk_forward_splits(
            n_bars=int(cfg["n_bars"]),
            min_train_bars=int(cfg["min_train_bars"]),
            test_bars=int(cfg["test_bars"]),
            step_bars=cfg.get("step_bars"),
            label_horizon_bars=int(cfg["label_horizon_bars"]),
            embargo_bars=int(cfg["embargo_bars"]),
        )
        out: Any = {
            "splits": splits,
            "hygiene": verify_split_hygiene(
                splits,
                label_horizon_bars=int(cfg["label_horizon_bars"]),
                embargo_bars=int(cfg["embargo_bars"]),
            ),
        }
    else:
        out = run_validation_audit(payload)

    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
