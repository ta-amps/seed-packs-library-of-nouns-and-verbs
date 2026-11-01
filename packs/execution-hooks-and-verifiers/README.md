# Execution hooks and verifiers

## What this pack lets workers do

A collection of nouns and verbs for compiling four-stage portable execution hooks across coding harnesses, enforcing pre-tool safety and spend guards, running topological pre-submit verifier DAGs, auditing verifier mutation sensitivity and extracting dead-end negative tombstones.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Enforce `disable_bypass_permissions=True`, block secret reads, destructive shell flags and unapproved spend, require distinct non-anonymous principals and gate verifiers on synthetic mutations |
| `spec.four-stage-hooks-and-verifier-dag` | Four lifecycle phases (`pre_claim`, `pre_tool`, `post_step`, `pre_submit`), four harnesses and five built-in DAG verifier types |
| `rules.mutation-gate-and-tombstone-normalization` | Checks-of-Checks `trusted`, `revise` and `reject` thresholds plus normalized `negative_tombstone` hashing |
| `tool.hooks-verifiers` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.hooks-verifiers-receipt` | JSON Schema for compiled harnesses, `pre_tool` verdicts, Verifier DAG outcomes, mutation audit bands and tombstone ID |
| Worked example | Hook, guard, Verifier DAG and mutation suite (`example.hooks-verifiers-bundle`) and recomputed receipt (`example.hooks-verifiers-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `compile-portable-hooks-and-guard-tools` | agent, no model | Compile 4-stage hook specs for `claude_code`, `muse_code`, `opencode` and `pi_coding_agent` and classify `pre_tool` calls |
| `execute-verifier-dag-and-tombstones` | agent, no model | Run topological `pre_submit` Verifier DAGs and emit normalized `negative_tombstone` dead-end signatures on failure |
| `audit-verifier-mutation-sensitivity` | agent, no model | Test verifiers against clean positive twins and mutated negatives to classify `trusted`, `revise` or `reject` |

## How to use it

Run `make check` in [code/](code/README.md) to execute unit tests covering `ZeroHardcodedValuesAstGate`, 4-harness hook compilation, `pre_tool` safety/CSP/storage/spend enforcement, topological Verifier DAG execution, Checks-of-Checks mutation audits, tombstone normalization and worked-example receipt recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through a work-engine.
- Hook compilation and verifier DAG execution run deterministically offline without modifying host harness files or invoking external services.
- Deterministic verifiers enforce structural, cryptographic and statistical contracts; human-gated boundaries still require accountable human review.
