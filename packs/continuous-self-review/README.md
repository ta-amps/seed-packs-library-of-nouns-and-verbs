# Continuous self-review

## What this pack lets workers do

A collection of nouns and verbs for reviewing a repository, site or video on a rotation, run after
run. Workers cut the target into scopes and give each the checks it needs from other packs. A review
schedule stays a proposal until a person approves it with an expiry. Each window, a fixed rule picks
the scopes reviewed least recently or changed most; their checks run as their own verbs; and each
run's findings are diffed against the last run of the same scope, so new, still open, fixed,
unverified, unexplained, unchecked and reopened findings are told apart and each gets its next verb.
A different worker verifies every fix, a review log shows coverage over time, and any worker reviews
its own change before handing it on.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The loop from scopes to coverage, and its rules |
| Guardrails | A schedule is a proposal until approved; gone is not fixed; compare like with like; not run is never a pass |
| Rotation rule | Never reviewed first, then urgent scopes past twice their interval, then staleness plus churn plus open high-severity findings |
| Diff rules | Seven classes by fingerprint, the verb each one proposes, and findings a person decided left alone |
| Scope kinds and self-review rules | Repository paths, pages, video segments and docs pages with their checks; self-review steps |
| Loop checks | 16 checks on a review run, with 2 good and 16 bad runs the validator recomputes |
| Templates | Scope catalog, schedule proposal, scope pick, review run, review log, self-review and coverage review |
| Test cases | 6 synthetic cases |
| Worked examples | A catalog, a schedule and its approval, a pick, a diffed run, the log, a self-review and a coverage review |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `map-scopes` | agent | Scopes with their checks, intervals and churn, and a schedule proposal |
| `approve-schedule` | person | Approved, approved with changes or declined, with an allowance and an expiry |
| `pick-scope` | agent, no model | The rotation rule's ranks, the window's scopes and their checks proposed |
| `diff-against-last-run` | agent, no model | Every finding sorted against the last run, each with its next verb |
| `log-run` | agent, no model | The run appended to the log by compare-and-set, coverage recomputed |
| `review-own-change` | agent or person | A self-review of one's own change, then a hand-off to someone else |
| `review-coverage` | agent | Scopes left out, checks that never fail or run, causes that come back |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. The approval reuses the [unattended run record](../unattended-run-record/README.md)
pack's run approval. Checks come from packs such as [codebase health review](../codebase-health-review/README.md),
[edge and corner cases](../edge-and-corner-cases/README.md), [annoyance hunt](../annoyance-hunt/README.md),
[video QA](../video-qa/README.md) and [wiring and conformance checks](../wiring-and-conformance-checks/README.md);
fixes and verification go through [findings to fixes](../findings-to-fixes/README.md), and measured
numbers against a baseline through [regression watch](../regression-watch/README.md).

## Worked examples

All synthetic: a pantry's repository, site and 45-second explainer, cut into eight scopes and
reviewed weekly on Fridays under a person's approval that expires on 2026-12-31; earlier runs were
manual. As of 2026-10-30 the rule picks the sign-up page, never reviewed; the API folder, which changed
by 420 lines; and the docs, 58 days since their last review. The API run has one finding in each
class, from a fix verified by another worker to one reopened after it was closed, and leaves alone a
finding a person closed as won't fix. After the window the log shows seven of eight scopes within
their intervals; the forms folder is overdue, 21 days out on a 14-day interval. The coverage review
proposes testing a link check that never fails.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- No scheduler is activated: windows run only when an authorized requester enqueues pick-scope, under
  a person's approval, until Tessera's flag-gated schedule support exists.
- The examples are synthetic; the library's tests recompute the pick, the diff and the coverage only.
- A rotation reviews what the catalog lists; a scope nobody listed is never picked.
