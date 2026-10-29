# Decomposition patterns

## What this pack lets workers do

Decide how to split work into verbs using shapes that have worked before, try two or
three different breakdowns as separate attempts, and keep the shape that led to better
results downstream. Every pattern has its own success record, so the library learns
which shapes work for which kinds of tasks.

## Nouns

| Noun | What it holds |
| --- | --- |
| 9 patterns | Do it in one verb; probe then build; split by part then combine; separate attempts then compare; draft, check, review; reproduce then repair; baseline then variant; scan then consolidate; pause for a person |
| 9 success records | One per pattern, starting empty with null counts so rankings show "unranked" instead of a made-up score |
| Templates | Breakdown, attempt plan, comparison, success entry and success record |

Each pattern says when to use it, when not to, its stages and their order, stop rules,
known failure modes and examples elsewhere in this library.

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| propose-breakdown | Picks a pattern and proposes child verbs; run once per alternative (a, b, c) | Breakdown |
| materialize-attempt | Lowers one breakdown into child task previews; enqueues nothing | Attempt plan |
| compare-breakdowns | Compares attempts by what their children actually achieved | Comparison |
| record-outcome | Adds the result to the pattern's success record by compare-and-set | New record version |

Each verb can also end with `no_change`, `unknown` or `blocked`. The first rule is to
prefer one verb: split only when parts have independent outcomes, permissions or recovery.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only, write a goal noun, fill
`propose-breakdown` from [verbs.json](verbs.json) once per alternative with
`scripts/build_packs.py --instantiate`, and enqueue them yourself. You, not a verb,
enqueue the children an attempt plan describes.

## Limits

- No pattern has a recorded use yet; the records are empty on purpose.
- Children share one budget. No verb here enqueues anything.
- `record-outcome` is the one verb that updates an existing noun, through
  compare-and-set against the pinned version.
