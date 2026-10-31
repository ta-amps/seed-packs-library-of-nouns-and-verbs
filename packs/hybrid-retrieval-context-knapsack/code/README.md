# hybrid-retrieval-context-knapsack code

Standard-library hybrid retrieval, deduplication, sanitization and token-budget packing for `packs/hybrid-retrieval-context-knapsack`:

- `context_knapsack.fusion`: Okapi BM25 + dense cosine similarity fused via Reciprocal Rank Fusion (`k=60`).
- `context_knapsack.dedup_and_sanitize`: 64-permutation universal-hash MinHash near-duplicate pruning plus untrusted prompt-injection directive stripping.
- `context_knapsack.knapsack`: exact 0/1 dynamic-programming knapsack solver and redundancy-penalized token-budget context packer.

Run `make check` to compile with `-W error` and execute the unit tests and worked-example recomputation.
