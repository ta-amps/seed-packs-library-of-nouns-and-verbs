# Benchmark scores

## What this pack lets workers do

A collection of nouns and verbs for keeping benchmark scores current and comparable.
Workers record every score with its source, date, hardware, setup and method, refresh
the watched ones daily, flag stale or contradicted scores with a fixed rule, check the
claims that matter on your own hardware, and note when a new score agrees or disagrees
with earlier ones.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | When two scores are comparable, and who reported each |
| Staleness policy | Max ages per reporter, version changes, contradiction by our own run, missing setup |
| Worked example | Made-up: six scores and their flags, which the validator recomputes |
| Templates | Score, benchmark, watch list, comparison and staleness report |
| Daily refresh | A proposal: refresh and flag daily at 06:00 UTC; not activated |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| collect-scores | Records new reported scores with full provenance | Scores |
| refresh-scores | Re-reads sources and supersedes changed scores | New score versions |
| flag-stale | Applies the policy and proposes refresh or comparison verbs; deterministic | Staleness report |
| compare-on-profile | Reproduces a claim twice on your hardware under committed pass marks | Comparison |
| situate-score | Records whether a new score corroborates or contradicts earlier ones | Score with relations |

Each verb can also end with `no_change`, `unknown` or `blocked`.

## Recurring runs

Recurring execution needs Tessera's flag-gated schedule support, which is being
designed now. **No scheduler is activated by this pack.**

## How to use it

Write a watch list and source cards for the benchmarks you care about. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- Scores without hardware stay unverified; they are never averaged into one number.
- Our own reproductions follow the [evaluation-design](../evaluation-design/README.md) method.
- A proposal: no score has been collected or refreshed with these verbs yet.
