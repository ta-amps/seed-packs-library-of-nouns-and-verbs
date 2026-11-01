# Coconut latent and thought budget routing

## What this pack lets workers do

A collection of nouns and verbs for routing reasoning tasks across four compute regimes, compressing verbose multi-turn traces into continuous latent state plus invariant checkpoints and halting repetitive overthinking cycles. Workers route tasks across `zero_step_direct`, `fast_sketch`, `compressed_state_checkpoint` and `full_deliberative_verify`, shed verbose chain-of-thought prose by more than `3x` while retaining `100%` of binding constraints, open obligations and SHA-256 digests and halt cyclic paraphrase loops early.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Require `100%` recall on binding constraints, unresolved obligations and SHA-256 digests, clamp budgets to grid ceilings and forbid inline magic literals |
| `spec.coconut-latent-and-budget-grid` | Four reasoning regimes, continuous latent sketch dimensions, `3.0x` minimum compression target and invariant checkpoint fields |
| `rules.regime-routing-and-stagnation-halt` | Zero-model Shannon ambiguity entropy equation, signed feature-hash latent projection and stagnation loop predicate |
| `tool.thought-budget-routing` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.thought-budget-routing-receipt` | JSON Schema for regime maps, token savings, compression ratios, invariant recall and loop-halt metrics |
| Worked example | Five tasks + verbose and looping traces (`example.thought-budget-routing-bundle`) and recomputed receipt (`example.thought-budget-routing-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `route-adaptive-reasoning-budget` | agent, no model | Route tasks across 4 compute regimes under grid-clamped token and latency budgets |
| `compress-latent-checkpoint-and-detect-loops` | agent, no model | Compress verbose multi-turn traces (`>3x`) into invariant + latent checkpoints and halt cyclic loops |
| `verify-invariant-recall-and-ast-gate` | agent, no model | Recompute receipts with a `distinct_reviewer` rule and verify zero AST magic-literal violations |

## Worked example

`python3 -m thought_budget_routing --bundle BUNDLE.json` routes `5` tasks across all `4` regimes (`55%` token savings with latency-clamped checkpoint downshift), compresses a `123`-token 3-turn trace into `20` checkpoint tokens (`6.15x` ratio, `1.0` constraint/obligation/hash recall) and halts an overthinking loop at step `3`.

## Acceptance checks

- `make -C packs/coconut-latent-and-thought-budget-routing/code check` passes all unit tests and `scan_directory_for_hardcoded_values == []`.
- Compression exceeds `3.0x` with `1.0` recall on binding constraints, open obligations and 64-character SHA-256 digests.

## Contents

- `source.json`, `nouns.json`, `verbs.json`, `manifest.json` and tested Python package in [code/](code/README.md).

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through a work-engine.
- Continuous latent state vectors here are deterministic signed feature-hash sketches for state handoff and loop detection, not learned hidden-state activations inside transformer weights.
- Unstructured obligations lacking relational syntax or `CONSTRAINT:`/`OBLIGATION:` tags must be supplied explicitly in turn dicts.
