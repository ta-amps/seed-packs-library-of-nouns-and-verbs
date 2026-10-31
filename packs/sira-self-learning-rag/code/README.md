# SIRA self-learning RAG and analogy index (`sira_rag`)

Standard-library Python package for Seed Pack `sira-self-learning-rag` (inspired by Meta SIRA June 2026, RA-RFT, MR-Search and HyperAgents / DGM-H March 2026).

## Modules
- `noun_enricher.py`: `SiraNounEnricher` for offline corpus-discriminative vocabulary, I/O type signatures, capability facets and predictive query expansions.
- `analogy_index.py`: `RaRftAnalogyIndex` for 12 structural problem-isomorphism frames and single-shot cross-domain hybrid RRF retrieval.
- `mr_search_reflector.py`: `MrSearchReflector`, `HermaShimCompiler` (`< 2 ms` deterministic shimming rules) and `DgmHIndependentVerifier` (`proposer != verifier` promotion gate).
- `benchmark.py`: 60-query cross-domain and analogical benchmark across all Seed Packs in `packs/`.

## Verification
```bash
make check
```
