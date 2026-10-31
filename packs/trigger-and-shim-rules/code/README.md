# trigger-and-shim-rules (`trigger_shim`)

Standard-library implementation of:
- `ThreeTierTriggerEngine`: trigram bitmask fast-reject, keyword and anti-trigger veto rules, sparse stem + char n-gram + concept-synonym TF cosine with Role-Filler Frame isomorphism bonus, and verified governance lens checks.
- `ConversationDedupAndSubmodularKnapsack`: `[PROVISION: <id>@v<n>]` marker deduplication and redundancy-penalized 0/1 integer DP context knapsack.
- `HarnessTaxAndThreeRegimeRouter`: step-slicing `HarnessTax` break-even calculator and 3-regime + hybrid Shim/Code/LoRA router.
- `WhichFitsCompatibilityMatcher`: privacy-aware Pareto compatibility matcher (`recommend_which_fits`).

Run checks:
```bash
make check
```
