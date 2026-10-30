# Regression watch

## What this pack lets workers do

A collection of nouns and verbs for watching for regressions against baselines a person accepted.
Baselines are nouns: page screenshots by hash, metrics with tolerances, API response shapes, check
results and video QA numbers. Every change is measured again under the same settings and compared by
fixed rules, and every mismatch is measured twice more before anything is reported, so a flaky
check is told apart from a real regression. Regressions become findings, flaky checks become
findings against the check, and every new baseline, even an improvement, waits for a person.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle, the rules and when to measure, including after a release |
| Guardrails | Compare like with like; rerun before reporting; only a person moves a baseline; not run is never a pass; measure the exact bytes |
| Baseline kinds | Screenshot, metric, API shape, video QA numbers and check result (failures counted, never passes) |
| Compare rules | Six outcomes and the rule for each kind, from digests and tolerances to shape changes |
| Flake rules | Two reruns by default, the verdicts, and what happens to a check that keeps flaking |
| Watch checks | 16 checks on a comparison, with 2 good and 16 bad comparisons the validator recomputes |
| Templates | Baseline set, measurement, comparison, a person's acceptance and a flake review |
| Test cases | 6 synthetic cases |
| Worked examples | A baseline set, a measurement, a comparison with every outcome, an acceptance, the next set and two findings |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `capture-baseline` | agent | A candidate set under named settings, never marked accepted |
| `accept-baseline` | person | Item by item, which values become the baseline and which tolerances change |
| `apply-acceptance` | agent, no model | The person's decision written as the next set, nothing else; the old set kept |
| `remeasure` | agent | The change measured under exactly the baseline's settings |
| `compare-to-baseline` | agent, no model | The rules, two reruns of every mismatch, and an outcome per item |
| `report-regressions` | agent | Findings for regressions and flaky checks, and proposals for a person |
| `review-flaky-checks` | agent, no model | Which checks keep flaking, and what to do about each |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Video numbers come from the [video QA](../video-qa/README.md) pack's report on
the exact bytes; after a release, the [release and verify](../release-and-verify/README.md) pack's
parity and smoke checks read the live version and this pack compares their results; screenshots use
the [screenshot design review](../screenshot-design-review/README.md) matrix. Findings go through
[findings to fixes](../findings-to-fixes/README.md), and a check that keeps flaking goes to
[checks of checks](../checks-of-checks/README.md).

## Worked examples

All synthetic: a pantry site, its shifts API and its 45-second explainer. Against an accepted set of
ten items, one change gives four matches; a removed `ends_at` field and a lost caption cue that both
reruns confirm; a lab LCP of 2480 ms against 2100 ms that reads 2150 and 2090 ms on reruns, so the
check is flaky; an intended screenshot change and a smaller bundle for a person; and a true peak that
was not measured. The person accepts the two changes, widens the flaky check's tolerance, keeps the
old values for the regressions, and the next set is written exactly from that decision.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The examples are synthetic; the library's tests recompute their outcomes and counts only.
- Two reruns catch noise, not every intermittent fault; a flaky check still needs its own fix.
- Tolerances are a person's call; the defaults here are starting points, not standards.
- An exact screenshot digest is strict by design: fonts, masks and settings must be pinned to use it.
