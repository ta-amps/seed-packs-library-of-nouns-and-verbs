# self-rewarding-and-iterative-dpo-flywheel (`iterative_rpo_flywheel`)

Standard-library implementation of grid-governed iterative RPO preference curation, rubric-judge calibration gating and pre-registered flywheel promotion:
- `IterativeRpoPairCurator`: builds `(prompt, chosen_verified, rejected_tombstone)` pairs with `Iterative RPO` scoring (`DPO logistic loss + alpha * NLL_chosen` regularizer preventing chosen log-probability collapse), length-ratio bias filtering and 3-key structural deduplication.
- `RubricJudgeCalibrationGate`: evaluates candidate self-rewarding rubric judges against deterministic ground-truth verifiers (Cohen's kappa, exact agreement and false-positive approval rate) and blocks uncalibrated synthetic pairs.
- `PreRegisteredFlywheelPromoter`: gates candidate generation rounds against pre-registered holdout SHA-256 locks, sanity retention bounds, regression caps and distinct-reviewer separation.
- `ZeroHardcodedValuesAstGate` and `scan_directory_for_hardcoded_values`: mechanical Python AST scanner verifying zero non-identity inline numeric literals across `iterative_rpo_flywheel/`.

Run checks:
```bash
make check
```
