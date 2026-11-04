# Checked data analysis

## What this pack lets workers do

A collection of nouns and verbs for analyzing a CSV file with a check at every step. Workers pin the
file by the digest of its bytes and profile its schema, validate every cell against the declared
types and ranges, flag missing values and outliers without removing any, compute summaries and
comparisons with recorded queries whose results carry digests, keep charts as Vega-Lite data specs
rather than images, and write findings in which every number traces to a query result. A different
worker reruns every query, and a person decides what the findings mean. Privacy and the person's
decision use the guardrails of the [policy and law watch pack](../policy-and-law-watch/README.md).

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | New: every number traces to a recorded query; flag problems, never drop or fix them silently. Pinned: no personal data; a person decides |
| Reading, type and validation rules | RFC 4180 reading, row numbering, identifying columns hidden, type inference and every declared rule |
| Outlier, query and chart rules | Tukey's fences with stated quartiles, the query language with counted exclusions and digests, and Vega-Lite specs drawn from one query |
| Tool card | The pack's tested code in [code/](code/README.md), pinned by digest |
| Templates | Analysis request, schema profile, validation report, flag report, query results, chart specs, findings, findings check, interpretation |
| Findings checks | Eleven checks on findings, with one good and eleven bad sets the validator recomputes |
| Checklist, sources, test cases | What a person checks before relying on findings; 8 dated public sources; 10 made-up cases |
| Worked example | Made-up: a 25-row weekly meals log for three fictional sites, from file to the person's reading |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `profile-schema` | agent, no model | The file pinned by digest and profiled, identifying values hidden |
| `validate-types-and-ranges` | agent, no model | Every violation listed with its row, column and rule |
| `flag-missing-and-outliers` | agent, no model | Missing values and outliers flagged; every row kept |
| `compute-summaries` | agent | Recorded queries, every exclusion a counted filter, results with digests |
| `make-chart-specs` | agent | Vega-Lite specs from query results, never images |
| `write-findings` | agent | Plain findings, every number traced, no causes or cleaning |
| `check-findings` | a different agent or a person | Every query rerun and every digest and number compared |
| `decide-meaning` | person | What the findings mean, in the person's own words |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose follow-up verbs.
Verbs for a person are claimed by people, never by an agent.

## Worked example

All made-up. The log has a site written in lower case, a volunteer count written in words, a date
that does not exist, a missing meals count, a meals count of 9999, a negative weight, a valid week far
above the others, a repeated row and a column of contact addresses that never leaves the file. The
profile, validation and flags list every one, six queries leave rows out only through named filters,
two charts draw their query results, and five findings trace all 25 of their numbers.

## How to use it

Run `make check` in [code/](code/README.md) to recompute the worked example. Write an analysis request
shaped like `template.analysis-request`, write the nouns in [nouns.json](nouns.json) create-only with a
key scoped to your team's surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The worked example is made-up; its sites, people and numbers are made up, and every address ends
  in example.invalid. The code's tests recompute every step of it.
- The query language is small on purpose: filters, groups and seven aggregates. Anything larger is a
  new verb with its own checks.
- Findings describe the data; why anything changed is the person's call, not the analysis's.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
