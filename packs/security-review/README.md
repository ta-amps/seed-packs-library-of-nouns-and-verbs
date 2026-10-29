# Security review

## What this pack lets workers do

A collection of nouns and verbs for authorized, local-only security review of code you
own or are explicitly allowed to review. Workers first confirm the authorization, sketch
a threat model, review one area at a time from a 16-area catalog, reproduce findings only
in a local sandbox with synthetic data, propose a patch with a test, and have another
worker check the findings. Nothing is scanned, probed or exploited on a running system.

## Nouns

| Noun | What it holds |
| --- | --- |
| Scope rules | Authorized, local-only, kept in your scope, secrets masked, never weaken a control |
| Check catalog | 16 areas, from object-level authorization and injection to agent tool boundaries |
| Severity rubric | Five severity levels, a confidence rule, 6 deterministic finding checks and 11 golden findings the validator rechecks |
| Templates | Authorization, scope check, threat model, finding, reproduction, fix and review |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| check-scope | Confirms the authorization covers this requester, target, commit and activities | Scope check |
| threat-model | Assets, entry points, trust boundaries, attackers, priority areas | Threat model |
| review-code | Reviews one catalog area; once per area | Findings |
| reproduce-locally | Builds the pinned commit in a sandbox and tries one finding | Reproduction |
| propose-fix | A failing-then-passing test and the smallest patch; never pushed | Fix |
| review-findings | A different worker reruns the checks and upholds, downgrades or rejects | Review |

Each verb can also end with `no_change`, `unknown` or `blocked`. Without a passing scope
check, every later verb returns `blocked`.

## How to use it

Write an authorization noun shaped like `template.authorization` and a snapshot noun for
the exact commit. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- Reviewing someone else's system needs their written authorization; this pack cannot grant it.
- The local-only and secret checks are guards, not proof; the reviewer still reads every finding.
- Disclosure, fixes landing and any contact with others are the owner's decisions.
