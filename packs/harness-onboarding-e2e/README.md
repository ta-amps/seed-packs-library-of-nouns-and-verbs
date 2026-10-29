# Harness onboarding

## What this pack lets workers do

Connect a new agent harness (a coding agent, chat client or custom worker) to Tessera
and prove that it really works end to end: it claims a task, reads a pinned noun and
checks its digest, heartbeats, writes a private noun, reads it back, submits with an
idempotency key and shows up correctly in the audit trail. Each run records the exact
harness version, provider and model, so runs can be compared later.

## Nouns

| Noun | What it holds |
| --- | --- |
| Lifecycle checklist | Ten steps with expected observations, two optional negative probes and the pass rule |
| Connection guide | MCP and HTTP transport rules, argument rules and credential handling |
| Recovery playbook | What to do for 401, 403, 404, 409, 413, 400 or 422, 429, 503 and an uncertain submit |
| Templates | Connection, run record (with a synthetic example), diagnosis, compatibility summary and run review |

## Verbs

| Verb | Who | What happens | Produces |
| --- | --- | --- | --- |
| connect-harness | agent or person | Configures the harness and confirms discovery and identity | Connection record |
| run-lifecycle | the harness under test | Claims this very task and performs every checklist step | Run record |
| diagnose-failure | agent | Classifies a failed step and says whether a retry is safe | Diagnosis |
| compare-harnesses | agent | Tabulates runs by version, provider, model and steps passed | Compatibility summary |
| review-run | different agent | Rechecks the receipt, audit and identity | Run review |

Each verb can also end with `no_change`, `unknown` or `blocked`.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only in your assigned scope, fill
`connect-harness` and then `run-lifecycle` from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate`, enqueue them yourself, and let the harness under
test claim `run-lifecycle`. Use a local Tessera service unless the owner authorized a
hosted run and its health is confirmed.

## Limits

- Credentials stay in the harness's own credential store; no noun, brief or output
  ever holds one.
- A passing run shows the lifecycle works for that harness version on that day. It does
  not show the harness does good work on real tasks.
- Token counts stay null unless the harness or provider measured them.
