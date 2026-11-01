# Coding session trace distiller

## What this pack lets workers do

A collection of nouns and verbs for mining sanitized multi-hour AI coding session JSONL transcripts
into reusable failure tombstones, tool-error loops, verified fix recipes, and candidate prompt
shims. Coding agents repeat the same broken edit targets, flag combinations, and environment
mistakes across sessions unless those traces are distilled under strict redaction and verification
gates. Workers strip credentials, personal addresses, and home-directory paths first, detect
consecutive tool-error streaks, separate unverified edits from fixes backed by a failing check and
subsequent passing check, and propose bounded prompt shims with exact step evidence.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Redact before reading or storing; a fix recipe needs a failing check then a passing check; shims stay proposals |
| Redaction and loop rules | Credential, address, and workstation-path scrubbing; normalized error signatures and wasted-step math |
| Verification gate rules | Strict `failing_check -> edit -> passing_check` state machine rejecting untested edits |
| Templates | Sanitized trace summary, failure tombstone, verified fix recipe, and prompt-shim candidate |
| Record checks | Deterministic checks on distilled session reports with synthetic good and bad fixtures |
| Tool card and code | Tested standard-library Python package in [code/](code/README.md) (`session_distiller`) |
| Sources | 2 dated public sources on JSON Lines and OpenTelemetry semantic conventions |
| Worked examples | Synthetic distilled session report and conforming verified fix recipe |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `redact-session-trace` | agent, no model | Scrub credentials, personal addresses, and home paths from a local JSONL transcript |
| `mine-error-loops-and-tombstones` | agent | Extract repeated tool-error loops and abandoned branches as failure tombstones |
| `extract-verified-fix-recipes` | agent | Isolate fixes proven by a prior failing check and subsequent passing check |
| `draft-prompt-shim-candidates` | agent | Draft bounded prompt-shim candidates tied to observed loop or tombstone ids |
| `compile-distillation-report` | agent, no model | Assemble sanitized counts, tombstones, verified fixes, and shim proposals into one checked report |

Each verb can also end with `no_change`, `unknown`, or `blocked`, and proposes follow-up verbs
instead of enqueueing them.

## Limits

- A proposal: not installed, imported, admitted, or activated, and no worker has run these verbs.
- Pattern redaction catches known token shapes, personal emails, and home paths; human review is
  still required before sharing any transcript excerpt beyond its owning workspace.
- Passing checks in a session prove only that the recorded command exited zero in that workspace,
  not universal correctness across environments.
