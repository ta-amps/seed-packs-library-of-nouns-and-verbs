# JEPA world-state and action simulator

## What this pack lets workers do

A collection of nouns and verbs for action-conditioned latent world-state prediction, representation-space epistemic energy anomaly gating and counterfactual multi-step rollout planning. Workers project environment observations into compact factored representations (`FactoredWorldState`: leases, resource quotas, record digests, capability taints and invariant predicates), predict post-action states `s_hat_{t+1} = transition(s_t, a_t)` before irreversible execution with `ActionConditionedStatePredictor`, gate unexpected execution divergence via `EpistemicEnergyAnomalyGate`, and rank `K` multi-step counterfactual trajectories with `CounterfactualRolloutPlanner`.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Reject invariant-breaking trajectories before irreversible execution and resolve all surprise/horizon bounds from `NodeGrid` with zero inline magic scalars |
| `spec.jepa-world-state-and-energy-grid` | Factored representation axes, default rollout horizon (`6`) and review/rollback surprise energy thresholds (`0.2` / `1.0`) |
| `rules.latent-transition-and-surprise-energy` | Zero-model representation transition `s_hat_{t+1}`, epistemic surprise `E(s_hat, s_obs)` and multi-step rollout objective `J(a_{0:H-1})` |
| `tool.world-state-jepa` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.world-state-jepa-receipt` | JSON Schema for trajectory recommendations, goal/risk energies, surface-jitter surprise and anomaly rollback recall |
| Worked example | `3` candidate trajectories plus clean/anomalous observations (`example.world-state-jepa-bundle`) and recomputed receipt (`example.world-state-jepa-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `plan-counterfactual-rollout-trajectories` | agent, no model | Simulate `K` multi-step candidate action sequences in representation space and rank feasible minimum-energy plans |
| `gate-step-by-epistemic-surprise-energy` | agent, no model | Compute post-action representation-space surprise `E(s_hat_{t+1}, s_obs_{t+1})` and output `continue`, `require_review` or `trigger_rollback` |
| `verify-world-state-simulator-receipt` | agent, no model | Independently verify trajectory fencing, anomaly rollback recall (`distinct_reviewer`) and `ZeroHardcodedValuesAstGate` |

## Worked example

In `example.world-state-jepa-bundle`, `CounterfactualRolloutPlanner` rejects an unfenced tainted commit plan pre-execution and selects `plan-fenced-sanitized-clean` (`goal_distance_energy = 0.0`, `total_objective_energy = 0.3925`) ahead of a quota-heavy dangling-lease plan. After step execution, `EpistemicEnergyAnomalyGate` assigns `0.0` surprise (`continue`) under benign whitespace/timestamp jitter while triggering rollback on `100%` (`3/3`) of injected lease-theft, phantom-CAS and quota-drain anomalies (`max_anomaly_energy = 9.18778`).

## Acceptance checks

Run `make check` in [code/](code/README.md) to verify pre-execution lease/taint/CAS/quota invariant fencing, representation-space invariance to surface noise, `100%` anomaly rollback recall, `NodeGrid` constraint enforcement, `scan_directory_for_hardcoded_values == []` and CLI receipt recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through the work-engine.
- Factored symbolic-and-hashed world-state transitions model explicit protocol invariants deterministically rather than training neural encoder weights online.
- Counterfactual simulations prevent predictable invariant breaches; unmodeled external perturbations still rely on post-step `EpistemicEnergyAnomalyGate` rollback checks.

## Contents

- `README.md`, `source.json` and generated proposal payloads (`nouns.json`, `verbs.json`, `manifest.json`)
- [code/](code/README.md): `world_state_jepa` standard-library Python package and `unittest` suite
