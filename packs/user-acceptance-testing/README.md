# User acceptance testing

## What this pack lets workers do

A collection of nouns and verbs for user acceptance testing that ends in a person's decision.
Workers write synthetic personas and acceptance criteria before anyone tests, and a person agrees
to one exact version of the criteria. Workers then turn the criteria into scenario scripts, run
each script on a named build and record what they observed as it happened, with evidence for every
failure. Every failed or blocked step becomes a proposed finding. A deterministic worker derives
each criterion's verdict and a recommendation by fixed rules, and the accountable person records
go, no-go or go with conditions as a noun. An agent never signs off.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle, the rules and the roles: criteria first, results as observed, a person signs off |
| Persona guide | What a persona holds and how to keep it goal-based, accessible and synthetic |
| Criteria guide | Given, when and then; must, should and could; accessibility criteria citing WCAG; time thresholds |
| Test-data rules | Reserved example domains and fictional numbers, never real people's data |
| Defect rules | How a failed step becomes a finding: kind, provisional severity and the evidence to attach |
| Verdict rules | Met, not met or not tested for each criterion, and a recommendation that is advice only |
| Sign-off checks | 14 deterministic checks with 3 synthetic good and 14 synthetic bad sign-offs, rechecked by `make check` |
| Templates | Persona, acceptance criteria, criteria agreement, scenario script, session record, results summary and sign-off |
| Worked examples | A keyboard-only persona, criteria, a script, a session with a failure, a summary and a no-go |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| draft-personas | agent | Writes two to five synthetic personas with goals, access needs and what success means |
| write-acceptance-criteria | agent | Writes testable criteria before any testing, citing WCAG for accessibility ones |
| agree-criteria | person | Agrees to an exact criteria version, or changes it with reasons |
| write-scenario-scripts | agent | Numbered steps with expected observations, covering every must criterion |
| run-scenario | agent or person | Follows one script on one build and records each result as it happens |
| compile-results | agent, no model | Derives verdicts and a recommendation by the verdict rules |
| sign-off | person | Records go, no_go or go_with_conditions, with reasons and accepted risks |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Defects go to [findings to fixes](../findings-to-fixes/README.md), accessibility
criteria cite the [accessibility audit](../accessibility-audit/README.md) checklist, and a sign-off is
evidence for [launch readiness](../launch-readiness/README.md).

## Worked examples

All synthetic, on a made-up pantry volunteer site. A keyboard-only volunteer persona leads to four
criteria, one of them citing 2.1.1 and 2.4.7. The scenario script marks the step that books a shift
as needing a test target, so the session records it as not run. The session fails step 1 because
the shift buttons show no focus indicator, with a screenshot digest and region, and proposes
finding UAT-F-2. The summary marks AC-3 not met and recommends no-go; the program manager records the
no-go with a next step.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- Personas are assumptions, not research; they need real evidence to confirm or replace them.
- The sign-off checks catch missing and inconsistent fields, not a wrong decision; the decision is the person's.
- Signing off records a decision only. Releasing stays a separate act by a person.
