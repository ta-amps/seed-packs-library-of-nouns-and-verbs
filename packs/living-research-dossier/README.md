# Living research dossier

## What this pack lets workers do

A collection of nouns and verbs for keeping a research dossier current on a topic people keep relying
on, such as a policy brief or a funding landscape. A one-off report goes stale quietly: a deadline
passes, a rule is revised, a figure is updated, and nobody can tell which sentences still hold.
Workers keep a numbered queue of open questions and work it in cycles, with at most one sub-agent per
question in each cycle. They fold sourced answers into the next dossier version and append a cycle
log. Every fact carries an as-of date, a decay class and the refresh date that follows. Once no
question is open, the dossier switches to watching named triggers; a fired trigger reopens
questions, and facts past their refresh date are read again. A person decides which version is
published.

It builds on the [deep research report pack](../deep-research-report/README.md): its research
question shape, source log, claim extract, permitted-access, screening and evidence-strength rules,
guardrails, checklist and adversarial review are pinned, not redefined. The person's decision is the
[policy and law watch pack](../policy-and-law-watch/README.md)'s delivery record.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | One sub-agent per question per cycle; an as-of date and decay class on every fact; nothing overwritten; plus five pinned from the deep research and policy watch packs |
| Question queue rules | Numbers never reused, six statuses, parking with a reason, raised questions appended |
| Cycle rules | Plan, answer, fold in and log; three questions a cycle by default; one sub-agent each |
| Decay classes | Stable, slow, periodic, fast and volatile, from 365 days to 7, and what makes a fact due |
| Trigger rules | Named triggers on public sources, cheap checks, fired versus changed, unreachable sources |
| Templates | Dossier, cycle plan, answer, cycle log, trigger check and refresh record |
| Dossier checks | 13 deterministic checks with 2 made-up good and 13 made-up bad dossiers, rechecked by `make check` |
| Checklist and sources | What a person checks before publishing; 3 dated public sources |
| Worked examples | A cycle plan, an answer, a cycle log, a trigger check, a refresh record and the dossier they produce |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `open-dossier` | agent | A first version with a numbered question queue |
| `plan-cycle` | agent | Picks open questions and proposes one answer-question verb for each |
| `answer-question` | agent, the one sub-agent | Sourced, dated facts with a source log and a claim extract |
| `fold-in` | agent | The next version by compare-and-set: facts added or superseded, questions reopened |
| `log-cycle` | agent, no model | The appended log of what changed and which sub-agent worked what |
| `switch-to-watching` | agent | Named triggers once the queue has run out |
| `check-triggers` | agent, no model | Each trigger checked cheaply; fired ones reopen questions |
| `refresh-decayed-facts` | agent | Facts past their refresh date read again from their sources |
| `review-dossier` | a different agent or a person | Quotes rechecked, overreach listed, missed counter searches |
| `decide-publication` | person | Delivers or holds one exact version |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Verbs for a person are claimed by people, never by an agent.

## Worked examples

All made-up: a dossier on cold-storage grants for small food banks in a made-up state. Two cycles
answer three questions and park one, and the dossier switches to watching three triggers. A closing
date in the volatile class is read again on 2026-10-26 and refreshes by 2026-11-02. A changed
guidelines page fires a trigger that reopens two questions, and a third cycle supersedes the award
range of 5,000 to 25,000 with 5,000 to 40,000 while keeping the old fact. Each bad dossier breaks one
rule, such as watching while a question is open or a fact with no source.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface,
then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- No scheduler is activated. Cycles, trigger checks and refreshes happen only when an authorized
  requester enqueues them; a suggested cadence is a note, not a schedule.
- The decay classes are starting points, not measured half-lives; a trigger misses any change it
  does not watch, so refresh dates stay the backstop.
- The dossier checks catch missing dates, sources, logs and reasons, not a wrong fact; the review
  and the person's decision still matter.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
