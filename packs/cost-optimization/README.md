# Cost optimization

## What this pack lets workers do

Find where a project's money goes and how to spend less without breaking anything.
Workers build a ledger from usage exports and invoices you supply, read dated public
prices, propose savings with their arithmetic and risks, measure the promising ones
before and after, and recommend changes for you to make. Billed, measured, estimated
and credit amounts never get mixed, and unknown amounts stay unknown.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | Four kinds of numbers kept apart, dated prices, nulls not zeros, quality must hold, the caller's model settings kept |
| Templates | Cost ledger, price card (with a synthetic example), saving hypothesis, saving result, recommendation and review |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| inventory-costs | One ledger line per service and unit, with its source | Cost ledger |
| price-check | Reads public pricing pages; never logs in | Price cards |
| propose-savings | Concrete savings with arithmetic and risks | Saving hypotheses |
| measure-saving | Before and after, two runs each, locally, with committed pass marks | Saving result |
| recommend | Do, measure first or no change, with trade-offs | Recommendation |
| review-recommendation | A different worker recomputes every saving | Review |

Each verb can also end with `no_change`, `unknown` or `blocked`. Measurements follow
the [evaluation-design](../evaluation-design/README.md) method.

## How to use it

Write usage exports or invoices as nouns, write the nouns in [nouns.json](nouns.json)
create-only, then fill `inventory-costs` from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate` and enqueue it yourself.

## Limits

- No verb changes a plan, setting, resource or model choice, and no verb opens a
  billing dashboard. `adoption_authorized` is always false.
- Prices behind a login are out of scope; they stay unknown.
- The repository review pack's cost questions find candidates in code; this pack is
  for deeper, measured follow-up.
