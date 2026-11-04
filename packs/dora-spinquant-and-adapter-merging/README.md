# DoRA, SpinQuant and adapter merging

## What this pack lets workers do

A collection of nouns and verbs for Walsh-Hadamard outlier rotation quantization, weight-decomposed low-rank adapter analysis and subspace interference routing across static fusion and co-resident switching. Workers disperse concentrated channel outliers with `FastWalshHadamardOutlierRotator` (`W' = (W * diag(s)) @ H_d / sqrt(d)`) prior to symmetric `4-bit` uniform quantization, decompose low-rank `(B @ A)` updates into unit column directions and Euclidean magnitudes with `WeightDecomposedLoraAnalyzer`, and route adapter pools between `ties_static_merge` and `dynamic_co_resident_switch` with `SubspaceInterferenceAndMergeRouter`.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Route high-interference or sign-conflicting adapters to `dynamic_co_resident_switch` and enforce zero inline magic scalars via `ZeroHardcodedValuesAstGate` |
| `spec.spinquant-dora-ties-grid` | `4-bit` quantization, `64`-channel Walsh-Hadamard rotation, `DoRA` column decomposition and `TIES` interference invariants |
| `rules.outlier-rotation-and-interference-routing` | Zero-model mathematical formulas for orthogonal Rademacher-Hadamard rotation, `DoRA` composition and static-vs-dynamic adapter routing |
| `tool.adapter-quant-and-merge` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.adapter-quant-merge-receipt` | JSON Schema for max-to-RMS/kurtosis suppression, `4-bit` quantization MSE reduction, `DoRA` ratios and routing decisions |
| Worked example | Heavy-tailed `64`-channel and multi-adapter fixture (`example.adapter-quant-merge-bundle`) and recomputed receipt (`example.adapter-quant-merge-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `rotate-outliers-and-quantize-weights` | agent, no model | Apply Sylvester Walsh-Hadamard rotation with deterministic sign flips and measure `4-bit` reconstruction MSE vs unrotated weights |
| `decompose-dora-and-route-adapter-subspaces` | agent, no model | Compute `DoRA` directional vs magnitude update ratios and route adapters between `ties_static_merge` and `dynamic_co_resident_switch` |
| `verify-quantization-merge-and-ast-gate` | agent, no model | Independently verify `4-bit` MSE reduction, routing receipts (`distinct_reviewer`) and `ZeroHardcodedValuesAstGate` conformance |

## Worked example

On the `16 x 64` heavy-tailed made-up channel matrix (`outlier_scale = 32.0`), Walsh-Hadamard rotation reduces `max_abs_to_rms` from `12.578755` to `2.166179`, collapses excess kurtosis from `103.842906` to `-1.034782`, and cuts symmetric `4-bit` quantization MSE by `10.039322x` (`0.231252` to `0.023035`), while routing orthogonal adapters (`cosine = 0.0`) to `ties_static_merge` and sign-conflicting adapters (`conflict = 1.0`) to `dynamic_co_resident_switch`.

## Acceptance checks

Run `make check` in [code/](code/README.md) to verify Walsh-Hadamard orthogonality (`inverse_rotate(rotate(W)) == W`), `> 10x` `4-bit` MSE reduction, `DoRA` column-norm synthesis, `TIES` sign-conflict routing, `scan_directory_for_hardcoded_values == []` and exact CLI receipt recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through the work-engine.
- Sylvester Walsh-Hadamard transforms require power-of-two channel dimensions (or explicit zero-padding prior to rotation) and matching sign-flip seeds on inverse reconstruction.
- Static `TIES` fusion remains lossy whenever task adapters share overlapping subspace directions with opposing signs; high-interference pairs must stay isolated under `dynamic_co_resident_switch`.

## Contents

- `README.md`, `source.json` and generated proposal payloads (`nouns.json`, `verbs.json`, `manifest.json`)
- [code/](code/README.md): `adapter_quant_and_merge` standard-library Python package and `unittest` suite
