# Status and handoff

## What this pack lets workers do

A collection of nouns and verbs for answering what is done, what is next and where to resume,
with evidence. "What is the status?", "what is next?" and "did that really finish?" are among
the most frequent questions a person asks a team of agents, and the answers drift when a
claim from an earlier session is repeated as fact. Workers read the real state first, place
every item at one of seven levels with the evidence that level needs, have a different worker
recheck reported claims, rank the next steps with at most three decisions for the person, write
a handoff whenever a session stops, and resume from a handoff by rechecking it.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle and the rules: one status per checkpoint, observed apart from reported, counts first, no stop without a handoff |
| Status levels | Verified, reported, in progress, blocked, failed, unknown and not started, with the evidence each needs |
| Evidence rules | Which evidence supports which claim, such as a check run on the exact head, and when it goes stale |
| Ranking rules | Deadline risk, then what unblocks most, then staleness, then size; at most three items for the person |
| Resume playbook | Resuming after a usage limit, a context limit, a crash or a reassignment |
| Status checks | 10 deterministic checks with 2 made-up good and 10 made-up bad status reports, rechecked by `make check` |
| Templates | Snapshot, status report, claim check, next steps, handoff and resume check |
| Worked examples | A status with every level and a handoff written when a usage limit stopped a session |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| take-snapshot | agent, deterministic | Reads heads, check runs, deployments and workers, read-only |
| write-status | agent | Places every item at one level with evidence and leads with counts |
| recheck-claims | a different agent | Confirms or contradicts reported claims against fresh evidence |
| rank-next-steps | agent | Orders next steps by the ranking rules and keeps the person's list short |
| write-handoff | agent | Records ownership, next steps with a first check each, open questions and unchecked claims |
| resume-from-handoff | agent | Rechecks a handoff's claims and looks for concurrent work before continuing |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs
instead of enqueueing them. A contradicted claim or a stop without a handoff goes to
[findings to fixes](../findings-to-fixes/README.md); a large next step goes to
[decomposition patterns](../decomposition-patterns/README.md). Release receipts from
[release and verify](../release-and-verify/README.md) are the strongest evidence a status can cite.

## Worked examples

All made-up. A status for a small catalog site leads with "2 verified, 1 reported but not
rechecked, 1 in progress, 1 blocked, 1 failed, 1 unknown"; the failed draft keeps its log, and
the blocked backup carries one question about a credential. The handoff names what the next
session owns, what belongs to another agent and the first check before any edit.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Take a snapshot before every status.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- The status checks catch missing evidence and inconsistent fields, not wrong evidence; a recheck by a different worker still matters.
- Evidence ages are starting points to tune, not measured values.
