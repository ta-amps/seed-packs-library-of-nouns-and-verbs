# Direction to work

## What this pack lets workers do

A collection of nouns and verbs for turning a stakeholder's message into direction nouns,
finding nouns and atomic verbs. One message often mixes a new rule, a complaint about
something that came back, a request, a question about money and a "yes" to an earlier
proposal. Workers split it into typed parts, record each direction with its scope and
source, keep superseded directions on the record, plan small verbs for the requests,
settle what research can settle and ask the person only what only they can decide. Later
work is checked against the directions in force, so the same correction is not needed twice.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle and the rules: one part, one type, one destination; a repeated correction is a finding plus a check |
| Part kinds | Direction, finding, work request, question, approval, taste call, status request and standing order, with signals and destinations |
| Ask policy | Ask only about spending, licenses, credentials, private facts, irreversible or public actions and real taste calls; otherwise decide and record why |
| Supersession policy | Newer wins in the same scope, narrower wins inside its scope, ambiguity goes to a person, nothing is deleted |
| Term rule guide | Forbid, require and prefer rules a sweep can check, with variants and allowed contexts |
| Direction checks | 11 deterministic checks with 3 made-up good and 11 made-up bad directions, rechecked by `make check` |
| Templates | Message intake, direction, decision, work plan, conflict, confirmation and compliance report |
| Worked examples | A made-up message split into six routed parts, a vocabulary direction in force, and a three-item work plan |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| split-message | agent | Records the message by digest and splits it into typed, routed parts |
| draft-directions | agent | Writes proposed directions with scope, source, term rules and checks |
| find-conflicts | agent | Lists overlaps with directions in force and suggests resolutions |
| confirm-directions | person | Confirms paraphrases and scopes and settles conflicts; only then does a direction bind |
| plan-work | agent | Turns requests into atomic verbs with inputs, acceptance checks, authority and outcomes |
| decide-or-ask | agent | Decides with a recorded reason, or writes one precise question with a default |
| sweep-compliance | agent | Checks artifacts against directions in force and proposes a finding per violation |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs
instead of enqueueing them. Problems go to [findings to fixes](../findings-to-fixes/README.md),
large requests to [decomposition patterns](../decomposition-patterns/README.md), taste calls to
[taste palettes](../taste-palettes/README.md), status questions to
[status and handoff](../status-and-handoff/README.md) and renames to
[rename and relink](../rename-and-relink/README.md).

## Worked examples

All made-up. A program director's chat message holds six parts: a vocabulary direction
("neighbors", not "clients"), a page that still uses the old word, a request for pickup times,
a hosting-plan question that only the director can answer, an approval and a status question.
The direction supersedes an older one that stays on the record, and the work plan gives each
item its inputs, checks, authority and outcome.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Keep each message noun in your private scope.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- The direction checks catch missing and inconsistent fields, not a wrong reading of a message; a person confirms every direction.
- Term sweeps catch words, not meaning; rules that are not about words need a reviewer's judgment.
