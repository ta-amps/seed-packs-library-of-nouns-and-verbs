# agent-harness-feeds code

Standard-library evaluation and feed encapsulation tools for `packs/agent-harness-feeds`:

- `harness_feeds.metrics`: computes `HarnessTax` token overhead (`(total - raw) / raw` and multiplier), `cost_per_verified_task_usd`, Wilson 95 percent intervals for MCP tool reliability and Terminal-Bench / SWE-bench solve rates, and setup completeness flags.
- `harness_feeds.pareto`: computes exact multi-objective Pareto non-dominated frontiers, constrained harness recommendations, and release-aware exponential freshness decay.
- `harness_feeds.feed`: encapsulates child task objects (`profile.*`, `source.*`, `benchmark.*`, `recommendation.*`) for Harness Square / Harness2, OpenCode, Pi and Muse Code into a deterministic SHA-256 `Feed` task object.

Run `make check` to compile with `-W error` and execute the unit tests and worked-example recomputation.
