# Release and verify

## What this pack lets workers do

A collection of nouns and verbs for releasing a change and proving what is live. A release
goes wrong quietly when checks passed on a different commit, when "deployed" means "the
command finished", or when nobody kept the version to go back to. Workers plan the release
around the exact tested head, confirm every required check ran on that head, and then wait:
the release owner lands the change and switches the live version, and records both. Workers
then hash the live bytes against the build, run read-only smoke checks and write one receipt
whose verdict follows from its parts. When something fails, they brief the owner on a rollback.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle and the rules: rerun checks if the landed commit differs, no release without a rollback target, partial means listed gaps |
| Release stages | Planned, checks green at head, landed, live, parity verified, smoke passed, verified and rolled back, with their evidence |
| Authority boundaries | What only the release owner does, what workers do, and how holds stop a plan |
| Parity methods | Comparing live and built bytes for static files, script bundles, container images and packages, and when the answer is unknown |
| Smoke checklist | Five read-only checks for any live release, and when a write check needs the owner's named target |
| Release checks | 10 deterministic checks with 2 synthetic good and 10 synthetic bad receipts, rechecked by `make check` |
| Templates | Release plan, head check, release record, parity check, smoke report, rollback brief and release receipt |
| Worked examples | A release plan for a small site fix and a verified receipt |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| plan-release | agent | Names the tested head, checks, holds, rollback target, parity method, smoke checks and owner acts |
| check-head | agent, deterministic | Confirms every required check passed on the exact head, read-only |
| record-release | release owner | Records the landed commit, the live version and the version it replaced |
| verify-parity | agent, deterministic | Hashes the live bytes and compares them with the build |
| run-smoke | agent, deterministic | Runs read-only smoke checks against the live version |
| write-receipt | agent, deterministic | Assembles the chain and derives the verdict from its parts |
| prepare-rollback | agent | Briefs the release owner on switching back; the owner decides |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs
instead of enqueueing them. Failures go to [findings to fixes](../findings-to-fixes/README.md),
and receipts are the evidence a [status](../status-and-handoff/README.md) cites when it says verified.

## Worked examples

All synthetic. A plan for a small site fix names head `9c1e2d7a41b0`, two required checks and
the three acts only the release owner performs. Its receipt is verified: both checks ran on
that head, the live bytes of two files match the build, five smoke checks pass and the previous
version is kept. The release checks also hold a partial receipt where a cache hid the live bytes.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- No verb lands, releases or reverts anything; those stay the release owner's acts.
- The release checks catch missing and inconsistent fields, not wrong identifiers; the receipt is only as good as what was read.
