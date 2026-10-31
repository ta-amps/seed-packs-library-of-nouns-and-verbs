# lora-memory-and-shimming code

Standard-library dataset compiler, strategy router and promotion gate evaluator for `packs/lora-memory-and-shimming`:

- `lora_memory.compiler`: compiles verified post-cutoff Task Objects into direct-recall, supersession-contrast and scope-abstention SFT pairs, and checks 4-gram Jaccard disjointness against pre-registered holdouts.
- `lora_memory.router`: routes adaptation requests across `prompt_context_shim`, `lora_weight_update` and `hybrid_shim_and_lora` using churn half-life, query frequency, context token cost and instant-revocation needs.
- `lora_memory.gates`: runs seeded paired bootstrap (`B=1000`) 95 percent confidence intervals on pre-registered holdout gains, general-capability retention and hallucination ceilings.

Run `make check` to compile with `-W error` and execute the unit tests and worked-example recomputation.
