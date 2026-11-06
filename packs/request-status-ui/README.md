# Request status UI

## What this pack lets workers do

A collection of nouns and verbs for rendering an event-driven request status page (`/requests/:id`) from receipt-backed event envelopes, mapping snapshot payloads, holding replay steps at human reading speed and keeping waiting states and dedicated-worker attributions honest.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Keep raw worker ids, request ids, hashes and HTTP codes out of plain views; show self-check refusals only when `review.refused` occurred; keep dedicated team workers distinct from volunteers; require `distinct_reviewer` on view receipts |
| `spec.request-status-events-v1` | Fifteen event types, six progress-strip states, four workflow bands (`step-split`, `step-build`, `step-review`, `step-ready`) and reading-speed replay floors |
| `tool.request-status-ui` | Tested Python package and dependency-free JavaScript port in [code/](code/README.md), counting shared-library `task objects` and `tasks` (things to do) |
| `template.request-event-list` | JSON Schema for validated event streams derived from snapshot payloads |
| `template.request-view-receipt` | JSON Schema for Python/JavaScript parity, plain-copy hygiene and replay-hold receipts |
| Worked example | Made-up intake request parity receipt (`example.req-intake-07-view-receipt`) verified by Python and Node tests |

## Verbs

| Verb (task: thing to do) | Who | What happens |
| --- | --- | --- |
| `derive-events` | agent, no model | Derive ordered request-status events from a snapshot payload and validate sequence and receipt digests |
| `check-view` | agent, no model | Independently check Python/JS view parity, plain-copy rules and reading-speed replay holds (`distinct_reviewer`) |

## How to use it

Run `make check` in [code/](code/README.md) to run all 15 Python unit tests, `ZeroHardcodedValuesAstGate` AST scanning and Node JavaScript parity checks across both fixtures.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these Tasks through the shared work queue.
- Offline checks verify deterministic event reduction, parity and reading-time math; real screen-reader and layout review still belong on rendered pages.
