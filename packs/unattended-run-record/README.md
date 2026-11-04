# Unattended run record

## What this pack lets workers do

A collection of nouns and verbs for running work unattended, overnight or on a schedule, and
leaving a record anyone can check in the morning. When nobody is watching, the usual failures
are quiet ones: a run invents work because it cannot decline, a question waits for an answer
that never comes, an attempt edits its own check and reports green, a weaker fallback is used
without a word, and an empty night is written up as progress. Workers plan the window, get a
person's approval, decline work that has no check before any model runs, give every candidate
its own copy and a hashed baseline, let the check grade each attempt on an outcome ladder, and
write a plain-language report that keeps every failure.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The night in order, from intake and triage to delivery on branches and the morning report |
| Run guards | Lock, stop file, machine probes, approval, allowances from the remaining budget, retention |
| Outcome ladder | Thirteen rungs from already green to void, each with who establishes it |
| Fallback ladder | Every layer degrades to a named, recorded result; containment is refused, never downgraded |
| Verification strength | Eight rungs of checking beyond the task's own check, recorded separately |
| Run checks | 11 deterministic checks with 2 made-up good and 11 made-up bad reports, rechecked by `make check` |
| Templates | Run plan, run approval, candidate, triage record, baseline, attempt record, grade and run report |
| Worked examples | A seven-hour overnight plan and a triage that declines three candidates without a model call |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| plan-run | agent | Writes the window, allowance, guards, candidate sources and delivery |
| approve-run | person | Approves, changes or declines the plan, with an expiry |
| triage-candidates | agent, deterministic | Declines what has no check, a risky check or a passing check, then ranks the rest |
| take-baseline | agent, deterministic | Makes the candidate's copy, runs every check first and hashes the check folder and environment |
| attempt-candidate | agent | Works the candidate in its copy under the step contract and commits on its branch only |
| grade-attempt | agent, deterministic | Reruns the checks, rehashes and places the attempt on the ladder |
| write-run-report | agent | Writes counts first, evidence per candidate, declines, fallbacks and next steps |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs
instead of enqueueing them. Steps follow the [atomic step contract](../atomic-step-contract/README.md);
shortfalls become handoffs in [status and handoff](../status-and-handoff/README.md), and defects go to
[findings to fixes](../findings-to-fixes/README.md).

## Worked examples

All made-up. The good night report leads with "1 verified, 1 cause localised, 1 void, 1 already
green; 2 declined": one attempt changed its own check and was voided but kept as a branch, an
unreported counter is left empty with the reason, and each shortfall has a next step. The empty
night says nothing unresolved was found. Each bad report breaks one rule, such as a headline
claiming everything was fixed or a summary made of raw machine output.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Approve each plan before its first window.

## Limits

- These are proposals. Nothing here is installed, imported, scheduled or activated, and no worker has run these verbs.
- No scheduler is part of this pack; recurring windows need the fabric's own schedule support and a person's approval.
- The run checks catch missing fields and contradictions, not a wrong rung; grading still needs the runner's own check runs.
- A strong check is the ceiling on what an unattended run can prove; work without one is declined, not attempted.
