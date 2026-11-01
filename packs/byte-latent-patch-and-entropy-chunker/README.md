# Byte latent patch and entropy chunker

## What this pack lets workers do

A collection of nouns and verbs for segmenting byte streams into lossless variable-length patches at conditional Shannon entropy spikes and allocating downstream compute proportional to cumulative information surprise. Workers group predictable boilerplate stretches into long patches (`up to max_patch_bytes`), slice high-surprise regions into fine-grained patches (`down to min_patch_bytes`), concentrate inspection budgets on high-information patches and re-synchronize boundaries after byte insertions.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Require exact byte-for-byte stream reconstruction within `[min_patch_bytes, max_patch_bytes]`, surprise-weighted budget apportionment and zero inline magic literals |
| `spec.dynamic-byte-entropy-patching-grid` | Conditional byte Shannon entropy predicates, 256-byte Dirichlet prior smoothing and perturbation re-synchronization metrics |
| `rules.entropy-spike-cut-and-hamilton-apportionment` | Zero-model predictive byte entropy equation, pointwise surprise `-log2 P(b_t | ctx)` and Hamilton apportionment rules |
| `tool.entropy-byte-patcher` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.entropy-byte-patcher-receipt` | JSON Schema for variable patch stats, lossless check, surprise budget focus gain and boundary resync gain |
| Worked example | Calibration motifs + clean/corrupted byte streams (`example.entropy-byte-patcher-bundle`) and recomputed receipt (`example.entropy-byte-patcher-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `segment-dynamic-byte-entropy-patches` | agent, no model | Segment raw byte streams into lossless variable-length patches at conditional entropy spikes |
| `allocate-surprise-proportional-patch-budget` | agent, no model | Apportion compute slots by cumulative surprise and benchmark shift re-synchronization vs fixed stride |
| `verify-lossless-patching-and-ast-gate` | agent, no model | Recompute receipts with a `distinct_reviewer` rule and verify zero AST magic-literal violations |

## Worked example

`python3 -m entropy_byte_patcher --bundle BUNDLE.json` segments a `111`-byte mixed-entropy stream into `9` lossless patches (`4..30` bytes), allocates `90.62%` of inspection slots to high-entropy patches (`+68.74%` focus gain over raw byte-length weighting) and preserves `77.78%` of patches after a 1-byte prefix insertion vs `14.29%` for `8`-byte fixed-stride chunking (`+63.49%` resync gain).

## Acceptance checks

- `make -C packs/byte-latent-patch-and-entropy-chunker/code check` passes all unit tests and `scan_directory_for_hardcoded_values == []`.
- Concatenated patch hex bytes reconstruct the exact input stream and outperform fixed-stride chunking under prefix insertions.

## Contents

- `source.json`, `nouns.json`, `verbs.json`, `manifest.json` and tested Python package in [code/](code/README.md).

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through a work-engine.
- Conditional byte entropy accuracy depends on either representative calibration byte motifs or sufficient stream length for online causal n-gram adaptation.
- Purely encrypted or compressed uniform-random byte streams exhibit uniformly maximal entropy (`~8` bits/byte) and fall back to fine-grained patches.
