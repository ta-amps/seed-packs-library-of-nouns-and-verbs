# Hybrid retrieval context knapsack

## What this pack lets workers do

A collection of nouns and verbs for fusing Okapi BM25 and dense cosine rankings via Reciprocal Rank
Fusion (`k=60`), stripping untrusted prompt-injection directives, pruning MinHash near-duplicates and
packing context into a strict token budget via 0/1 dynamic-programming knapsack. In plain language,
nouns are **task objects** (fusion and knapsack specs, sanitization rules, pinned standard-library
code, schemas and made-up worked examples) and verbs are **tasks** a worker claims. Instead of
blindly concatenating top-k retrieved passages until the prompt overflows or repeats itself, workers
fuse lexical and dense signals, redact untrusted directives, drop near-duplicate shingles and solve
an exact token-budget knapsack with overlap penalties.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Redact untrusted directives before packing; enforce strict `total_tokens <= token_budget`; prune MinHash near-duplicates and discount redundant overlap |
| `spec.rrf-and-knapsack` | Okapi BM25 (`k1=1.5, b=0.75`), RRF (`k=60`), 64-permutation 3-shingle MinHash (`0.75`) and exact 0/1 knapsack (`redundancy_lambda=0.35`) parameters |
| `rules.sanitization-and-minhash` | Zero-call untrusted directive redaction rules and universal-hash MinHash near-duplicate filter |
| `tool.context-knapsack` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.packed-context` | JSON Schema for a ranked, sanitized and budget-packed context receipt |
| Worked example | Made-up 5-chunk candidate set (`example.retrieval-candidates`) and recomputed packed receipt (`example.packed-context`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `fuse-hybrid-rrf` | agent, no model | Score chunks with Okapi BM25 and dense cosine similarity and fuse ranks with RRF (`k=60`) |
| `sanitize-and-dedup-chunks` | agent, no model | Strip untrusted prompt-injection directives and prune 64-permutation MinHash near-duplicates |
| `pack-token-knapsack` | agent, no model | Discount overlap and solve exact 0/1 dynamic-programming knapsack under `token_budget` |

## How to use it

Run `make check` in [code/](code/README.md) to compile with warnings treated as errors and verify RRF
fusion, MinHash deduplication, prompt-injection stripping and exact 0/1 knapsack packing.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these tasks through Tessera.
- Heuristic directive stripping is one defense layer and never replaces strict tool-permission
  boundaries or capability sandboxing.
- The worked example in `source.json` is made-up.
