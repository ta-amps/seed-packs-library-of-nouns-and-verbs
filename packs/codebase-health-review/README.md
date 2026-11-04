# Codebase health review

## What this pack lets workers do

A collection of nouns and verbs for a periodic review of a codebase's health at one commit, area by
area. Workers age TODO and FIXME comments by the date git blame gives their lines, find exception
handlers that swallow errors, check dependency drift and unpinned versions, measure oversized
modules, duplicated code and log noise, find untested error paths and flaky tests in a sandbox, and
scan for possible secrets by place and pattern only. A report gives every area its own status and
never one score, and every item that needs action becomes a finding with its file and line, its
measurement, a fix and a regression guard. Tested code does the aging and the exception finding.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle, the rules and a suggested cadence that schedules nothing |
| Guardrails | Report where a secret is, never what; ages from history; no single score; not run is never ok; a canary per rule |
| Health areas | Eleven areas, each with its signal, measurement, watch and act thresholds, kind, severity and route |
| Rules | Marker aging, swallowed-exception classes and secret patterns reported by place only |
| Tool card | The TODO ager and the swallowed-exception finder in [code/](code/README.md), pinned by digest |
| Health checks | 9 checks on a finding, with 3 good and 9 bad findings the validator recomputes |
| Templates | Health plan, area result and health report |
| Sources and test cases | 5 dated public sources; 6 made-up cases |
| Worked examples | A made-up repository's dated history, its plan, two scans the code computes, a report and a finding |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `plan-health-review` | agent | The commit, the as-of date, each area's thresholds and what other packs cover |
| `age-todos` | agent, no model | Markers in comments, aged by git blame or unknown with the reason |
| `find-swallowed-exceptions` | agent, no model | Handlers that swallow errors, by file, line and class |
| `check-dependencies` | agent | Drift, end of life, unpinned ranges, moving tags and unpinned CI actions |
| `measure-code-structure` | agent, no model | Lines per file and function, repeated blocks and log noise |
| `review-tests-and-errors` | agent | Untested error paths by coverage and flaky tests by reruns, in a sandbox |
| `scan-secret-patterns` | agent, no model | Possible secrets by file, line and pattern name, never their values |
| `write-health-report` | agent | Each area's status, areas not run, a fair trend, and a finding per act item |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. The [wiring and conformance checks](../wiring-and-conformance-checks/README.md)
pack owns unused modules, mock-only tests and hollow probes, so this pack links its report instead of
measuring them again. Secrets go to [security review](../security-review/README.md), deprecations
to [freshness checks](../freshness-checks/README.md), documentation examples to
[docs improvement](../docs-improvement/README.md), and every finding through
[findings to fixes](../findings-to-fixes/README.md).

## Worked examples

All made-up: a small roster repository built in four commits dated from 2024-06-03 to 2026-10-26.
As of 2026-10-30 the ager finds 6 markers: 2 ancient, 1 aging and 3 fresh, while a TODO
inside a string is not one. The finder lists 2 swallowed handlers, a broad suppress, a logged-only
and a fallback handler and a narrow ignore, and leaves a re-raise alone. The code's tests rebuild
the repository at the same dates and recompute both scans exactly.

## How to use it

Run `make check` in [code/](code/README.md). Write the nouns in [nouns.json](nouns.json) create-only
with a key scoped to your team's surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- Thresholds are starting points from small codebases, not standards; the plan says which applied.
- The ager reads comments by syntax, not meaning; the finder reads Python only, and a listed handler
  is a lead a reviewer reads, not proof of a bug.
- Coverage, flakiness, drift and secrets are measured by the worker's own tools; this pack's code
  covers only the ages and the handlers.
