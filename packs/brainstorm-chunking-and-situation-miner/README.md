# Brainstorm chunking and situation miner

## What this pack lets workers do

A collection of nouns and verbs for deduplicating noisy raw notes, chunking unstructured text into
content-addressed records, and clustering real-world situations into candidate seed-pack categories,
with tested standard-library Python code. Raw brainstorming dumps frequently contain accidental
multi-paste repeats (such as 14 inline copies of the same rubric without blank lines) mixed with
unique operational notes. Workers split repeated spans deterministically, collapse exact and
word-shingle near-duplicates, emit SHA-256-addressed chunks, and rank category gaps by demand divided
by existing coverage.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Preserve unique text; pin every chunk by SHA-256; keep mined categories as proposals |
| Deduplication and gap rules | Left-maximal 6-word anchor splitting, 5-word shingle Jaccard threshold, and gap formula |
| Templates | Deduplication summary, content-addressed chunk, real-world situation, and category gap report |
| Record checks | Deterministic checks on mined brainstorm reports with made-up good and bad fixtures |
| Tool card and code | Tested standard-library Python package in [code/](code/README.md) (`brainstorm_miner`) |
| Sources | 2 dated public sources on Rabin/Broder shingling and RFC 6234 SHA-256 |
| Worked examples | Made-up 14:1 paste-collapse and situation-mining report |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `deduplicate-raw-notes` | agent, no model | Split inline or block repeats and collapse exact and shingle near-duplicates |
| `chunk-canonical-notes` | agent, no model | Segment canonical blocks into SHA-256-addressed semantic chunks |
| `extract-real-world-situations` | agent | Map chunks to actor, trigger problem, and operational constraint records |
| `score-category-coverage-gaps` | agent, no model | Rank candidate seed-pack categories by demand over existing pack count |

Each verb can also end with `no_change`, `unknown`, or `blocked`, and proposes follow-up verbs
instead of enqueueing them.

## Limits

- A proposal: not installed, imported, admitted, or activated, and no worker has run these verbs.
- Shingle similarity catches lexical near-duplicates, not paraphrases written in completely new words.
- Gap scores rank candidate backlog priorities only; human stewards decide which packs to author.
