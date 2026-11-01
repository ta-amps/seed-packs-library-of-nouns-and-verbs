# loops-schedules-and-heuristics (`loops_schedules`)

Standard-library implementation of:
- `DeclarativeScheduleAndCadenceCompiler`: inert Schedule Noun compiler (`auto_enqueued=False`) with window-keyed `idempotency_key`s, deterministic jitter, zero-I/O due-window checks, `stop_at` deadlines, exponential backoff, `systemd --user` templates, Fragility Half-Life Urgency scheduling, and AIMD Claim Pacing.
- `BanditAntiStallLoopAndResourceHeuristic`: UCB1 + empirical-Bayes shrinkage arm selector with plateau mutation and `negative_tombstone` suppression, plus the 7-tier Compute & Resource Cascade Heuristic.
- `SwappableLearnerAdvisors`: deterministic `advice_only=True`, `keep_baseline_valid=True` evaluators for all 6 swappable learners.

Run checks:
```bash
make check
```
