# leakage-safe-regime-backtesting code

Standard-library statistical validation hygiene tools for `packs/leakage-safe-regime-backtesting` (strictly for synthetic or historical statistical evaluation hygiene and never financial or trading advice):

- `regime_backtest.splits`: purged and embargoed expanding-window walk-forward and blocked K-fold split generators plus zero-leakage horizon auditors.
- `regime_backtest.metrics`: Spearman Rank IC and ICIR stratified across causal volatility regimes, linear turnover cost accounting, and multiple-testing Deflated Sharpe Ratio (`deflated_sharpe_ratio`).

Run `make check` to compile with `-W error` and execute the unit tests and worked-example recomputation.
