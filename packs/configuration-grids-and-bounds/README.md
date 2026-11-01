# Configuration grids and bounds

## What this pack lets workers do

A collection of nouns and verbs for declaring multi-dimensional configuration settings grids (`NodeGrid`) with typed axes (`integer_range`, `choice`, `boolean`) and cross-parameter constraints, clamping runtime values within `ParameterBounds`, tracking every cell lifecycle through `GridLedger` (`represented` through `promoted`), selecting verified cells by contextual workload regime (`OperationCostLedger`), automatically expanding saturated parameter bounds into a new grid generation, and scanning operational Python ASTs (`ZeroHardcodedValuesAstGate`) so hardcoded magic numbers fail closed.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Forbid inline magic numeric literals outside identity constants (`-1`, `0`, `1`); forbid promoting unverified grid cells; require `distinct_reviewer` before promoting a regime winner |
| `spec.node-grid-and-bounds` | Declarative axis schema (`integer_range`, `choice`, `boolean`), cross-parameter constraint clauses, runtime clamping rules and saturation expansion factors |
| `rules.grid-ledger-and-ast-gate` | Seven-stage `GridLedger` transition rules, contextual `OperationCostLedger` regime resolution and Python `ast` magic-number gate exemptions |
| `tool.config-grids` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.grid-evaluation-receipt` | JSON Schema for constrained cell counts, lifecycle states, regime winner selection, auto-expanded generation axis bounds and AST gate results |
| Worked example | Workload-regime search and AST audit bundle (`example.grid-evaluation-bundle`) and recomputed receipt (`example.grid-evaluation-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `compile-grid-and-clamp-bounds` | agent, no model | Validate `NodeGrid` axes and cross-parameter constraints, enumerate applicable cells and clamp proposed coordinates inside `ParameterBounds` |
| `evaluate-regime-and-expand-bounds` | agent, no model | Record `OperationCostLedger` observations, select contextual regime winners and auto-expand saturated axis boundaries into a next-generation grid |
| `review-ast-gate-and-cell-promotion` | agent, no model | Run `ZeroHardcodedValuesAstGate` on operational Python files and verify independent `distinct_reviewer` evidence before promoting a verified cell |

## How to use it

Run `make check` in [code/](code/README.md) to run unit tests covering cross-parameter constraint pruning, `GridLedger` lifecycle enforcement, contextual regime winner selection, boundary auto-expansion, self-check `ZeroHardcodedValuesAstGate` scanning and worked-example receipt recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through Tessera.
- Offline grid compilation, regime selection and Python AST scanning run deterministically without network access or live service mutation.
- Boundary auto-expansion proposes next-generation parameter ranges from observed saturation; accountable workers and reviewers still verify new cells on held-out workloads before promotion.
