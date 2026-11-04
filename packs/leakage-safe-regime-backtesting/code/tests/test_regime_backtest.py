"""Unit tests for purged/embargoed splits, regime Rank IC/ICIR, turnover costs and Deflated Sharpe Ratio."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from regime_backtest.__main__ import run_validation_audit
from regime_backtest.metrics import (
    account_turnover_costs,
    compute_regime_ic_summary,
    deflated_sharpe_ratio,
    spearman_rank_ic,
)
from regime_backtest.splits import (
    generate_purged_kfold_splits,
    generate_purged_walk_forward_splits,
    verify_split_hygiene,
)

PACK_SOURCE = Path(__file__).resolve().parents[2] / "source.json"


class RegimeBacktestTest(unittest.TestCase):
    def test_purged_walk_forward_and_kfold_prevent_horizon_leakage(self) -> None:
        wf = generate_purged_walk_forward_splits(
            n_bars=60,
            min_train_bars=20,
            test_bars=10,
            step_bars=12,
            label_horizon_bars=3,
            embargo_bars=2,
        )
        self.assertEqual(len(wf), 3)
        audit = verify_split_hygiene(wf, label_horizon_bars=3, embargo_bars=2)
        self.assertTrue(audit["leakage_free"])

        # Inject a horizon-leaking training index right before test_start and verify detection
        leaky = [dict(wf[0], train_indices=list(wf[0]["train_indices"]) + [wf[0]["test_indices"][0] - 1])]
        bad_audit = verify_split_hygiene(leaky, label_horizon_bars=3, embargo_bars=2)
        self.assertFalse(bad_audit["leakage_free"])
        self.assertTrue(any("pre_test_label_horizon_leak" in v for v in bad_audit["violations"]))

        kf = generate_purged_kfold_splits(n_bars=40, n_splits=4, label_horizon_bars=3, embargo_bars=2)
        kf_audit = verify_split_hygiene(
            kf, label_horizon_bars=3, embargo_bars=2, require_causal_walk_forward=False
        )
        self.assertTrue(kf_audit["leakage_free"])

    def test_spearman_rank_ic_and_regime_stratification(self) -> None:
        self.assertAlmostEqual(spearman_rank_ic([1.0, 2.0, 3.0, 4.0], [-0.2, 0.0, 0.1, 0.5]), 1.0, places=6)
        self.assertAlmostEqual(spearman_rank_ic([1.0, 2.0, 3.0, 4.0], [0.5, 0.1, 0.0, -0.2]), -1.0, places=6)
        # Tie handling
        tied = spearman_rank_ic([1.0, 1.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0])
        self.assertGreater(tied, 0.90)

        bars = [
            {"causal_realized_vol": 0.008, "predictions": [1, 2, 3, 4], "realized_outcomes": [1, 2, 3, 4]},
            {"causal_realized_vol": 0.010, "predictions": [1, 2, 3, 4], "realized_outcomes": [1, 3, 2, 4]},
            {"causal_realized_vol": 0.030, "predictions": [1, 2, 3, 4], "realized_outcomes": [4, 3, 2, 1]},
        ]
        summary = compute_regime_ic_summary(bars, low_vol_ceiling=0.012, high_vol_floor=0.025)
        self.assertGreater(summary["low_vol"]["mean_rank_ic"], 0.8)
        self.assertAlmostEqual(summary["high_vol"]["mean_rank_ic"], -1.0, places=6)

    def test_turnover_cost_accounting_and_multiple_testing_deflation(self) -> None:
        # High-churn weights flip sign every bar so turnover drag turns positive gross into negative net
        weights = [[-0.5, 0.5], [0.5, -0.5], [-0.5, 0.5], [0.5, -0.5]]
        outcomes = [[-0.001, 0.001], [0.001, -0.001], [-0.001, 0.001], [0.001, -0.001]]
        costs = account_turnover_costs(weights, outcomes, cost_bps=15.0)
        self.assertGreater(costs["gross_cumulative"], 0.0)
        self.assertLess(costs["net_cumulative"], 0.0)

        modest_series = [0.004, 0.002, -0.001, 0.003, 0.001, 0.002, -0.002, 0.003, 0.002, 0.001, 0.003, -0.001]
        single_trial = deflated_sharpe_ratio(modest_series, num_trials=1, cross_trial_sr_std=0.35)
        mined_500_trials = deflated_sharpe_ratio(modest_series, num_trials=500, cross_trial_sr_std=0.35)
        self.assertGreater(single_trial["deflated_sharpe_prob"], 0.95)
        self.assertLess(mined_500_trials["deflated_sharpe_prob"], 0.50)

    def test_pack_worked_example_recomputes_exactly(self) -> None:
        source = json.loads(PACK_SOURCE.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in source["nouns"]}
        inp = nouns["example.made-up-panel"]
        expected = nouns["example.validation-receipt"]["instance"]

        actual = run_validation_audit(inp)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
