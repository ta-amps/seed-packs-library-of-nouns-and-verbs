# probabilistic-filters-and-sketches (`probabilistic_sketches`)

Standard-library implementation of grid-governed probabilistic filters, locality-sensitive hashing expanders, and streaming sketches:
- `BlockedBloomFilter`: cache-line partitioned bitset using Kirsch-Mitzenmacher double hashing (`h_i = h1 + i * h2`) with union combination and zero false negatives.
- `CuckooFilter`: bucketized fingerprint filter with partial-key cuckoo hashing (`i2 = i1 ^ hash(fp)`) supporting `insert`, `contains`, and `O(1)` `delete`.
- `StaticXorFingerprintFilter`: deterministic 3-wise peeling-order Xor fingerprint filter (`table[h0] ^ table[h1] ^ table[h2] == fp`) at ~9-10 bits/key.
- `MultiProbeSimHashLshExpander`: 128-bit 8-band SimHash multi-probe key expander (8 exact + 128 1-bit + budgeted 2-bit probes) plus `benchmark_simhash_recall`.
- `MinHashLshDecontaminator`: deterministic k-word shingle MinHash + banded LSH holdout contamination detector.
- `ConservativeCountMinHeavyKeeperHll`: conservative-update Count-Min Sketch, HeavyKeeper exponential-decay top-K tracker, and HyperLogLog cardinality estimator.
- `ZeroHardcodedValuesAstGate`: mechanical Python AST scanner verifying zero non-identity inline numeric literals across `probabilistic_sketches/`.

Run checks:
```bash
make check
```
