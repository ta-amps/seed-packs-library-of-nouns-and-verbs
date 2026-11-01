# Agent capability and tier firewall

## What this pack lets workers do

A collection of nouns and verbs for enforcing scoped effect ceilings, credential and PII redaction,
and model data-tier routing guards before an agent tool call or model request runs. Autonomous
coding and research workers routinely mix internal repository text, environment variables, and
varied provider endpoints; a single misconfigured contributor flag or over-broad write grant can
expose sensitive context to training-enabled APIs or mutate out-of-scope paths. Workers define an
explicit capability lattice (`none < read < write-internal < write-repo < public`), scan payloads
for token prefixes and high-entropy secrets while preserving 64-char SHA-256 digests, block
non-public data from `trains_on_inputs` or `contributor_shared` endpoints, and record auditable
allow/block receipts.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Fail closed on effect ceiling breaches; block non-public payloads from training/contributor tiers; never dispatch secret-tier data |
| Capability and tier rules | Ordered 5-level effect lattice, Shannon entropy threshold (`4.25` bits/char), and 4-tier endpoint retention matrix |
| Templates | Firewall policy, pre-dispatch evaluation receipt, and redaction audit |
| Record checks | Deterministic checks on firewall decision receipts with synthetic good and bad fixtures |
| Tool card and code | Tested standard-library Python package in [code/](code/README.md) (`tier_firewall`) |
| Sources | 2 dated public sources: OWASP Top 10 for LLM Applications and NIST SP 800-53 Rev. 5 |
| Worked examples | Synthetic blocked contributor-mode dispatch receipt and clean enterprise-tier allow receipt |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `author-capability-tier-policy` | human | Define maximum effect ceiling, allowed stores/paths, and redaction policy for a worker scope |
| `scan-payload-for-secrets` | agent, no model | Scan and scrub outbound payloads for credentials, personal IDs, and high-entropy tokens |
| `evaluate-pre-dispatch-gate` | agent, no model | Run effect-ceiling, secret-scan, and model data-tier checks via `tier_firewall` before execution |
| `quarantine-blocked-dispatch` | agent | Record a failure tombstone when a request is blocked for exceeding capability or data-tier bounds |

Each verb can also end with `no_change`, `unknown`, or `blocked`, and proposes follow-up verbs
instead of enqueueing them.

## Limits

- A proposal: not installed, imported, admitted, or activated, and no worker has run these verbs.
- Pre-dispatch text scanning catches known credential shapes, SSN-like identifiers, and mixed-case
  high-entropy tokens, but cannot infer semantic confidentiality of plain prose without accurate
  `data_sensitivity` classification from the caller.
- Process and OS sandboxing remain necessary alongside pre-dispatch policy checks.
