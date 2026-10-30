# Chain measures

Recomputes every number a descriptive options chain review cites, so a reviewer can check it without
the drafter's tools: a snapshot's terms, scope and timestamps, Black-Scholes-Merton greeks at the
provider's implied volatility beside the provider's own greeks, implied volatility from each mid,
spreads, an implied volatility rank and percentile over one named measure's history, the person's
liquidity screens, and roll candidates compared with a reference contract. Python 3.10 or later,
standard library only.

```bash
make check                                    # compile, then every test
python -m chain_measures check --request REQUEST.json --snapshot SNAPSHOT.json --history HISTORY.json
python -m chain_measures measures --request REQUEST.json --snapshot SNAPSHOT.json --history HISTORY.json
python -m chain_measures screen --request REQUEST.json --snapshot SNAPSHOT.json --history HISTORY.json
python -m chain_measures candidates --request REQUEST.json --snapshot SNAPSHOT.json --history HISTORY.json
python -m chain_measures iv-rank --history HISTORY.json --lookback 252 --min-observations 200
```

The model is for European options; American-style options can differ, so a gap between a provider's
greek and the recomputation is recorded as a difference, never corrected. The tests check put-call
parity, every greek against finite differences of the price, implied volatility round trips and
bounds, and recompute the pack's worked example from [source.json](../source.json). Nothing here
ranks or recommends a contract, prices or places an order, connects to a brokerage, opens a network
connection or writes a file. MIT license, written for this pack by ta-amps.
