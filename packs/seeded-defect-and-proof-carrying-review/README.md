# Seeded defect and proof-carrying review

## What this pack lets workers do

A collection of nouns and verbs for mutation-guided reviewer calibration across six seeded defect classes, proof-carrying refusal and approval verification and exact Wilson score plus paired bootstrap confidence intervals. Workers synthesize deterministic defect twins (`digest_mismatch`, `boundary_off_by_one`, `silent_exception_swallow`, `capability_tier_violation`, `self_approval_principal_reuse` and `ungrounded_citation_span`), enforce "no refusal without a failing check; no approval without mutant kill threshold" and bound rates and head-to-head deltas statistically.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Reject refusals lacking a reproduced failing check witness, reject uncalibrated rubber-stamp approvals and forbid inline magic literals |
| `spec.seeded-defect-and-review-proof-grid` | Six universal seeded defect operators, proof-carrying verdict invariants and Wilson/bootstrap interval specs |
| `rules.mutant-calibration-and-interval-audit` | Zero-model twin calibration rules, Wilson score equation and paired bootstrap delta definition |
| `tool.proof-carrying-review` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.proof-carrying-review-receipt` | JSON Schema for mutant kill rates, clean FPR, proof-carrying gate outcomes and confidence intervals |
| Worked example | Two clean bundles + paired score vectors (`example.proof-carrying-review-bundle`) and recomputed receipt (`example.proof-carrying-review-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `generate-seeded-defect-mutant-twins` | agent, no model | Expand clean candidate bundles into deterministic 6-class defect twins |
| `verify-proof-carrying-review-verdicts` | agent, no model | Calibrate reviewer kill/FPR rates and block unfounded refusals or rubber-stamp approvals |
| `audit-wilson-and-paired-bootstrap-intervals` | agent, no model | Recompute Wilson and paired bootstrap intervals with a `distinct_reviewer` rule and verify AST gates |

## Worked example

`python3 -m proof_carrying_review --bundle BUNDLE.json` expands `2` clean bundles into `12` mutants across `6` defect classes, calibrates a proof-carrying reviewer (`1.0` kill rate, `0.0` clean FPR, 95% Wilson CI `[0.7575, 1.0]`), blocks unfounded refusals and rubber-stamp approvals and measures paired bootstrap mean delta `0.22` (`95%` CI `[0.215, 0.2263]`).

## Acceptance checks

- `make -C packs/seeded-defect-and-proof-carrying-review/code check` passes all unit tests and `scan_directory_for_hardcoded_values == []`.
- Every seeded mutant trips its exact target check while unfounded refusals and rubber-stamp approvals fail closed.

## Contents

- `source.json`, `nouns.json`, `verbs.json`, `manifest.json` and tested Python package in [code/](code/README.md).

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through a work-engine.
- Mutant kill calibration measures sensitivity across the six modeled structural defect classes and does not prove absence of unmodeled semantic bugs.
- Paired bootstrap intervals assume exchangeable evaluation items across baseline and candidate runs.
