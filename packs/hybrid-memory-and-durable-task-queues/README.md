# Hybrid memory matrices and durable task queues

## What this pack lets workers do

A collection of nouns and verbs for operating inline-lease durable task queues of `tasks (things to do)` and `task objects` without fragile cron stalled-job sweepers, enforcing `maker != checker` anti-self-approval and `dead_letter` poison routing, memoizing paid model step receipts for `0`-token crash replay, deduplicating ratings by content/ontology/rubric/prompt/model SHA-256, coalescing homogeneous items sharing prefix `P` while triggering `ADaPT` subtask decomposition strictly on verification failure, and training open-weights adapters across time-bounded sessions via subspace optimizer memory matrices and rotating transformer layer windows.

## Nouns

| Noun (`task objects`) | What it holds |
| --- | --- |
| Guardrails | Inline `lease_expires_at` reclamation, `maker != checker` separation, `0`-token step-receipt replay, 6-field rating idempotency and bounded subspace memory matrices |
| `spec.durable-queue-and-subspace-memory-grid` | Durable task lifecycle states, rating idempotency tuple, `ADaPT` granularity modes and subspace layer-window grid axes |
| `rules.lease-idempotency-adapt-and-layer-rotation` | Zero-sweeper claim query, `HarnessTax` shared-prefix batch coalescing and chained SHA-256 rotating-layer checkpoints |
| `tool.hybrid-durable` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.hybrid-durable-receipt` | JSON Schema for inline lease reclamation, `maker != checker` verification, `0`-token replay, prefix token savings, subspace compression ratio and AST/naming verdicts |
| Worked example | Evaluation bundle (`example.hybrid-durable-bundle`) and recomputed receipt (`example.hybrid-durable-receipt`) verified by `test_hybrid_durable.py` |

## Verbs

| Verb (`tasks (things to do)`) | Who | What happens |
| --- | --- | --- |
| `claim-and-replay-durable-task` | agent, no model | Reclaim expired leases inline without cron sweepers, enforce `maker != checker`, dead-letter poison tasks and replay cached step receipts in `0` tokens |
| `coalesce-prefix-and-decompose-on-failure` | agent, no model | Coalesce homogeneous items sharing ontology/schema prefix `P` into `K`-item batches and trigger `ADaPT` decomposition strictly on failure |
| `project-subspace-memory-and-verify-gates` | agent, no model | Compress gradient matrices into rank-`r` subspace states across rotating layer windows and enforce AST/naming conformance gates |

## How to use it

Run `make check` in [code/](code/README.md) to verify inline lease expiry reclamation, `maker != checker` gating, `dead_letter` poison caps, `0`-token step replay, rating deduplication, shared-prefix token savings, `4.0x` subspace compression across `16` layers, `ZeroHardcodedValuesAstGate` and `DomainAgnosticNamingGate`.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these Tasks through the shared work queue.
- Offline SQLite queue simulation, subspace projection, AST verification and worked-example recomputation run deterministically with the Python standard library and no network calls.
