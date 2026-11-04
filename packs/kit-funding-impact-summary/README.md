# Funding impact summary kit

## What this pack lets workers do

A collection of nouns and verbs for a funding impact summary in a grant renewal: the grant period's results compared with the original targets, spending by budget line taken word for word from the finance lead's figures, missing numbers kept as unknown, and a traceable summary draft, while the finance lead checks the figures and the executive director approves and submits.

Compare a whole grant period's program results with the targets in the original agreement, take spending by budget line only from the finance lead's figures, and draft the renewal application's impact summary with every number traced to its source. The finance lead checks every figure, and the executive director approves the summary and submits the renewal.

## Nouns

| Noun | What it holds |
| --- | --- |
| Kit | The agent's whole setup as one noun: the step map and pins to every part below |
| Skill `impact-summary-drafter` | Drafts a grant renewal's funding impact summary from a period results table, keeping every number traceable and every gap visible. |
| Read-only tool card `compare_period_to_targets` | Totals each measure across a grant's reporting periods, compares it with the original target, and lists missing numbers as unknown. |
| File: Grant Period Results Table | One row per measure for the whole grant period, with its target, total and percent of target, plus spending by budget line from the finance lead. No participant details. |
| File: Funding Impact Summary Outline | Five-section outline for a renewal's impact summary, with every number from the period table. |
| Checklist | 4 checks a person runs with the kit |
| Sources | 2 dated public sources |
| Test cases | 2 made-up cases; 1 must go to a person |
| Need, in its own words | One or two plain sentences an organization might say about this work, marked made-up |
| Templates | a grant period's results and spending against its targets, a funding impact summary draft with every number traced, and a person's step record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `compare-period-to-targets` | agent, no model | Compare the grant period's results with the original targets |
| `draft-impact-summary` | agent | Draft the funding impact summary for the renewal |
| `check-figures` | person | Check every figure against the books and program records |
| `approve-summary` | person | Approve the summary and how shortfalls are explained |
| `submit-renewal` | person | Submit the renewal application to the funder |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

The marketplace example `examples/kits/10-funding-impact-summary.json` points at this pack's kit and need nouns by
their value digests, so the kit has one source.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The test cases are made-up. Passing them shows the kit's shape, not that it helps a real organization.
- The tool cards describe read-only tools; this pack ships no tool code.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
