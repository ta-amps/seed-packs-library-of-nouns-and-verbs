# Trigger and shim rules

## What this pack lets workers do

A collection of nouns and verbs for three-tier trigger compilation with Role-Filler Frame isomorphism, conversation-aware submodular context-shim knapsacks, step-slicing HarnessTax break-even routing and privacy-safe compatibility matching.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Enforce Tier-1 `exclude_keywords` anti-trigger vetoes, block `quarantined` provisions at Tier 3 and refuse contributor-training entries on non-public data |
| `spec.trigger-knapsack-and-regime-equations` | Three-tier trigger equations, submodular overlap penalty, `(k - 1) * P / (k * P + C)` HarnessTax formula and four adaptation regimes |
| `rules.which-fits-and-dedup-markers` | `[PROVISION: <id>@v<n>]` conversation deduplication modes (`once_per_conversation`, `every_turn`, `on_error_signature`) and privacy tiers |
| `tool.trigger-shim` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.trigger-shim-receipt` | JSON Schema for trigger match/veto maps, packed provision tokens, HarnessTax break-even, regime choices and Pareto winners |
| Worked example | Trigger, knapsack, router and matcher bundle (`example.trigger-shim-bundle`) and recomputed receipt (`example.trigger-shim-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `evaluate-three-tier-triggers` | agent, no model | Filter rules via trigram bitmasks, anti-trigger vetoes, Role-Filler Frame cosine bonus and verified governance checks |
| `pack-dedup-shim-knapsack` | agent, no model | Deduplicate `[PROVISION: <id>@v<n>]` markers across turns and solve scaled integer 0/1 context knapsacks |
| `route-regime-and-match-which-fits` | agent, no model | Compute step-slicing HarnessTax break-even rates, route Shim/Code/LoRA regimes and rank privacy-safe Pareto winners |

## How to use it

Run `make check` in [code/](code/README.md) to execute unit tests covering `ZeroHardcodedValuesAstGate`, Role-Filler Frame trigger matching, conversation deduplication knapsacks, `HarnessTax` 4-regime routing, `recommend_which_fits` privacy filtering and worked-example receipt recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through a work-engine.
- Deterministic trigger, knapsack and routing evaluations run offline without network calls or live model weight updates.
- Compatibility scores rank declared entry parameters; accountable workers and reviewers still verify held-out task outcomes before promotion.
