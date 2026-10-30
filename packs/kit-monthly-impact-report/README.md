# Monthly program impact report kit

## What this pack lets workers do

A collection of nouns and verbs for a community nonprofit's monthly program impact report: a month of program records totaled by measure and compared with targets and last month, missing numbers kept as unknown, and a report draft that traces every figure, while the program manager checks figures and the executive director approves and shares the report.

Turn a month of program records, such as sessions held, people served and outcome check-ins, into a results table that compares each measure with its target and with last month, and draft the monthly impact report with every figure traced to that table. The program manager checks every figure, and the executive director approves the report and shares it.

## Nouns

| Noun | What it holds |
| --- | --- |
| Kit | The agent's whole setup as one noun: the step map and pins to every part below |
| Skill `impact-report-drafter` | Drafts a monthly impact report from a results table, keeping every number traced to a measure and every gap visible. |
| Read-only tool card `summarize_month_by_measure` | Totals a month's program records by measure and compares each with its target and with last month, listing missing counts as unknown. |
| File: Monthly Results Table | One row per measure for the month: target, count, percent of target, last month, change and the record it came from. No participant details. |
| File: Monthly Impact Report Outline | Five-section outline for the monthly report, with every number drawn from the results table. |
| Checklist | 4 checks a person runs with the kit |
| Sources | 2 dated public sources |
| Test cases | 3 synthetic cases; 2 must go to a person |
| Example request | What an organization might type when it asks for this kit, marked synthetic |
| Templates | a month's program results by measure, a monthly impact report draft with every number traced, and a person's step record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `total-month` | agent, no model | Total the month's program records by measure |
| `draft-impact-report` | agent | Draft the monthly impact report |
| `check-figures` | person | Check every figure against the program records |
| `approve-report` | person | Approve the report and how shortfalls are explained |
| `share-report` | person | Share the report with the board and partners |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

The marketplace example `examples/kits/06-monthly-program-impact-report.json` points at this pack's kit and example request
nouns by their value digests, so the kit has one source.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The test cases are synthetic. Passing them shows the kit's shape, not that it helps a real organization.
- The tool cards describe read-only tools; this pack ships no tool code.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
