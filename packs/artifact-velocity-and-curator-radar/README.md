# Emerging artifact velocity and curator radar

## What this pack lets workers do

A collection of nouns and verbs for harvesting sanctioned public velocity signals on brand-new open-source repositories, separating runnable engineering substance from star-farming hype, matching curator-lens heuristics, cross-linking existing seed archives without blind duplication, and proposing bounded verification, adapter and demo tasks.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Enforce `allow_authenticated_wall_scraping: false` (sanctioned public APIs and explicit canonical repo intake only) and preserve single-authority queue governance |
| `template.velocity-signal-dossier` | JSON Schema for canonical repo URL, creation timestamp, age in days, star velocity, fork ratio, SPDX license, quickstart commands, runtime footprint, capability facets, curator lenses and 64-bit SimHash |
| `catalog.curator-lens-and-upstream-radar-feeds` | Declarative curator-lens heuristics (`PHfreecoder`, `fusin.automation`, `chriiske` and 7 reference profiles with `authenticated_wall_scraping_prohibited: true`) paired with GitHub Search REST API, Hacker News Algolia, Hugging Face Daily Papers and Atom/RSS feeds |
| `rubric.breakout-utility-and-hype-filter` | 6-axis utility and anti-hype scoring rubric penalizing unlicensed, tiny or waitlist-shell repositories while rewarding runnable quickstarts and cross-source corroboration |
| `tool.velocity-signal-radar` | Tested zero-dependency Python 3.10+ package in [code/](code/README.md), pinned by path, file count and SHA-256 |
| `template.radar-evaluation-receipt` | Deterministic receipt schema for coalesced dossiers, refused unsanctioned wall probes, filtered hype keys and bounded follow-up proposals |
| Worked example | Synthetic multi-source bundle (`example.velocity-radar-bundle`) and recomputed receipt (`example.velocity-radar-receipt`) |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `harvest-and-normalize-upstream-velocity-signals` | agent, no model | Normalize sanctioned public sightings across GitHub Search, Hacker News Algolia and Hugging Face while refusing login-gated social walls |
| `deduplicate-and-score-breakout-utility` | agent, no model | Coalesce canonical repository keys and 64-bit SimHash shingles, score breakout utility vs hype and enforce distinct review |
| `verify-quickstart-and-extract-architecture-card` | agent, no model | Verify quickstart commands, SPDX license and runtime footprints and map capabilities onto `capability-ontology-and-benchmark-seeds` |
| `emit-bounded-enrichment-and-demo-proposals` | agent, no model | Emit bounded `proposed_verbs` / `queued_tasks` envelopes for quickstart verification, ontology linking, MCP/skill adapters and runnable demos |

## How to use it

Run `make check` in [code/](code/README.md) to execute all unit tests covering `NodeGrid` clamping and boundary auto-expansion, `GridLedger` distinct-verifier promotion, login-gated wall refusal (`sanctioned_public_api_or_search_lens_only`), 64-bit SimHash deduplication, hype-filter scoring, `ZeroHardcodedValuesAstGate` and `DomainAgnosticNamingGate`.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has run these verbs on a live fabric.
- Workers never scrape login-gated Facebook walls or bypass `robots.txt` or authentication boundaries; curator URLs act strictly as declarative topic lenses and human/agent link-intake references.
- Follow-up tasks stay bounded proposals inside `proposed_verbs` and `proposed_nouns` (`maximum_automatically_enqueued_children: 0`) without creating a competing queue authority.
