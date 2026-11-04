# Exploratory testing charters

## What this pack lets workers do

A collection of nouns and verbs for exploratory testing in time-boxed sessions, after session-based
test management. Workers draft charters with one mission each, in the form explore a target, with
resources, to discover information, aimed at risks such as open findings or failed acceptance
steps. One charter is explored per session inside its time box, with notes taken as it happens.
Every bug gets steps and evidence and becomes a proposed finding; every open question becomes an
issue. A different worker or a person debriefs each session, and coverage notes say what has and
has not been explored, with a proposed charter for every gap. Exploring is never called complete.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle, the rules and the five debrief questions: past, results, obstacles, outlook, feelings |
| Charter guide | The charter form, sizing, risks, resources and time boxes of 45, 90 and 120 minutes |
| Test ideas | Product elements, quality criteria and six tours, such as keyboard-only and slow-network |
| Session rules | Time box, timestamped notes, time split, bugs, issues, coverage and data |
| Coverage model | Areas by quality criteria, with explored, partly, not explored and out of scope |
| Session checks | 14 deterministic checks with 2 made-up good and 14 made-up bad session notes, rechecked by `make check` |
| Templates | Charter, session notes, debrief and coverage notes |
| Worked examples | A charter, its session notes with a bug and a question, the debrief and coverage after three sessions |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| draft-charters | agent | One to eight charters aimed at named risks, ranked |
| run-session | agent or person | Explores one charter in its time box and keeps notes as it happens |
| debrief-session | a different agent or person | Answers the debrief questions and confirms or questions each bug |
| map-coverage | agent | Coverage by area and quality criterion, with a charter proposed for every gap |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Bugs go to [findings to fixes](../findings-to-fixes/README.md); scripted checks
belong to [user acceptance testing](../user-acceptance-testing/README.md).

## Worked examples

All made-up. A 45-minute charter explores a volunteer sign-up form's error handling with only a
keyboard and a slow connection, because an acceptance step failed there last week. The session runs
five minutes over to reproduce a bug where going back clears the name fields, asks whether a shift
is held during an error, and lists the screen reader and the dark theme as not covered. The debrief
confirms the bug and proposes a screen reader charter; the coverage notes show that gap.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- The session checks catch missing fields and late notes, not shallow exploration; the debrief is the real review.
- Coverage is what the sessions report; it is not proof that unexplored areas are free of problems.
- Sources are named in the method; the wording, rules and examples are original.
