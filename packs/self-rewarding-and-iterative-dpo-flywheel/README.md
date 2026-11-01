# Self-rewarding and iterative DPO flywheel

## What this pack lets workers do

A collection of nouns and verbs for iterative RPO preference curation, rubric-judge calibration gating against deterministic verifiers and pre-registered holdout flywheel promotion. Workers curate `(prompt, chosen_verified, rejected_tombstone)` pairs with `IterativeRpoPairCurator` (`DPO logistic loss + alpha * NLL_chosen` regularizer that prevents chosen log-probability collapse across rounds, plus length-ratio bias filtering and `3`-key structural deduplication), gate synthetic self-rewarding pairs with `RubricJudgeCalibrationGate`, and verify candidate rounds against locked SHA-256 holdouts with `PreRegisteredFlywheelPromoter`.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Block synthetic pairs from uncalibrated rubric judges, require SHA-256 holdout locks plus `proposer != reviewer` and enforce zero inline magic scalars via `ZeroHardcodedValuesAstGate` |
| `spec.iterative-rpo-and-flywheel-grid` | `DPO` `beta`, `Iterative RPO` `alpha`, length-ratio ceilings, `3`-key structural deduplication and Cohen's kappa calibration bounds |
| `rules.rpo-objective-and-calibration-gates` | Zero-model `L_RPO` loss formula, `3`-key structural hashes and pre-registered holdout promotion checks |
| `tool.iterative-rpo-flywheel` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.iterative-rpo-flywheel-receipt` | JSON Schema for rubric kappa/FPR, admitted/rejected pair counts, `DPO` margin, `RPO` loss and holdout promotion verdicts |
| Worked example | Calibrated vs uncalibrated rubric judges, `RPO` candidate pairs and locked holdout (`example.iterative-rpo-flywheel-bundle`) plus recomputed receipt (`example.iterative-rpo-flywheel-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `calibrate-rubric-judge-against-verifiers` | agent, no model | Compute Cohen's kappa, exact agreement and false-positive rate against deterministic verifiers and block uncalibrated synthetic pairs |
| `curate-iterative-rpo-preference-pairs` | agent, no model | Score preference pairs with `Iterative RPO` (`DPO + alpha * NLL_chosen`), reject logp-collapse/length-bias pairs and run `3`-key deduplication |
| `verify-preregistered-flywheel-promotion` | agent, no model | Independently verify holdout SHA-256 locks, sanity retention, regression caps (`distinct_reviewer`) and `ZeroHardcodedValuesAstGate` |

## Worked example

In `example.iterative-rpo-flywheel-bundle`, `RubricJudgeCalibrationGate` approves the calibrated judge (`cohens_kappa = 0.75`, `FPR = 0.0`) while blocking `100%` of synthetic pairs from an uncalibrated judge (`cohens_kappa = -0.2`). `IterativeRpoPairCurator` filters out `1` length-ratio-biased pair, `1` chosen-logp-collapse trap and `1` structural skeleton duplicate, admitting `2` clean pairs (`mean_dpo_margin = 0.925`, `mean_rpo_loss = 0.743994`) that pass `PreRegisteredFlywheelPromoter` with `+0.2` net holdout gain and `0.0` regressions.

## Acceptance checks

Run `make check` in [code/](code/README.md) to verify `Iterative RPO` chosen-collapse suppression (`alpha > 0` vs pure `DPO`), length-ratio filtering, `3`-key structural deduplication, Cohen's kappa calibration gating, holdout SHA-256 tamper rejection, `scan_directory_for_hardcoded_values == []` and CLI receipt recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through the work-engine.
- Offline `Iterative RPO` scoring and rubric calibration evaluate precomputed policy/reference log-probabilities and verifier outcomes without running neural gradient updates.
- Synthetic self-rewarding preference pairs remain subordinate to deterministic verifiers and pre-registered holdouts.

## Contents

- `README.md`, `source.json` and generated proposal payloads (`nouns.json`, `verbs.json`, `manifest.json`)
- [code/](code/README.md): `iterative_rpo_flywheel` standard-library Python package and `unittest` suite
