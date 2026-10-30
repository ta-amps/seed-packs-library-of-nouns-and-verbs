# File triage at scale

## What this pack lets workers do

A collection of nouns and verbs for organizing very large collections of files without losing
any: years of drives, shared folders and exports that nobody can face sorting by hand. The
expensive mistakes are quiet ones: two folders with the same name treated as copies, a copy
verified by size, a source deleted before anyone checked the copy, a scan that reads a key file,
or an index that still points where things used to be. Workers scan read-only with secrets
excluded, place every group under a policy, prove duplicates by content hash, draft a move plan
a person approves, journal and verify each move, and leave sources in place until the person
retires them.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle from scope to reconciliation, and the rules on units, timestamps and caches |
| Placement policy | Ten roles and eleven statuses; a role comes from what the work produces, not its name |
| Duplicate rules | Four evidence levels; only a full hash with distinct inodes proves a duplicate |
| Filesystem fit | Space, allocation units, permissions, links, live databases and mount health |
| Secret exclusions | Paths listed by name and never opened, including key files |
| Triage checks | 13 deterministic checks with 2 synthetic good and 13 synthetic bad move plans, rechecked by `make check` |
| Templates | Scan scope, inventory, placement register, duplicate set, move plan, plan approval, move journal, retirement record and index reconciliation |
| Worked examples | A read-only inventory of two drives and three equal copies proven by full hash |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| scope-scan | agent | Agrees roots, exclusions, secret patterns, limits and the person's grouping rules |
| inventory-files | agent, deterministic | Walks the scope read-only and keeps every error |
| classify-items | agent | Places groups under the policy and asks about the uncertain ones |
| find-duplicates | agent, deterministic | Proves duplicates by full hash, inode and links, and lists consumers |
| plan-moves | agent | Drafts moves, deletions, questions, prechecks and a dry run for the person |
| approve-plan | person | Approves or rejects each move and deletion and answers each question |
| move-and-verify | agent, deterministic | Journals, copies, verifies by hash and never removes a source |
| retire-sources | person | Retires, keeps or links each verified source |
| reconcile-indexes | agent | Finds missing paths, stale notes and unregistered copies |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs
instead of enqueueing them. Drift and failed moves become findings in
[findings to fixes](../findings-to-fixes/README.md); progress on a long migration is reported with
[status and handoff](../status-and-handoff/README.md).

## Worked examples

All synthetic. The inventory covers an internal disk and an archive drive in bytes, keeps two
errors, lists three secret-bearing paths without opening them and changed nothing. The duplicate
set holds three equal files with distinct inodes, so removing two frees 8,000,004,096 allocated
bytes, but only after a report that reads one copy is pointed at the kept one. Each bad plan
breaks one rule, such as a deletion resting on name, size and date.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Run scope-scan before anything reads a file.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- The triage checks catch a missing safeguard in a plan, not a wrong placement; the person's approval still matters.
- Network drives that cannot be listed reliably end as unknown; the pack does not retry them indefinitely.
- Moves between machines, cloud uploads and their read-back checks need their own plan and are not covered here.
