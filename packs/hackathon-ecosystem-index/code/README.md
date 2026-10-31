# hackathon-ecosystem-index code

Standard-library repository decomposition and hybrid search engine for `packs/hackathon-ecosystem-index`:

- `ecosystem_index.decompose`: decomposes public repository scan metadata and README summaries into typed **Tasks** (`verb` signatures) and **Task Objects** (`noun` signatures) marked `candidate_unverified` with explicit scan provenance.
- `ecosystem_index.search`: indexes decomposed records with Okapi BM25 (`k1=1.5, b=0.75`), scores stack/domain/track/task-category facets, and fuses ranked lists via Reciprocal Rank Fusion (`k=60`).

Run `make check` to compile with `-W error` and execute the unit tests and worked-example recomputation.
