# seeded-defect-and-proof-carrying-review (`proof_carrying_review`)

Standard-library implementation of mutation-guided review calibration, proof-carrying review verification, and exact statistical interval auditing:
- `SeededDefectMutantSuite`: deterministically injects 6 universal defect classes (`digest_mismatch`, `boundary_off_by_one`, `silent_exception_swallow`, `capability_tier_violation`, `self_approval_principal_reuse`, `ungrounded_citation_span`) into structured candidate bundles and runs reproducible AST/invariant checks.
- `ProofCarryingReviewVerifier`: enforces *"no refusal without a reproducible failing check; no approval without mutant kill threshold"* across clean vs seeded-defect twins, rejecting both unfounded refusals and rubber-stamp approvals.
- `StatisticalIntervalAuditor`: computes exact Wilson score confidence intervals for pass/kill proportions and deterministic paired bootstrap confidence intervals for head-to-head system comparisons.
- `ZeroHardcodedValuesAstGate` and `scan_directory_for_hardcoded_values`: mechanical Python AST scanner verifying zero non-identity inline numeric literals across operational modules.

Run checks:
```bash
make check
```
