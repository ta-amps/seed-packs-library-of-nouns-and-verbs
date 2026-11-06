# Partner compute telemetry cards

## What this pack lets workers do

A collection of nouns and verbs for building and validating honest partner compute telemetry cards for Modal, Baseten and Fireworks AI from cascade records, showing measured numbers only on live credentialed runs with provider request ids and 64-hex receipts, and rendering CSP-safe HTML.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Forbid numeric performance claims on `offline_check` cards, require `measured_at` + `provider_request_ids` + `measured` + 64-hex receipt on `live_run` cards, forbid credit amounts/logos/stamp words, and require `distinct_reviewer` |
| `rules.card-honesty-and-csp` | Deterministic `offline_check` vs `live_run` rules and class-only HTML rules (`style-src 'self'`) |
| `tool.telemetry-cards` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.partner-telemetry-card-bundle` | JSON Schema for validated three-provider card bundles and CSP-safe HTML checks |
| Worked example | Offline three-provider cascade example (`example.oct31-offline-cascade-cards`) verified by unit tests |

## Verbs

| Verb (task: thing to do) | Who | What happens |
| --- | --- | --- |
| `build-cards` | agent, no model | Build Modal, Baseten and Fireworks AI telemetry cards and escaped class-only HTML from a cascade record |
| `verify-cards` | agent, no model | Independently verify card receipts, claim honesty, stamp bans and CSP-safe HTML (`distinct_reviewer`) |

## How to use it

Run `make check` in [code/](code/README.md) to run all 7 unit tests covering offline card generation, live-run evidence requirements, numeric-claim and stamp-word rejection, HTML escaping and `ZeroHardcodedValuesAstGate`.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these Tasks through the shared work queue.
- Offline checks validate cascade records locally; live provider numbers appear only when credentialed cloud runs record their receipts.
