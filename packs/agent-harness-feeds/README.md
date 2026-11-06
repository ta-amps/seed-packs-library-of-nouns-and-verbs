# Agent harness feeds

## What this pack lets workers do

A collection of nouns and verbs for continuously researching, benchmarking and encapsulating
updates on open agent harnesses: **Harness Square / Harness2**, **OpenCode**, **Pi** and
**Muse Code**. In plain language, nouns are **task objects** (an encapsulating `Feed` object,
child harness profiles, release sources, normalized benchmarks, Pareto recommendations, an
unactivated schedule proposal and pinned code) and verbs are **tasks** a worker claims. Workers
probe upstream release feeds, normalize Terminal-Bench and SWE-bench Verified trials alongside
`HarnessTax` token overhead, cost-per-verified-task and MCP tool reliability, check staleness,
encapsulate child objects into one deterministic `Feed` digest, and select a harness for a task.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| `feed.agent-harnesses` | Encapsulating `Feed` task object (`noun.feed_source`) pinning child profiles, sources, benchmarks and Pareto recommendations under a deterministic SHA-256 digest |
| `profile.harness-square`, `profile.opencode`, `profile.pi`, `profile.muse-code` | Architecture, tool loop, context discipline and MCP support profiles for the four open agent harnesses |
| `source.open-harness-releases` | Upstream public repositories and benchmark boards probed for release and protocol changes |
| `benchmark.normalized-matrix` | Normalized `HarnessTax`, `cost_per_verified_task_usd`, solve rate and MCP reliability matrix |
| `recommendation.pareto-selection` | Non-dominated Pareto frontier and constrained harness recommendation |
| `schedule.harness-feed-scan` | Unactivated daily scan proposal (`activation: not_activated`, `authority: none`) requiring an authorized schedule service |
| `tool.harness-feeds` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| Templates and worked example | `template.feed-snapshot` schema and made-up trial data (`example.raw-harness-runs`) recomputed in CI |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `probe-harness-sources` | agent, no model | Fetch public release tags and changelog metadata from `source.open-harness-releases` |
| `normalize-harness-benchmarks` | agent, no model | Compute `HarnessTax`, `cost_per_verified_task_usd` and Wilson 95 percent intervals for solve rate and MCP reliability |
| `recheck-harness-freshness` | agent, no model | Apply exponential age and missed-release freshness decay to profiles and benchmark rows |
| `encapsulate-harness-feed` | agent, no model | Seal updated child profiles, sources, benchmarks and recommendations into a new `Feed` snapshot digest |
| `select-harness-for-task` | agent, no model | Compute the Pareto frontier and pick the highest-utility harness meeting cost, `HarnessTax` and MCP floors |

## How to use it

Run `make check` in [code/](code/README.md) to compile with warnings treated as errors and verify
`HarnessTax`, Pareto ranking, freshness decay and the encapsulated `feed.agent-harnesses` digest.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these Tasks through the shared work queue.
- `schedule.harness-feed-scan` is `not_activated` (`authority: none`) and cannot schedule or
  authorize work by itself.
- Benchmark figures inside `example.raw-harness-runs` and `benchmark.normalized-matrix` are
  made-up fixtures testing normalization and Pareto math, never live leaderboard claims.
