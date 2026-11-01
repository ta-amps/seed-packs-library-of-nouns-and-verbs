# FAISS IVF-PQ and ANN index cascade

## What this pack lets workers do

A collection of nouns and verbs for k-means++ Voronoi inverted-file partitioning, residual uint8 product quantization, asymmetric distance lookup tables and exact top-R reranking. Workers partition dense `R^D` vectors into `nlist` Voronoi cells via deterministic k-means++, encode residuals into `M`-byte `uint8` product-quantization (`PQ`) codes with `ProductQuantizedIvfIndex`, query `nprobe` cells via `M x K_sub` Asymmetric Distance Computation (`ADC`) lookup tables plus exact top-`R` reranking, and benchmark byte compression vs `Recall@k` across `fast_compact` and `high_recall` grid cells.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Enforce `dim % subspaces_m == 0`, `uint8` codebook bounds (`K_sub <= 256`), `nprobe <= nlist` and zero inline magic scalars via `ZeroHardcodedValuesAstGate` |
| `spec.ivf-pq-and-adc-cascade-grid` | `ProductQuantizedIvfIndex` parameters and `fast_compact` vs `high_recall` `NodeGrid` regimes |
| `rules.residual-pq-and-adc-lookup` | Zero-model residual PQ decomposition, `M x K_sub` `ADC` lookup sum and float64/float32 byte compression formulas |
| `tool.ivf-pq-cascade` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.ivf-pq-cascade-receipt` | JSON Schema for `PQ` bytes/vector, compression ratios, `ADC` scan counts, exact reranks and `Recall@k` |
| Worked example | Seeded `192`-vector `32-D` cluster benchmark (`example.ivf-pq-cascade-bundle`) and recomputed receipt (`example.ivf-pq-cascade-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `fit-ivf-pq-voronoi-and-residual-codebooks` | agent, no model | Train `nlist` Voronoi centroids and `M` residual `PQ` sub-codebooks via k-means++ and pack `uint8` codes |
| `benchmark-adc-and-exact-rerank-regimes` | agent, no model | Run `ADC` lookup tables + optional exact top-`R` reranking across `fast_compact` and `high_recall` regimes |
| `verify-ivf-pq-compression-and-recall-receipt` | agent, no model | Independently verify compression ratios, `Recall@k` (`distinct_reviewer`) and `ZeroHardcodedValuesAstGate` |

## Worked example

On the `192`-vector `32-D` corpus (`256` bytes/vector in `float64`, `128` bytes/vector in `float32`), `fast_compact` (`M = 4`, `nprobe = 1`, `rerank_top_r = 0`) stores `4` `uint8` bytes/vector (`64.0x` compression vs `float64`, `32.0x` vs `float32`), scanning `24.0` candidates/query with `0` exact dense evaluations (`Recall@5 = 0.533333`). Switching to `high_recall` (`M = 8`, `nprobe = 4`, `rerank_top_r = 20`) stores `8` `uint8` bytes/vector (`32.0x` vs `float64`, `16.0x` vs `float32`), evaluates exact distances on only `20.0` shortlisted candidates (`10.4%` of corpus) and reaches `Recall@5 = 1.0`.

## Acceptance checks

Run `make check` in [code/](code/README.md) to verify k-means++ determinism, compact `bytes` `uint8` PQ storage, `ADC` lookup accuracy, exact top-`R` rerank `Recall@k` gains, `NodeGrid` constraint enforcement, `scan_directory_for_hardcoded_values == []` and CLI receipt recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through the work-engine.
- Pure-Python standard-library loops target reference verification, small-to-medium local caches and cascade regime sizing rather than SIMD/GPU billion-scale throughput.
- Exact top-`R` reranking requires retaining or fetching unquantized vectors for the `R` shortlisted candidates.

## Contents

- `README.md`, `source.json` and generated proposal payloads (`nouns.json`, `verbs.json`, `manifest.json`)
- [code/](code/README.md): `ivf_pq_cascade` standard-library Python package and `unittest` suite
