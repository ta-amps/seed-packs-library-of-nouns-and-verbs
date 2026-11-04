# Probabilistic filters and sketches

## What this pack lets workers do

A collection of nouns and verbs for cache-line blocked Bloom filters, deletable Cuckoo filters, static Xor filters, multi-probe LSH and streaming sketches. Workers use grid-governed probabilistic data structures to shield expensive reads with `BlockedBloomFilter`, delete gone `404` spider targets in `O(1)` with `CuckooFilter`, pack static edges into ~9-10 bits per key with `StaticXorFingerprintFilter`, recover near-duplicate recall across 128-bit SimHash bands with `MultiProbeSimHashLshExpander`, screen holdout contamination with `MinHashLshDecontaminator` and summarize skewed streams with `ConservativeCountMinHeavyKeeperHll`.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Require `CuckooFilter` when `O(1)` deletion is enabled, forbid deleting uninserted keys and enforce zero inline magic numbers via `ZeroHardcodedValuesAstGate` |
| `spec.filter-lsh-and-sketch-grid` | Bit-width, band-count, probe-key (`8` exact, `136` 1-bit) and Xor bits-per-key invariants |
| `rules.multiprobe-recall-and-sketch-selection` | Zero-model regime mapping across read shields, mutable spider frontiers, static edge tables, LSH lookup and streaming sketches |
| `tool.probabilistic-sketches` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.probabilistic-sketches-receipt` | JSON Schema for filter false-negative checks, Cuckoo deletion, Xor bits/key, SimHash recall and sketch summaries |
| Worked example | Made-up filter, LSH and sketch bundle (`example.probabilistic-sketches-bundle`) and recomputed receipt (`example.probabilistic-sketches-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `build-and-query-membership-filters` | agent, no model | Construct `BlockedBloomFilter`, `CuckooFilter` and `StaticXorFingerprintFilter` instances from grid specs and verify zero false negatives |
| `expand-multiprobe-lsh-and-decontaminate` | agent, no model | Expand 128-bit SimHash multi-probe keys across Hamming distances and screen candidate texts against holdouts with MinHash LSH |
| `verify-sketch-bounds-and-ast-conformance` | agent, no model | Verify `ConservativeCountMinHeavyKeeperHll` stream summaries, recompute receipts with a `distinct_reviewer` rule and run `ZeroHardcodedValuesAstGate` |

## How to use it

Run `make check` in [code/](code/README.md) to execute unit tests covering Kirsch-Mitzenmacher `BlockedBloomFilter` unions, `CuckooFilter` `O(1)` deletions and compact serialization, `StaticXorFingerprintFilter` peeling, 128-bit SimHash multi-probe recall curves, MinHash holdout decontamination, `ConservativeCountMinHeavyKeeperHll` accuracy, `ZeroHardcodedValuesAstGate` self-scanning and worked-example receipt recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through the work-engine.
- Probabilistic filters provide one-sided membership guarantees on static or properly maintained sets; positive hits still require exact downstream verification when false positives matter.
- Deleting a key that was never inserted into a `CuckooFilter` can evict a colliding live fingerprint, so `O(1)` deletion applies strictly to previously inserted targets.
