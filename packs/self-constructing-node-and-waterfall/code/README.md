# constructible_node

Standard-library Python 3.10+ reference implementation for `self-constructing-node-and-waterfall`:

- `Interrogator5W1H` and `ContinuousStepProfiler`: structured `who/what/where/when/why/how` + temporal horizon decomposition and per-step state signature hashing to short-circuit already-solved intermediate states in zero model tokens.
- `KeywordFreshResourceTrigger`: deterministic keyword matching hydrating recently updated (`< max_age_hours`) external context before reasoning.
- `PlanKDecideOneFrontier` and `WeightedWaterfallExecutor`: five-rung execution waterfall (`rung_0_exact_cache` through `rung_4_cli_harness_grid` with configurable `opencode`, `pi`, and `codex` harness cells).
- `MultiPersonaVectorJudge` and `CapabilityGapSpinoutLedger`: multi-persona, multi-dimension vector scoring, cheaper deterministic distillation proposals, and quorum-gated background capability-builder verb proposals.
- `ZeroHardcodedValuesAstGate` and `DomainAgnosticNamingGate`: mechanical AST magic-number and domain-agnostic naming gates.

Run checks:

```bash
make check
```
