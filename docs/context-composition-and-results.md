# Context, combined outcomes and result delivery

These are contributor design guidelines, not an installed context resolver,
notification service or new set of API fields. Put owner-defined work data inside
an existing task brief or noun value. Read [format limits](formats.md) and the
[worker lifecycle](lifecycle.md) before constructing a real request.

## Keep the worker's required context small

A useful work contract identifies one outcome, pinned input nouns, permitted
artifact paths, required capabilities, output types, acceptance checks and limits.
Separate required inputs from optional pointers. Include the relevant source
sections and stable references; do not copy an entire repository or transcript
into every task. Missing required context should produce one precise question or
a supported park/failure outcome, not a guess that the task is complete.

Some tasks need only a model to return a typed candidate. Others need a harness
that can inspect files, execute checks or use a browser. Choose the narrowest
sufficient worker capability profile for that task. A tool-free profile is an
option, not a universal rule for all workers. Capability declarations describe
requirements; actual grants and harness controls enforce what may happen.

Keep the full project definition as versioned nouns, with a small resolved packet
for each verb. The planned general resolver must pin dependencies, detect
conflicts and record source. This guide does not implement that resolver.
Workers should not be required to reconcile competing category tables manually.

## Check the combined outcome

Two valid contributions can violate a shared condition when combined. An export
route can rely on a role check that a separate refactor moves elsewhere. Separate
passing checks do not establish that a guest still cannot export the combined
application's data.

Declare the shared invariant and the exact artifact versions being assembled.
Use a bounded `verb.verify_gate` work contract for the affected integration checks
when needed. Keep its evidence as a separate evaluation noun tied to the combined
revision. If an artifact or required environment changes, the earlier evidence
continues to describe the old state; rerun affected checks for the new state.

Do not turn every small change into a review pipeline. Reuse valid component
evidence and check the interfaces or constraints changed by the combination.
Additional judgment remains a review verb only when the owning policy requires
it. A shared public catalog can still require a distinct reviewer.

For coupled settings, evaluate the tuple. A made-up retry budget may include
attempt count, timeout, backoff, overhead and the remaining lease interval.
Testing only the new retry count misses the joint time bound. A formula using
configured limits is not an observed latency or throughput measurement.

Current dependency readiness can follow terminal failure or cancellation as well
as success. A downstream worker must inspect the actual predecessor outcome and
required artifacts. Preserve these distinct facts: component check passed,
combined check passed, authorized application occurred, parent outcome satisfied
and public admission completed. A submit record alone proves none of the latter
conditions beyond its own accepted output identity.

## Finish work once; deliver its result separately

A useful completion update is short and specific:

> Submitted the candidate. The required checks passed. Independent admission is
> pending. The artifact and check record are linked in the task output.

Use the actual state and actual checks. Prefer status, outcome, next action and
permitted evidence references over a long recap or an ambiguous "done". This can
be a deterministic projection of an existing task result. Optional client-side
wording or speech must not invent checks or change the recorded status.

Place custom presentation data in the task's declared output schema or a governed
noun. The version-1 execution report rejects unsupported top-level fields; use
its documented summaries and artifact references where appropriate.

If a future delivery adapter retries a notification, identify the delivery by
run/record, destination and channel. Retrying delivery must not resubmit the
work, repeat a payment, republish a file or replay another external effect. Keep
delivery acknowledgment separate from task completion. A crash with an uncertain
external effect needs reconciliation against the destination before another
attempt. Internal idempotency does not prove that an external effect occurred
exactly once. This repository installs no such delivery adapter.

## Let evidence select no change

An improvement experiment should retain the unchanged baseline as a valid
outcome. A candidate that does not beat the fixed acceptance criteria can remain
private. Equal measured outcomes need no invented semantic tie-break. Missing or
invalid outcome evidence remains unknown. A timed-out check records a timeout,
not a correctness verdict or an invented cost.

Record whether a check used a lightweight fixture, the actual target runtime,
a deployed service or a native model harness. Each supplies different evidence.
The worker-driven [meta-pack blueprints](meta-pack-blueprints.md) use these
boundaries when proposing reusable methods, shims or evaluation changes.
