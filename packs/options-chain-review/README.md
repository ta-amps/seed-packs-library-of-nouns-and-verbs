# Options chain review

## What this pack lets workers do

A collection of nouns and verbs for reviewing an options chain descriptively, never as financial
advice. Workers read one timestamped snapshot from an official or licensed data source the requester
already has access to, under its terms, then recompute the greeks with a Black-Scholes-Merton model
beside the provider's, solve implied volatility from each mid, place the 30-day implied volatility in
its one-year range, apply the person's liquidity screens and list roll candidates at the same strike
and a later expiry or at a different strike. A review describes and compares only, a different worker
rechecks every number, and a person decides what is delivered. No verb trades, places or previews an
order, or connects to a brokerage. The guardrails come from the
[public company research pack](../public-company-research/README.md) and the
[policy and law watch pack](../policy-and-law-watch/README.md); this pack adds only the one they lack.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails, defined once | Pinned: not financial advice; no trades, orders or brokerage access; a person decides; cite every number; respect each provider's terms. New: every market data number carries its data timestamp |
| Data access rules | Licensed or official sources the requester already has, terms read first, no brokerage, no scraping, licensed prices kept to the people the terms cover |
| Option math rules | The model's formulas, time to expiry from the source's expiration time, mids, bounds, rounding, tolerances, and this pack's one definition of implied volatility rank and percentile |
| Screen and candidate rules | Five screens the person sets, and roll candidates ordered by expiry and strike, never ranked |
| Tool card | The pack's tested code in [code/](code/README.md), pinned by digest |
| Templates | Review request, chain snapshot, implied volatility history, chain measures, liquidity screen, roll candidates, chain review, review check |
| Review checks | Ten checks on a review, with one good and ten bad reviews the validator recomputes |
| Checklist, sources, test cases | What a person checks before delivery; 6 dated public sources; 10 made-up cases |
| Worked example | Made-up: nine calls on a fictional underlying, FERN.X, from one delayed snapshot |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `capture-chain` | agent, no model | One snapshot and one history, under the source's terms, with digests |
| `compute-measures` | agent, no model | Mids, spreads, implied volatility, greeks beside the provider's, the rank |
| `screen-liquidity` | agent, no model | The person's screens on every contract; nothing dropped |
| `list-roll-candidates` | agent, no model | Same strike and later expiries, other strikes, each beside the reference |
| `write-chain-review` | agent | A plain review, every figure with its data timestamp, marked Not financial advice |
| `check-chain-review` | a different agent or a person | Every number recomputed and every phrase checked |
| `decide-delivery` | person | Deliver or hold the checked review |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose follow-up verbs.
Verbs for a person are claimed by people, never by an agent.

## Worked example

All made-up. In a snapshot of 2026-10-30 19:30 UTC, delayed 15 minutes, FERN.X trades at 48.62. The
pack's code recomputes the greeks of nine calls and flags one provider delta 0.0313 above the model,
finds one quote 1669 seconds older than the snapshot, fails five contracts on the person's screens and lists eight roll
candidates for the 50-strike call expiring 2026-11-20. The 30-day implied volatility of 33.65% ranks
81.5 in its last 252 observations.

## How to use it

Run `make check` in [code/](code/README.md) to recompute the worked example. Write a review request
shaped like `template.review-request`, write the nouns in [nouns.json](nouns.json) create-only with a
key scoped to your team's surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- Not financial advice. A review describes one snapshot; any decision about a position stays with a person.
- The worked example is made-up: its underlying ends in .X so it never matches a listed security, and
  its rate, dividend yield, quotes and history are made up. The code's tests recompute its numbers.
- The model is for European options. American-style options can differ, so differences are recorded, never corrected.
- Market data terms vary by provider and subscriber; the rules say to stop when they forbid the reading.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
