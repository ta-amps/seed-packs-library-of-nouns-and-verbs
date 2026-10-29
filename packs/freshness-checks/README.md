# Freshness checks

## What this pack lets workers do

A collection of nouns and verbs for finding stale, deprecated or end-of-life knowledge
before it misleads a worker. Workers watch the tools, packages, APIs, models and pages
that other nouns pin, flag what is stale or out of support with a fixed policy, read
upstream deprecation notices, propose replacements and trials, and record do-not-use
tombstones with evidence.

## Nouns

| Noun | What it holds |
| --- | --- |
| Freshness policy | Max ages per kind of upstream, six flags and the action each calls for |
| Templates | Watch item, deprecation notice, freshness report and tombstone |
| Daily scan | A proposal: scan daily at 05:00 UTC; not activated |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| scan-staleness | Applies the policy and proposes the follow-up verbs each flag needs; deterministic | Freshness report |
| check-deprecations | Reads due items' release feeds and deprecation pages | Notices, watch items |
| propose-replacements | Describes named replacements and proposes trials for them | Candidate cards |
| record-tombstone | Checks the evidence and records a do-not-use tombstone | Tombstone |

Each verb can also end with `no_change`, `unknown` or `blocked`.

## Recurring runs

Recurring execution needs Tessera's flag-gated schedule support, which is being
designed now. **No scheduler is activated by this pack.**

## How to use it

Write a watch item for each upstream thing your nouns pin. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A failed request is "source unreachable", never proof of deprecation.
- License changes and unreachable sources go to a person.
- A proposal: nothing has been scanned with these verbs yet.
