# Launch readiness

## What this pack lets workers do

A collection of nouns and verbs for deciding whether a site or app is ready to launch. Workers plan
the check for one launch, resolve every link on the rendered pages, match every status claim on the
pages against a live read-only check or a receipt, compare the site's analytics statement with the
requests its pages actually make, check that missing pages answer 404, and review the rollback plan.
A deterministic worker assembles one report whose recommendation follows a fixed rule, and the
owner records go, no-go or go with waivers. The release itself stays with a person, recorded with
the release and verify pack.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle, the recommendation rule and who may waive an item |
| Readiness checklist | Seven required items and two optional ones, each with its evidence and pass rule |
| Claim rules | Counts, states, versions, capabilities and absences, and how each is checked |
| Analytics hosts | A starting list of analytics hosts and how to tell them from fonts and other third parties |
| Error page rules | 404 for missing pages, no soft 404s, a way home and nothing leaked |
| Go checks | 18 deterministic checks with 3 synthetic good and 18 synthetic bad reports, rechecked by `make check` |
| Templates | Readiness plan, page claims, analytics check, error page check, rollback review, readiness report and go decision |
| Worked examples | A plan, a claims check with a contradicted count, a not-ready report and the owner's no-go |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| plan-readiness | agent | Names the pages, claims, checklist items, rollback target and the people who release and decide |
| check-live-links | agent, no model | Resolves every rendered link and anchor in the link check shape |
| check-page-claims | agent | Quotes every status claim and checks it against a live read or a receipt |
| check-analytics | agent, no model | Lists every request host and compares it with the analytics statement |
| check-error-pages | agent, no model | Made-up addresses: status, view, link home, leaks |
| review-rollback | agent | Target version, steps, who and how long |
| assemble-readiness | agent, no model | One report with blockers, waivers and a derived recommendation |
| record-go-decision | person | Go, no_go or go_with_waivers on the exact report; releasing stays separate |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Links reuse [rename and relink](../rename-and-relink/README.md), claims reuse
[status and handoff](../status-and-handoff/README.md) evidence rules, and the release itself goes
through [release and verify](../release-and-verify/README.md).

## Worked examples

All synthetic. A small volunteer site's home page says 40 volunteers this month while the roster
shows 38, and unknown addresses answer 200 with a not-found view. The report lists both as blockers
and recommends not ready; the program manager records a no-go with a next step. The go checks also
hold a ready-with-waiver report where the owner waived the soft 404 with a reason.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- The analytics host list is a starting point, not complete; unknown hosts go to a person.
- The go checks catch missing and inconsistent fields, not a wrong claim check; the report is only as good as what was read.
- No verb releases, switches versions or waives an item; those stay with people.
