# Capability research: from feeds to a project decision

Status: proposed seed-pack workflow, October 29, 2026. This document defines a
use case and acceptance criteria. It does not connect to an inbox, scrape feeds,
install candidates, enqueue work or enable a background research service.

The problem is attention and comparability. Many posts can describe the same
release. Different projects report numbers for different tasks, hardware, model
versions, quality thresholds and budgets. Even an accurate result may have little
bearing on the system that would use it.

The useful outcome is a small set of decisions for a pinned project profile:
investigate, trial, adopt, watch or reject, with evidence and a reason. A worker
recommendation to adopt is separate from permission to change a project. Most
items should finish with a cheap relevance decision rather than an experiment.

## Nouns that preserve the context

These names describe proposed noun roles. They are not newly registered category
IDs, storage schemas or API fields. Store accepted records through existing CAS
contracts and preserve their owning scope.

| Noun role | Contents that matter |
| --- | --- |
| Source observation | Original URL or permitted message reference, author/publisher, publication and retrieval dates, permitted excerpt or digest, access restrictions and the exact upstream version when available |
| Capability candidate | What the release does, upstream identity, source/code/model revisions, supported interfaces, dependencies, licenses and known limits; keep posts about one release together |
| Claim | The attributed statement, metric, unit, task, dataset/split, baseline, model/version, harness, hardware, precision/quantization, concurrency and measurement conditions; unknown fields stay unknown |
| Project profile | Architecture and interfaces, target tasks, actual hardware/runtime, memory limits, data/privacy rules, allowed providers, license constraints, budgets and ranked preferences, with source and version for each requirement |
| Evaluation contract | The decision to resolve, fixed baseline, candidate versions, paired fixtures, success thresholds, resource limits, failure conditions and required evidence |
| Observation | Actual commands/tool events, environment and input hashes, outputs, failures, latency/quality/resource measurements and their provenance |
| Decision | A scoped recommendation, decisive evidence, unresolved questions, integration/maintenance cost, expiry or recheck triggers and the next useful verb |
| Procedure or seed | A reusable research method, fixture generator, adapter proposal or future verb brief derived from accepted evidence, with its own tests and admission state |

A profile should be a small set of versioned requirements with references, not a
copy of an entire project or private history. Workers can inspect authorized
configuration and read-only environment facts, but must distinguish observed
hardware from desired hardware and explicit preferences from inferred ones.
Missing facts become narrow questions only when they change the decision.

Private inbox observations and internal project constraints remain private.
Sanitized public summaries require a separate permitted projection. A source's
instructions, popularity or self-description cannot grant tool access or override
the research contract.

## Verbs that produce those nouns

| Bounded outcome | Inputs | Output and acceptance check |
| --- | --- | --- |
| Collect permitted observations | Configured public feeds, authorized connectors, exports or a batch of URLs | Source nouns with attribution, dates and access provenance; never claim unread content was inspected |
| Consolidate a release | Source observations and existing candidates | One candidate plus attributed claims; preserve conflicts and distinct versions, and avoid merging unrelated projects with similar names |
| Assess project relevance | Candidate, pinned project profile and earlier decisions | Explain the fit or mismatch and whether more evidence could change the decision; stop on a decisive hard constraint |
| Resolve a consequential claim | Attributed claim and permitted primary sources | Supported, contradicted, unresolved or inaccessible evidence, with exact sources; a vendor claim stays vendor-reported until reproduced |
| Design a comparison | Shortlisted candidate, current baseline and profile | A versioned evaluation contract approved under the owning task policy before running the candidate |
| Run a bounded trial | Fixed contract, isolated execution environment and permitted artifacts | Actual observations for both baseline and candidate, including failures and resource usage |
| Recommend a decision | Source claims, fit assessment and observed comparisons | Concise decision noun with tradeoffs, uncertainty, cost to adopt and a concrete follow-up or stop condition |
| Propose reusable work | Accepted observations and recurring research need | A candidate noun or seed verb with source pins, scope, checks and limits; no self-activation or self-admission |

Use existing verbs and kinds where they fit, such as source probing, drafting,
verification and benchmarking. Domain details belong inside the owning brief or
record value. This table does not introduce new top-level TaskSpec fields.

Deterministic URL canonicalization, hashing, ordinary retrieval, arithmetic and
receipt checks stay tools inside these verbs. Workers perform interpretation,
research planning and judgment. Herma can optionally provide scoped context.
The code-composition pack's tested code can supply verified deterministic experiment
steps where available; Kinema
can supply relevant motion/frame checks. Their availability does not establish
that a proposed adapter or evaluation already exists.

## Comparable evidence

Keep two separate questions: what a source claims, and what happened on the target
workload. Do not average unrelated leaderboards into a universal score.

Before treating numbers as comparable, match the task, dataset and split, metric
definition/direction, baseline, versions, harness, input size, hardware/runtime,
precision, concurrency, warm/cold state and quality requirements as applicable.
An irreconcilable difference is a reason to mark results non-comparable and define
a paired local trial. Unknown memory or cost is not zero.

For example, a synthetic post might report that Memory A is twice as fast as
Memory B on an unspecified accelerator. That is an attributed claim. It does not
establish latency, retrieval quality or privacy suitability for a CPU-only project.
The first useful work may be checking whether A supports that deployment at all.

Evaluate the current implementation and the candidate on the same target tasks
under pinned conditions. Include setup and integration effort, ongoing maintenance,
storage, RAM/VRAM, latency, quality, failed runs and provider/hosting cost where
relevant. Repeat enough trials for the stated decision; report dispersion and
sample size without inventing statistical confidence from a single run.

The candidate must not edit its judging controls. Separate development examples
from protected holdouts and group near-duplicates by source/workload to avoid
leakage. Preserve a no-change outcome. Existing independent review requirements
still govern shared artifact admission; ordinary screening does not need a new
reviewer for every item.

## Keep the attention and compute budgets explicit

Deduplicate before model work where possible. Reuse prior evidence only when its
source, version, profile and validity conditions still apply. Separate hard
constraints from soft preferences. A cheap incompatibility check can avoid an
expensive benchmark.

Escalate research when the expected decision value justifies its uncertainty,
execution cost and review time. Keep those estimates labeled as estimates. Set
per-batch source limits, a small trial allowance, a total model/cost ceiling and
a maximum decision-report size. Stop rather than recursively expanding tasks
without bounds. Queue absence or difficult comparison never enables server
inference automatically.

Retain useful rejection reasons with their scope and recheck trigger. A project
version, hardware change, new license or reproduced result may reopen a decision;
reposting an unchanged announcement should not. A rejection for one project is
not a global rejection of the capability.

## The report a person receives

Keep the first view short: the few decisions that could change current work,
their strongest evidence and the next action. Make detailed observations available
through links. Show screened/deferred/rejected counts without sending a summary
of every post. Set a maximum number of recommendations per report in the profile;
do not schedule messages or notifications without an authorized delivery contract.

Synthetic report shape, for illustration only:

```json
{
  "synthetic": true,
  "candidate": "SYNTHETIC-memory-a@revision-1",
  "profile": "SYNTHETIC-project@version-1",
  "recommendation": "watch",
  "reason": "Reported accelerator latency is not comparable to the CPU target.",
  "source_claim_status": "reported_not_reproduced",
  "target_measurements": null,
  "measurement_reason": "No target trial has run.",
  "next_outcome": "Establish CPU support and license compatibility before a trial.",
  "recheck_trigger": "A supported CPU build or the target runtime changes.",
  "adoption_authorized": false
}
```

Actual decisions need exact permitted evidence references, measured fields and
current scope. A title, confidence label or model-generated narrative is not a
substitute for those references.

## First pilot and its limits

Start with one project profile, one capability family and a small permitted source
batch. Memory systems are an example, not a selected provider or a current product
recommendation. Test the same workflow later on harnesses, model nodes, 3D tools
and motion systems using their own evaluation contracts.

The first pilot should prove that duplicate claims collapse without losing
provenance; incompatible candidates stop before costly work; non-comparable
numbers remain labeled; and any shortlisted trial produces an actual paired
result. Include inaccessible sources, contradictory claims, missing hardware,
failed trials and no-change decisions as acceptance cases.

Measure decision usefulness on fixed cases, missed relevant candidates, false
shortlists, source coverage and human review time alongside compute usage. Model
cost or the number of collected posts alone does not measure success. Source
connectors, a production profile resolver, scheduling, adapters and live trials
remain implementation work. This proposal makes none of them active.
