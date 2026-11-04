# Harness onboarding

## What this pack lets workers do

A collection of nouns and verbs for connecting an agent harness (a coding agent, chat
client or custom worker) and proving that it works end to end: it claims a task, reads a
pinned noun and checks its digest, heartbeats, writes a noun, reads it back, submits with
an idempotency key and shows up in the audit trail. Each run records the exact harness
version, provider and model, so runs can be compared later.

## Nouns

| Noun | What it holds |
| --- | --- |
| Lifecycle checklist | Ten steps with expected observations, two optional negative probes and the pass rule |
| Connection guide | MCP and HTTP transport rules, argument rules and credential handling |
| Recovery playbook | What to do for 401, 403, 404, 409, 413, 400 or 422, 429, 503 and an uncertain submit |
| Templates | Connection, run record (with a made-up example), diagnosis, compatibility summary and run review |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| connect-harness | agent or person | Configures the harness and confirms discovery and identity |
| run-lifecycle | the harness under test | Claims this very task and performs every checklist step |
| diagnose-failure | agent | Classifies a failed step and says whether a retry is safe |
| compare-harnesses | agent | Tabulates runs by version, provider, model and steps passed |
| review-run | different agent | Rechecks the receipt, audit and identity |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose
follow-up verbs, such as a diagnosis for a failed step.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface. Let the harness under test claim `run-lifecycle`. Use a local Tessera
service unless the owner authorized a hosted run and its health is confirmed.

## Limits

- Credentials stay in the harness's own credential store; no noun, brief or output holds one.
- A passing run shows the lifecycle works for that harness version on that day, not that
  the harness does good work on real tasks.
- Token counts stay null unless the harness or provider measured them.
