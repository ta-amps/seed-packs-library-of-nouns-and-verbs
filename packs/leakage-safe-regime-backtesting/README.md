# Leakage-safe regime backtesting

## What this pack lets workers do

A collection of nouns and verbs for synthetic and historical statistical validation hygiene using
purged and embargoed expanding-window walk-forward splits, causal volatility-regime Rank IC and
ICIR, turnover cost accounting and multiple-testing deflation, strictly never as financial,
investment or trading advice. In plain language, nouns are **task objects** (split specs, statistical
formulas, pinned standard-library code, schemas and synthetic fixtures) and verbs are **tasks** a
worker claims. Workers verify that multi-bar forward targets never leak across train/test boundaries,
check whether rank correlation survives across calm and volatile regimes, deduct linear turnover
costs, and penalize data-mined trial multiplicity via Deflated Sharpe probability. No task generates
orders, recommends trades or connects to any brokerage.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Strictly statistical validation hygiene and never financial or trading advice; purge overlapping label horizons; deflate multiple-testing selection bias |
| `spec.walk-forward-hygiene` | Purged expanding-window split settings, causal volatility regime thresholds, turnover cost bps and DSR floor |
| `rules.regime-and-turnover` | Tie-aware Spearman Rank IC, L1 turnover drag (`sum |w_t - w_{t-1}| * bps`) and Euler-Mascheroni trial deflation |
| `tool.regime-backtest` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.validation-receipt` | JSON Schema for a non-advisory statistical hygiene receipt |
| Worked example | Fictional 4-series synthetic panel (`example.synthetic-panel`, `SERIES_A.X..SERIES_D.X`) and recomputed receipt (`example.validation-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `build-purged-splits` | agent, no model | Generate expanding-window walk-forward folds with horizon purging and embargo bars and audit zero leakage |
| `score-regime-ic-and-turnover` | agent, no model | Compute tie-aware Spearman Rank IC and ICIR across causal volatility regimes and deduct turnover drag |
| `deflate-multiple-testing` | agent, no model | Adjust net Sharpe for skewness, kurtosis and `num_trials` to emit a statistical hygiene receipt |

## How to use it

Run `make check` in [code/](code/README.md) to compile with warnings treated as errors and verify
purged split hygiene, regime-stratified Rank IC, turnover cost drag and multiple-testing deflation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these tasks through Tessera.
- Strictly statistical validation hygiene on synthetic or historical panel series: never financial,
  investment or trading advice, with zero orders, trades or broker connections.
- The worked example in `source.json` uses fictional `.X` series and synthetic numbers.
