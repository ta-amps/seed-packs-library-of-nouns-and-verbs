# LoRA memory and shimming

## What this pack lets workers do

A collection of nouns and verbs for compiling post-cutoff Task Objects into leakage-checked
parametric-memory LoRA training pairs, routing between prompt/context shimming, weight updates and
hybrid setups, and evaluating pre-registered holdout paired bootstrap promotion gates. In plain
language, nouns are **task objects** (routing policies, promotion gate specs, pinned
standard-library code, schemas and synthetic worked examples) and verbs are **tasks** a worker
claims. Workers turn verified post-cutoff API or schema updates into direct-fact,
supersession-contrast and scope-abstention pairs, verify n-gram disjointness against holdout
prompts, calculate token-cost amortization before training, and gate adapter promotion on paired
bootstrap 95 percent confidence intervals.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Never present a smoke run or compiled SFT dataset as a proven model improvement; enforce holdout 4-gram disjointness; prefer revocable shims when facts churn fast |
| `spec.routing-and-gates` | Amortization thresholds for `prompt_context_shim` vs `lora_weight_update` vs `hybrid_shim_and_lora` and paired bootstrap (`B=1000`) CI promotion floors |
| `rules.pair-compilation` | Direct-recall, supersession-guard and scope-abstention pair generation plus 4-gram Jaccard (`<= 0.35`) holdout check |
| `tool.lora-memory` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.gate-decision` | JSON Schema for a routing and paired-bootstrap holdout gate decision |
| Worked example | Synthetic post-cutoff bundle (`example.post-cutoff-bundle`) and recomputed hybrid routing and gate result (`example.gate-decision`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `route-shim-or-lora` | agent, no model | Choose `prompt_context_shim`, `lora_weight_update` or `hybrid_shim_and_lora` from churn half-life, query volume and token budgets |
| `compile-lora-pairs` | agent, no model | Compile verified post-cutoff Task Objects into direct, supersession and abstention SFT pairs and verify holdout disjointness |
| `evaluate-bootstrap-gate` | agent, no model | Compute seeded paired bootstrap (`B=1000`) 95 percent CIs on target gain, general retention and hallucination ceilings |

## How to use it

Run `make check` in [code/](code/README.md) to compile with warnings treated as errors and verify
pair compilation, holdout disjointness, strategy routing and paired bootstrap promotion gates.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these tasks through Tessera.
- Compiling pairs or passing a synthetic fixture never constitutes a trained or deployed adapter;
  real promotion requires pre-registered holdouts and general-capability retention benchmarks.
- The worked example in `source.json` is synthetic.
