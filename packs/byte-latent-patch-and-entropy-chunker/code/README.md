# byte-latent-patch-and-entropy-chunker (`entropy_byte_patcher`)

Standard-library Python 3.10+ implementation of dynamic byte-entropy stream patching and surprise-proportional compute allocation:

- `DynamicByteEntropyPatcher`: computes rolling conditional byte Shannon entropy `H(b_t | context)` and pointwise surprise `-log2 P(b_t | context)`, segmenting byte streams losslessly into variable-length patches whenever `H_t > global_entropy_threshold` or `H_t - H_{t-1} > delta_spike_threshold` within `[min_patch_bytes, max_patch_bytes]`.
- `SurpriseProportionalBudgetAllocator`: apportions downstream inspection/context budgets across patches proportional to cumulative information surprise rather than raw byte length, and benchmarks perturbation re-synchronization against fixed-stride chunking.
- `ZeroHardcodedValuesAstGate`: enforces zero inline magic numeric literals across all operational modules.

## Run tests and CLI

```bash
make check
python3 -m entropy_byte_patcher --bundle BUNDLE.json
```
