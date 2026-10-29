# Security review

## What this pack lets workers do

Review code you own, or are explicitly authorized to review, for security problems.
Workers first confirm the authorization, sketch a threat model, review one area at a
time from a 16-area catalog, reproduce findings only in a local sandbox with synthetic
data, propose a patch with a test, and have another worker check the findings. Nothing
is scanned, probed or exploited on any running system, and findings stay private.

## Nouns

| Noun | What it holds |
| --- | --- |
| Scope rules | Authorized, local-only, private, secrets masked, never weaken a control |
| Check catalog | 16 areas, from object-level authorization and injection to agent tool boundaries |
| Severity rubric | Five severity levels, a confidence rule, 6 deterministic finding checks and 5 golden findings the validator rechecks |
| Templates | Authorization, scope check, threat model, finding, reproduction, fix and review |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| check-scope | Confirms the authorization covers this requester, target, commit and activities; deterministic | Scope check |
| threat-model | Assets, entry points, trust boundaries, attackers, priority areas | Threat model |
| review-code | Reviews one catalog area; run once per area | Findings |
| reproduce-locally | Builds the pinned commit in a sandbox and tries one finding | Reproduction |
| propose-fix | A test that fails before and passes after, plus the smallest patch; never pushed | Fix |
| review-findings | A different worker reruns the checks and upholds, downgrades or rejects | Review |

Each verb can also end with `no_change`, `unknown` or `blocked`. Without a passing
scope check, every later verb returns `blocked`.

## How to use it

Write an authorization noun shaped like `template.authorization` and a snapshot noun
for the exact commit, write the nouns in [nouns.json](nouns.json) create-only, then fill
`check-scope` from [verbs.json](verbs.json) with `scripts/build_packs.py --instantiate`
and enqueue it yourself.

## Limits

- Reviewing someone else's system needs their written authorization; this pack cannot
  grant it.
- Findings reasoned from code alone are at most medium confidence until reproduced.
- Disclosure, fixes landing and any contact with others are the owner's decisions.
