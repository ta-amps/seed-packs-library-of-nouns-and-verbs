# coconut-latent-and-thought-budget-routing (`thought_budget_routing`)

Standard-library Python 3.10+ implementation of continuous latent state sketching, adaptive reasoning budget routing and overthinking loop termination:

- `AdaptiveReasoningBudgetRouter`: routes tasks across `zero_step_direct`, `fast_sketch`, `compressed_state_checkpoint` and `full_deliberative_verify` using complexity features, Shannon ambiguity entropy and token/latency budget bounds from `default_grid_spec.json`.
- `LatentStateSketchCompressor`: compresses verbose multi-turn reasoning traces into compact typed invariant checkpoints + normalized continuous latent state vectors (`>3x` prose token reduction with `1.0` recall on binding constraints, open obligations and verified SHA-256 digests).
- `OverthinkingLoopDetector`: detects repetitive reasoning cycles via consecutive latent-vector cosine similarity, shingle overlap and invariant stagnation.
- `ZeroHardcodedValuesAstGate`: enforces zero inline magic numeric literals across all operational modules.

## Run tests and CLI

```bash
make check
python3 -m thought_budget_routing --bundle BUNDLE.json
```
