# velocity-signal-radar

Zero-dependency Python 3.10+ standard-library reference package for `artifact-velocity-and-curator-radar`.

## Capabilities

- **Grid-governed parameterization (`grid_config.py`)**: `ParameterBounds`, `NodeParameter`, `NodeGrid`, `GridLedger` (`represented` -> `applicable` -> `proposed` -> `dispatched` -> `evaluated` -> `verified` -> `promoted` with distinct verifier enforcement), `OperationCostLedger`, boundary auto-expansion, `ZeroHardcodedValuesAstGate` and `DomainAgnosticNamingGate`.
- **Sanctioned boundary enforcement (`radar_engine.py`)**: Rejects direct scraping of login-gated social walls (`facebook.com` and authenticated social hosts) with `sanctioned_public_api_or_search_lens_only`, routing discovery through sanctioned public APIs, feeds and canonical repository URLs.
- **64-bit shingle SimHash + canonical repository coalescing**: Deduplicates multi-source sightings across GitHub Search REST API, Hacker News Algolia `Show HN`, Hugging Face Daily Papers and public curator cross-post lenses while linking existing archive seed catalogs without blind duplication.
- **Breakout utility vs hype scoring**: Rewards permissive open-source licenses, runnable quickstart commands, real code substance, star-per-day velocity and cross-source corroboration while penalizing empty, unlicensed or star-farmed hype repositories.
- **Bounded follow-up proposal generation**: Emits `proposed_verbs` / `queued_tasks` envelopes for quickstart verification, capability-ontology linking, reusable MCP/skill adapter synthesis and runnable component demo creation without auto-enqueuing or creating a rival authority.

## Verification

```bash
make check
python3 -m pytest -q
```
