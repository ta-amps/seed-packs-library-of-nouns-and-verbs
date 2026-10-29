# Docs improvement

## What this pack lets workers do

Make documentation easier to understand and act on for a specific reader. Workers
audit pages against an eight-point plain rubric, find the first tasks no page covers,
draft rewrites that keep every fact, command and number, run the code examples and
check the links, and have another worker or a person confirm each fix. Rewrites are
private drafts until the owner commits them.

## Nouns

| Noun | What it holds |
| --- | --- |
| Doc rubric | Eight criteria: first screen, one reading order, task coverage, runnable examples, plain language, honest status, working links, accessible structure |
| Templates | Reader persona (with a synthetic example), doc audit, doc gaps, rewrite, example run and review |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| audit-docs | Reads the pages as the named reader and cites every issue | Doc audit |
| find-gaps | Lists first tasks no page covers, ranked | Doc gaps |
| draft-rewrite | Rewrites one page as a patch; facts unchanged | Rewrite |
| check-examples | Runs code blocks in a sandbox and checks local links; deterministic | Example run |
| review-docs | A different worker or a person checks each claimed fix | Review |

Each verb can also end with `no_change`, `unknown` or `blocked`. Tone choices can go
through the [taste-palettes](../taste-palettes/README.md) pack first.

## How to use it

Write a reader persona and a snapshot noun for the exact commit, write the nouns in
[nouns.json](nouns.json) create-only, then fill `audit-docs` from [verbs.json](verbs.json)
with `scripts/build_packs.py --instantiate` and enqueue it yourself.

## Limits

- A rewrite never changes a fact; `facts_changed` is always false.
- External links are checked only when the requester allows network access.
- Committing or publishing a rewrite is the owner's separate act.
