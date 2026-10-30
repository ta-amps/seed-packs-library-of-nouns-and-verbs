# Authored Example Recipes

Each JSON file in this folder is a declarative `RecipeSpec` referencing only prewritten verified `node_id`s from `code_composition/seed_nodes.py` -- zero inline Python code.

The wheel ships these same files as package data under `code_composition/recipes/`, so an installed package and a checkout load identical recipes. A missing or empty catalog is an error; the loader never substitutes a built-in recipe.

| Recipe file |Topology | Nodes wired | What it demonstrates |
|---|---|---|---|
| [tabular-anomaly-triage.json](tabular-anomaly-triage.json) | 13-step multi-root join DAG | CSV ingest, schema contract, dedupe, median impute, quantile winsorize, ratio, rolling z-score, logistic risk, threshold gate, keyed enrich join, group summary, Markdown report | Dual CSV entry inputs (`ingest_events.raw_csv`, `ingest_owners.raw_csv`) + keyed lookup join |
| [document-signal-digest.json](document-signal-digest.json) | 7-step text-to-table DAG | Whitespace normalize, regex extract, last-write dedupe, weighted keyword score, threshold gate, group summary, Markdown report | Turning unstructured incident text into typed `records` and a GFM digest |
| [ab-candidate-selection.json](ab-candidate-selection.json) | 12-step diamond evaluation DAG | CSV ingest, dedupe, impute, ratio, SHA-256 holdout split, parallel arms A & B (`model.linear_risk_score` + `eval.binary_metrics`), empirical-Bayes `eval.shrinkage_select`, cohort summary, Markdown report | Diamond fan-out/fan-in + sub-DAG prefix reuse across candidate challenger recipes |

## Compile & Run Any Recipe

```bash
uv run code-composition compile examples/recipes/ab-candidate-selection.json --emit-python
uv run code-composition run examples/recipes/ab-candidate-selection.json --verify-python
```
