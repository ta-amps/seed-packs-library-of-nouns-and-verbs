# Hackathon ecosystem index

## What this pack lets workers do

A collection of nouns and verbs for decomposing public AI repository metadata and READMEs into
searchable **Tasks** (`verb` signatures) and **Task Objects** (`noun` signatures) and serving
hybrid Okapi BM25 plus facet and stack Reciprocal Rank Fusion (`k=60`) retrieval. In plain
language, nouns are **task objects** (decomposition rules, RRF search specs, pinned
standard-library code, schemas and synthetic catalog examples) and verbs are **tasks** a worker
claims. Workers ingest read-only repository scan records, map entrypoints and artifacts into
unverified candidate task and task-object signatures, build a hybrid index, and retrieve projects
matching both free-text queries and structured stack or domain facets.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Mark all decomposed repository capabilities `candidate_unverified`; record explicit scan provenance; never treat a README claim as verified execution |
| `spec.decomposition-and-rrf` | Mapping from public repository entrypoints and artifacts to Tessera verb/noun categories plus Okapi BM25 (`k1=1.5, b=0.75`) and RRF (`k=60`) parameters |
| `tool.ecosystem-index` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.catalog-record` | JSON Schema for a decomposed repository record (`repo`, `track`, `domain`, `meta_stack`, `tasks`, `task_objects`, `summary`, `provenance`) |
| `template.search-response` | JSON Schema for hybrid BM25 + facet RRF (`k=60`) ranked search results |
| Worked example | Synthetic 4-repository scan (`example.raw-repo-scans`) and recomputed RRF search output (`example.search-results`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `decompose-repo-catalog` | agent, no model | Convert public repository scan metadata and READMEs into `candidate_unverified` Task and Task-Object records |
| `verify-catalog-hygiene` | agent, no model | Check schema conformance, provenance tags and absence of unverified admission claims across all catalog rows |
| `search-ecosystem-rrf` | agent, no model | Run Okapi BM25 + stack/domain/verb-category facet scoring fused via Reciprocal Rank Fusion (`k=60`) |

## How to use it

Run `make check` in [code/](code/README.md) to compile with warnings treated as errors and verify
repository decomposition, BM25 indexing, RRF (`k=60`) fusion and the worked example.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these tasks through Tessera.
- Decomposed `tasks` and `task_objects` reflect static metadata and README scans
  (`candidate_unverified`), never sandboxed execution or security endorsement of third-party code.
- The worked example in `source.json` is synthetic.
