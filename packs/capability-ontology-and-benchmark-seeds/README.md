# Capability ontology and benchmark seeds

## What this pack lets workers do

A collection of nouns and verbs for building, expanding, searching, benchmarking and maintaining open-ended polyhierarchical capability ontologies and intelligence cards across AI tools, MCP servers, feeds, durable task queues, agent architecture patterns, open-source releases and hackathons.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Keep workers stateless without creating a rival scheduler, custom primitive or single-parent ontology lock-in |
| `ontology.polyhierarchical-capability-graph` | Polyhierarchical `parent_ids` DAG supporting multi-niche membership and open-ended facet labels |
| `template.intelligence-card` | JSON Schema for AI tools, MCP servers, feeds, durable queues, patterns and releases with I/O-port hashes |
| `matrix.durable-queue-pattern-and-hackathon-radar` | Radar matrix covering inline-lease durable queues, CAS fencing, coalescing, OSS releases and hackathon tracks |
| `rubric.multi-axis-pareto-and-demo-benchmark` | Multi-axis head-to-head Pareto and regime rubric across cost, sub-10ms p99, 4GB laptop fit, zero-dep, K8s and accuracy |
| `catalog.root-ecosystem-seeds` | Starter nodes and feeds across OCR, PII, 3D, motion graphics, voice/ASR, MCPs, durable queues, patterns, OSS releases and hackathons |
| `tool.capability-ontology-seeds` | Tested zero-dependency Python 3.10+ package in [code/](code/README.md), pinned by path, file count and SHA-256 |
| `template.ontology-benchmark-receipt` | Deterministic receipt schema for DAG checks, I/O clustering, 3-generation seed digestion, Pareto ranking and AST/naming gates |
| `template.niche-demo-walkthrough` | Deterministic 4-beat component demo and verification walkthrough schema for top-ranked niche candidates |
| Worked example | Synthetic ecosystem bundle (`example.ontology-seed-bundle`) and recomputed receipt (`example.ontology-seed-receipt`) |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `expand-polyhierarchical-ontology-slice` | agent, no model | Digest one root or intermediate seed by 1 bounded hop (`generation_depth + 1`) via `parent_task_id` and shingle Jaccard deduplication |
| `discover-and-verify-intelligence-cards` | agent, no model | Validate AI tool, MCP server and feed cards, hash canonical I/O ports and cluster hot-swappable candidates |
| `harvest-and-diff-oss-releases-and-patterns` | agent, no model | Diff new open-source releases, papers and hackathon patterns against prior profiles to flag tool and I/O changes |
| `benchmark-and-pareto-rank-niche-candidates` | agent, no model | Score candidates across 7 axes, compute the Pareto frontier under a verified `NodeGrid` regime and enforce distinct review |
| `synthesize-niche-demo-and-walkthrough` | agent, no model | Synthesize a deterministic 4-beat runnable component demo and failure-mode check for top-ranked niche candidates |

## How to use it

Run `make check` in [code/](code/README.md) to execute all unit tests covering polyhierarchical DAG branching, I/O-port signature clustering, 3-generation (`gen 0 -> gen 1 -> gen 2`) `/q/submit` seed digestion, Pareto frontier ranking, `ZeroHardcodedValuesAstGate` and `DomainAgnosticNamingGate`.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has run these verbs on a live fabric.
- Seed digestion emits bounded follow-up proposals inside `proposed_verbs` and `proposed_nouns` and never auto-enqueues child tasks or creates a competing queue authority.
- All configuration bounds, fanout caps, Jaccard thresholds and rubric weights load from `code/capability_ontology_seeds/config/ontology_seed_grid.json` under `GridLedger` verification.
