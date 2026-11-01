# jepa-world-state-and-action-simulator (`world_state_jepa`)

Standard-library implementation of grid-governed factored representation-space world-state prediction, epistemic energy anomaly gating and counterfactual rollout planning:
- `ActionConditionedStatePredictor`: encodes environment state into compact factored representations (leases, resource quotas, record digests, capability taints, invariant predicates and normalized latent embeddings) and predicts `s_hat_{t+1} = transition(s_t, a_t)` before irreversible execution.
- `EpistemicEnergyAnomalyGate`: computes representation-space surprise energy `E(s_hat_{t+1}, s_obs_{t+1})` invariant to surface-level nuisance noise and triggers `require_review` or `trigger_rollback` when energy exceeds grid bounds.
- `CounterfactualRolloutPlanner`: simulates `K` multi-step candidate action sequences in representation space and ranks them by goal distance plus cumulative risk energy.
- `ZeroHardcodedValuesAstGate` and `scan_directory_for_hardcoded_values`: mechanical Python AST scanner verifying zero non-identity inline numeric literals across `world_state_jepa/`.

Run checks:
```bash
make check
```
