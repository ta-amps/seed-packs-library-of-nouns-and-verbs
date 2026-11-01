# hybrid-durable

Standard-library Python 3.10+ reference implementation for Seed Pack `hybrid-memory-and-durable-task-queues`:

- `InlineLeaseDurableQueue`: inline `lease_expires_at` reclamation with zero stalled-job cron sweepers, DAG `depends_on` unlocking, `maker != checker` anti-self-approval, `dead_letter` poison routing, `step_receipts` crash-replay memoization, and content-addressed rating idempotency.
- `AdaptAndCoalescePlanner`: `HarnessTax` shared-prefix batch coalescing (`1 < K <= K*`) paired with `ADaPT` decompose-on-failure.
- `HybridSubspaceMemoryTrainer`: zero-OOM subspace optimizer memory matrix compression and multi-session rotating transformer layer windows with SHA-256 checkpoint continuity.

```bash
make check
```
