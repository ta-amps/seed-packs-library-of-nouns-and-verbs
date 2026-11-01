# dora-spinquant-and-adapter-merging (`adapter_quant_and_merge`)

Standard-library implementation of grid-governed Walsh-Hadamard outlier rotation quantization, weight-decomposed low-rank adaptation analysis and subspace interference routing:
- `FastWalshHadamardOutlierRotator`: pure-Python Sylvester/Walsh-Hadamard orthogonal rotation `W' = (W * s) @ H_d / sqrt(d)` with deterministic Rademacher sign flips, heavy-tailed outlier kurtosis/max-to-RMS suppression and symmetric low-bit (`4-bit`) uniform quantization MSE evaluation.
- `WeightDecomposedLoraAnalyzer`: computes `DoRA` directional (`V / ||V||_col`) vs magnitude (`m`) update decomposition from `(B @ A)` low-rank deltas and measures directional-to-magnitude learning ratios.
- `SubspaceInterferenceAndMergeRouter`: computes flattened adapter Frobenius cosine similarity, `TIES` trim-elect-merge sign-conflict density and routes between `ties_static_merge` and `dynamic_co_resident_switch`.
- `ZeroHardcodedValuesAstGate` and `scan_directory_for_hardcoded_values`: mechanical Python AST scanner verifying zero non-identity inline numeric literals across `adapter_quant_and_merge/`.

Run checks:
```bash
make check
```
