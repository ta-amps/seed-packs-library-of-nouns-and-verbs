# Submission rubric and readiness audit

## What this pack lets workers do

A collection of nouns and verbs for auditing engineering repositories against weighted evaluation
rubrics covering problem specificity, verified open-weight and multimodal model usage, modular
source and CI depth, and live deployment plus video walkthrough completeness, with tested
standard-library Python code. Many project repositories mention models or live demos in README prose
while omitting wired imports, automated tests, Dockerfiles, or verified HTTP 200 endpoints. Workers
inspect actual source trees and dated probe receipts, withhold credit for prose-only claims, compute
weighted pillar totals, and rank remediations by recoverable points.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Code evidence beats prose claims; live endpoints require HTTP 200 + SHA-256 probe receipts |
| Rubric scoring rules | Default 30/25/20/25 pillar weights (10.0 pts) and recoverable-point remediation ordering |
| Templates | Repository manifest, weighted readiness scorecard, and remediation checklist |
| Record checks | Deterministic checks on readiness scorecards with synthetic good and bad fixtures |
| Tool card and code | Tested standard-library Python package in [code/](code/README.md) (`rubric_audit`) |
| Sources | 2 dated public sources on OpenSSF Scorecard checks and SPDX repository metadata |
| Worked examples | Synthetic 10.0-point evidence-backed repository readiness scorecard |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `inventory-repository-evidence` | agent, no model | Scan local files, imports, CI workflows, containers, and probe receipts into a manifest |
| `verify-model-and-depth-signals` | agent | Separate wired open-weight or multimodal code paths from README-only claims |
| `score-weighted-readiness-rubric` | agent, no model | Compute weighted pillar scores, blockers, and ranked remediations |

Each verb can also end with `no_change`, `unknown`, or `blocked`, and proposes follow-up verbs
instead of enqueueing them.

## Limits

- A proposal: not installed, imported, admitted, or activated, and no worker has run these verbs.
- Static import and config checks prove code wiring, not runtime model quality on held-out inputs.
- Automated readiness scores assist engineering self-audits and never replace human evaluation.
