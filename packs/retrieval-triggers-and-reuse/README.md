# Retrieval triggers and reuse

## What this pack lets workers do

A collection of nouns and verbs for looking up existing nouns before generating new ones and
reusing past solutions without trusting them blindly. Teams of agents keep rebuilding what they
already have: a worker writes a new template when one exists, solves a task whose twin was solved
last week, or reuses an answer verified under a different setup. Workers fire lookup triggers
before generating, climb a ladder from what is at hand to new research, treat a fingerprint match
as permission to try under the check, store only solutions that regenerate their result alone,
keep unmet needs open so later arrivals can meet them, and judge reuse by verified work per unit
of cost.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | How lookups, reuse, qualification, promotion and saved needs fit together |
| Trigger rules | When a worker must look up first, when it may skip, and the cheapest-first search order |
| Sufficiency ladder | Eight rungs from at hand to abstain, with a threshold derived from measured costs |
| Fingerprint rules | Step keys, five levels with backoff, loose on the task and strict on the environment |
| Qualification rules | Delete, replay alone, pass again, recitation guard; bars for each kind of memory |
| Evidence types | Parsed, resolved, observed, reported or designed, carried by every retrieved fact |
| Reuse checks | 9 deterministic checks with 2 synthetic good and 9 synthetic bad stored solutions, rechecked by `make check` |
| Templates | Lookup record, qualified solution, reuse attempt, saved need, arrival match, reuse ledger and promotion decision |
| Worked examples | A lookup that finds an exact match, an unmet need kept open and a month of reuse against the month before |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| look-up-first | agent | Fires the triggers, searches cheapest first and records the rung that answered |
| try-reuse | agent, deterministic | Tries a match in a copy; the check decides; a miss is rolled back |
| qualify-solution | agent | Stores a body only after it regenerates the result alone and passes the recitation guard |
| review-promotion | a different agent or a person | Promotes, keeps, rejects or tombstones a stored solution |
| record-saved-need | agent | Keeps an unmet need with constraints, a cheap filter and an expiry |
| match-arrivals | agent | Checks new arrivals against open needs and records the stage that rejected each |
| measure-reuse | agent, deterministic | Counts verified tasks per thousand model calls against a baseline window |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs
instead of enqueueing them. Surveys before building something new go to
[prior art and alternatives](../prior-art-and-alternatives/README.md); refuted or wrongly verified
solutions become findings in [findings to fixes](../findings-to-fixes/README.md). Step keys come
from the packets defined in the [atomic step contract](../atomic-step-contract/README.md).

## Worked examples

All synthetic. The lookup fires two triggers, searches three places and decides to try an exact
match under the check before generating anything. The saved need keeps a resumable upload helper
open with three constraints. The ledger shows 51 verified tasks for 340 model calls, 150.0 per
thousand, against 86.3 the month before, with 11 rolled-back misses and 4 self-reuses not counted.
Each bad stored solution breaks one rule, such as a replay run inside the producing run.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Run look-up-first before any verb that writes a new noun.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- Hit rates on a real stream of tasks are unknown; recurring shapes in a test corpus are the most favourable case.
- The reuse checks catch a skipped qualification step, not a wrong check; a weak check makes every reuse weak.
- A lexical filter misses equivalent work under other words, and an embedding filter matches too much; the fit judgment carries the rest.
