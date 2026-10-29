# Decomposition patterns

## What this pack lets workers do

A collection of nouns and verbs for breaking work into verbs with reusable patterns.
Workers propose a breakdown from common shapes, try two or three different breakdowns
as separate attempts, and keep the shape that led to better results downstream. This is
where verbs most clearly create verbs: a breakdown becomes child task previews that a
requester enqueues. Every pattern has a success record, so the library learns which
shapes work for which tasks.

## Nouns

| Noun | What it holds |
| --- | --- |
| 9 patterns | Do it in one verb; probe then build; split by part then combine; separate attempts then compare; draft, check, review; reproduce then repair; baseline then variant; scan then consolidate; pause for a person |
| 9 success records | One per pattern, starting empty with null counts so rankings show unranked instead of a made-up score |
| Templates | Breakdown, attempt plan, comparison, success entry and success record |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| propose-breakdown | Picks a pattern and proposes child verbs; once per alternative (a, b, c) | Breakdown |
| materialize-attempt | Lowers one breakdown into child task previews; enqueues nothing | Attempt plan |
| compare-breakdowns | Compares attempts by what their children actually achieved | Comparison |
| record-outcome | Adds the result to the pattern's success record by compare-and-set | New record version |

Each verb can also end with `no_change`, `unknown` or `blocked`. The first rule is to
prefer one verb: split only when parts have independent outcomes, permissions or recovery.

## How to use it

Write a goal noun. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface. You, not a verb, enqueue the children an
attempt plan describes.

## Limits

- No pattern has a recorded use yet; the records are empty on purpose.
- Children share one budget. No verb here enqueues anything.
