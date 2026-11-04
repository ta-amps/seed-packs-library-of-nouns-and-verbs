# Findings to fixes

## What this pack lets workers do

A collection of nouns and verbs for turning every noticed error, issue, design flaw or
annoyance into recorded, fixed and verified work. Whoever notices a problem records it at
once as a finding with evidence, even if it will be fixed a minute later. Workers then
reproduce it, merge duplicates, fix it, have a different worker verify the fix, add a guard
that is shown to fail without the fix, close it through a gate and, when the disclosure
rules allow it, prepare a public summary for the owner. Failures stay on the record:
nothing is deleted, and every later step writes a new version or a new noun.

A worker that notices a problem during any other verb, in any pack, returns a proposed
`record-finding` verb with its evidence, and an authorized requester enqueues it. Workers
create nouns and propose verbs; they never enqueue.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle, what each status means, the close gate and the rules: record first, failures stay, a fixer never verifies their own fix |
| Kind definitions | Error, issue, design flaw and annoyance, how to tell them apart, where each goes, and the fingerprint rule for duplicates |
| Severity guide | P0 to P3, what each means and how fast to respond, with the security review pack's levels mapped onto them |
| Evidence checklist | A minimal reproduction for an error, screenshots at named widths and themes for a visual design flaw, the person's words for an annoyance |
| Disclosure rules | Never publish details of an unfixed security finding; fixed and non-sensitive findings may be published once the owner agrees |
| Record checks | 20 deterministic checks with 11 known-good findings (8 real, 3 made-up) and 20 made-up known-bad ones, rechecked by `make check` |
| Templates | Finding, reproduction, fix proposal, fix, verification, regression guard, public summary and pattern review |
| Worked examples | Eight real public findings from October 29, 2026, and a pattern review written by hand from them |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| record-finding | agent or person | Writes the finding with evidence, a provisional kind and severity, and a fingerprint |
| reproduce | agent | Shows it again at the exact version, smallest first; security findings go to the security review pack |
| triage | agent | Merges duplicates by fingerprint, then sets kind, severity and sensitivity; reruns link later nouns |
| propose-fix | agent | Names the cause and one to three options, each marked repair or build and with its guard; a taste call gets a palette brief |
| fix | agent | Makes the chosen option in a local copy, with a test that fails first; never pushed |
| verify-fix | a different agent | Reruns the reproduction on the unfixed and fixed versions, where the problem was seen |
| add-regression-guard | agent | Proves a guard fails without the fix and passes with it, by the checks of checks trust rule |
| close | agent | Applies the close gate and writes the closing version; deterministic |
| publish-finding | agent | Prepares a public summary only when the disclosure rules allow it; the owner releases it |
| review-patterns | agent | Periodically finds causes that keep coming back and proposes one upstream fix for each |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up
verbs instead of enqueueing them. A taste call goes through [taste palettes](../taste-palettes/README.md),
a guard through [checks of checks](../checks-of-checks/README.md), a security finding through
[security review](../security-review/README.md), a documentation finding through
[docs improvement](../docs-improvement/README.md) and a large fix through
[decomposition patterns](../decomposition-patterns/README.md). A fix that would build something
new, such as a shared tool or check, first goes through `survey-existing` and
`research-alternatives` in [prior art and alternatives](../prior-art-and-alternatives/README.md);
a repair that restores something to its own tested contract does not.

## Worked examples

Real public findings, copied from a findings ledger kept on October 29, 2026, with product
and repository names written generically. Agent A and agent B are two different coding agents.

| Finding | Kind and severity | Status | What it shows |
| --- | --- | --- | --- |
| F-001 | error, P2 | fixed | A regression test recorded as failing without the fix (Tessera PR #14, merge 7e7433c) |
| F-002 | error, P1 | fixed | An independent reproduction; its 43-case test is not yet shown to fail without the fix (the video pack's code repo PR #6, merge 78bd722) |
| F-003 | error, P1 | open | A fix blocked because no replacement limit is authorized; no score exists |
| F-004 | issue, P2 | fixed | A process mistake, a merge against the owner's hold, reverted (archive PR #7, merge ef710fc) |
| F-006 | design flaw, P3 | open | One generator copied into every repository, with a workaround |
| F-009 | design flaw, P3 | fixed | A layout fix checked with light and dark screenshots, with no guard yet |
| F-011 | annoyance, P2 | in progress | The owner's annoyance at retired names, guarded in some places |
| F-014 | issue, P3 | open | Found by a daily check, with a repair verb queued |

The pattern review groups F-004 with F-005, F-006 across every copy and F-011 with F-019,
and proposes one upstream fix for each. Who made each fix is not in the record, so the
examples leave `distinct_from_fixer` unknown and none of them could close yet.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface. Run
`review-patterns` weekly or after every ten closed findings; this pack activates no schedule.

## Limits

- No worker has run these verbs. The examples show the shapes with real facts; they are not results.
- The record checks catch missing and inconsistent fields, not wrong judgments; a reviewer still reads each finding.
- Fingerprints and sensitivity in the examples were filled in by this pack's rules, not copied from the ledger.
- Publishing, landing fixes and deploying them stay the owner's acts; no verb here does any of them.
