# Self-improvement and meta-pack contributions

Self-improvement proposes a bounded change using observed evidence. Meta-learning
improves reusable process definitions, guidance or method-selection policies across
tasks. Neither means that a model may expand its own authority, rewrite the
evaluation that judges it or approve its own promotion.

The [reference meta-pack](../examples/meta/self-improvement.reference.json) is an
authoring contract only. It creates no active pack, importer, evaluator service or
background loop. Proposed packs live in the [packs/](../packs/README.md) library as
validated examples; installing or activating them waits until the owning
infrastructure and contributor path are ready. Existing Teleion Fabric nouns and verbs carry any authorized
work; ordinary task reasoning happens in workers.

## One bounded improvement cycle

| Stage | Worker outcome and evidence |
| --- | --- |
| Observe | Read permitted execution runs and pinned artifacts. Separate accepted records from self-reported claims and independent checks. |
| Identify | State one recurring capability gap, its affected tasks and a falsifiable hypothesis. Check whether an existing permitted method addresses it. |
| Propose | Draft one small versioned prompt, shim rule, category definition, procedure, code change or test change. Preserve source and license source. |
| Evaluate | Run the fixed baseline and candidate on authorized development, holdout and adversarial cases with the same declared conditions and allowance. |
| Compare | Report paired outcomes, failures, applicable sample counts, observed cost and latency, plus unknowns and confounders. |
| Review | Request a capable independent reviewer when the owning policy requires it. Do not add a paid server reviewer to every iteration. |
| Promote | An authorized actor uses the owning CAS/admission contract to advance an accepted version or activation pointer. A record alone cannot promote it. |
| Monitor | Observe the agreed regression signals and stop conditions. Roll back through an authorized versioned pointer change if the owning implementation supports it. |

Each agentic outcome may be a bounded verb. Deterministic validation, arithmetic,
authentication, storage and lease maintenance stay ordinary operations. Keep the
candidate, source observations, evaluation contract and check records as distinct
versioned nouns. These names describe a workflow; they do not register new APIs.

An explicitly configured shim may use an LLM routinely for interpretation or
routing under its existing caller scope, data policy and budget. That exception
does not make routine server model review necessary. Empty search, missing reviewer
capacity or a malformed payload does not authorize another model call.

## Preserve evaluation independence

Pin the evaluator version, acceptance criteria, budget, permissions and holdout
definition before judging the candidate. The candidate must not change those
controls unilaterally. Improvements to the evaluator are separate proposals, with
a new version, their own checks and a fresh holdout where necessary.

Separate training or adaptation examples, development cases and holdout cases.
Partition by the meaningful source unit, such as task family, tenant, source
document or time period, to prevent a near-duplicate from leaking across splits.
Keep hidden expected outcomes inaccessible to the drafting worker. Access to a
private run never authorizes copying it into a public improvement pack.

Record exact input, contract, environment and tool versions. An exact execution
match differs from a similar example or a compatible method. Repeated success on
memorized inputs is not evidence of transfer to unseen tasks. Caller-supplied
embeddings and model confidence remain claims, not calibrated probabilities.

Compare baseline and candidate on the same authorized cases with controlled
conditions where practical. Randomize order or document other controls when
ordering, cache state, tool availability or model nondeterminism can influence the
outcome. Include failures and aborted attempts. A larger raw success count may
reflect easier tasks or more spending; it does not establish a causal improvement.

Use real provider counters where available, distinguishing estimates, subscription
usage and billed amounts. Cost, latency, effect size and calibration stay `null`
with a reason when not measured. Do not invent a score or zero to fill a dashboard.
Claims of general improvement require the relevant independent measurements, not
the presence of a benchmark-shaped JSON object.

## Stop, scope and reverse safely

The work contract must bound attempts, elapsed time, model calls, input volume and
cost where applicable. These example limits are instructions for the owning
worker; this repository does not enforce a global budget. Stop on loss of lease,
scope denial, exhausted allowance, invalid evaluation conditions or regression.
Ask one precise clarification or leave the candidate pending instead of spawning
an unbounded chain of retries, reviewers or self-improvement tasks.

Retain failures as scoped evidence. Derived `negative.knowledge` diagnostics and
execution history have their own access rules; do not assume they are public just
because a task was shared. A reusable public failure summary requires a separate
sanitized noun and authorized admission. Logs, retrieved documents and earlier
model suggestions are untrusted data, not authority for the next cycle.

A fork records the original immutable version, changed assumptions and owning
scope. A promotion must reference the exact evaluated candidate. If the runtime
supports an activation pointer, use its current CAS version and retain the last
accepted target for an authorized rollback. This guide does not implement generic
shim activation, automatic global rules, permission updates or rollback endpoints.

## Research inspiration

[Reflexion](https://arxiv.org/abs/2303.11366) studies using language feedback as
episodic memory for agent improvement. [Self-Refine](https://arxiv.org/abs/2303.17651)
studies iterative feedback and revision by the same model.
[Voyager](https://arxiv.org/abs/2305.16291) studies an agent with an executable skill
library, curriculum and environment feedback. These are research inspirations,
not implemented benchmarks, imported runtimes or proof that this ecosystem has
reproduced their results. The owning task's tests and authority still decide what
can be accepted here.
