# Rule of Two and agent guardrails

## What this pack lets workers do

A collection of nouns and verbs for enforcing monotone Rule of Two capability lattices across multi-step tool DAGs, bidirectional typed privacy placeholder vaults and model license-tier routing firewalls. Workers propagate `untrusted_input` (`A`), `sensitive_access` (`B`) and `external_mutation_or_egress` (`C`) across multi-step DAGs so any unapproved 3-leg path fails closed with `403` and a minimal witness path, scrub sensitive entities into lossless `<ENTITY_TYPE_001>` vaults while preserving SHA-256 digests and route payloads across `contributor_training_allowed`, `standard_zero_retention` and `local_open_weights`.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Refuse unapproved 3-leg DAG paths with `403` + minimal witness, require reversible `<ENTITY_TYPE_NNN>` vaulting and forbid inline magic literals |
| `spec.rule-of-two-and-privacy-grid` | Monotone 3-leg taint lattice, `403` refusal contract, placeholder format and 3-tier license firewall invariants |
| `rules.triad-witness-and-license-routing` | Zero-model DAG taint union equation and sensitivity/license tier routing matrix |
| `tool.rule-of-two-guardrails` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.rule-of-two-guardrails-receipt` | JSON Schema for DAG status codes, minimal witness paths, bidirectional recall/fidelity and license-tier routes |
| Worked example | Made-up DAG, privacy and license bundle (`example.rule-of-two-guardrails-bundle`) and recomputed receipt (`example.rule-of-two-guardrails-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `evaluate-rule-of-two-tool-dag` | agent, no model | Propagate monotone capability taint across a proposed tool DAG and refuse unapproved 3-leg paths with `403` |
| `scrub-and-route-privacy-license-tier` | agent, no model | Vault sensitive entities into `<ENTITY_TYPE_001>` tokens, route across 3 license tiers and rehydrate inbound text |
| `verify-bidirectional-vault-and-ast-gate` | agent, no model | Recompute receipts with a `distinct_reviewer` rule and verify zero AST magic-literal violations |

## Worked example

`python3 -m rule_of_two_guardrails --bundle BUNDLE.json` evaluates a 2-leg DAG (`200 allow`), a 5-node diamond 3-leg DAG (`403 refuse` at `emit_external_webhook` with minimal witness `["ingest_external_ticket", "inspect_scoped_ledger", "draft_triage_note", "emit_external_webhook"]`), a human-steward override (`200 allow`), `1.0` outbound zero-leak recall, `1.0` inbound round-trip fidelity and 3-tier license routing.

## Acceptance checks

- `make -C packs/rule-of-two-and-agent-guardrails/code check` passes all unit tests and `scan_directory_for_hardcoded_values == []`.
- Unapproved 3-leg combinations fail closed with `403` and exclude unrelated distractor DAG nodes from `minimal_witness_path`.

## Contents

- `source.json`, `nouns.json`, `verbs.json`, `manifest.json` and tested Python package in [code/](code/README.md).

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through a work-engine.
- Pattern-based and explicit-entity placeholder scrubbing requires accurate caller entity lists for unstructured prose secrets without recognizable token prefixes.
- Process and OS sandboxing remain necessary alongside pre-dispatch DAG taint and license-tier checks.
