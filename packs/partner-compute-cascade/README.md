# Partner compute cascade

## What this pack lets workers do

A collection of nouns and verbs for routing public-good tasks across a edge shim,
Fireworks AI multi-LoRA specialist adapters, Baseten `<= 2,000,000 TPM` fenced worker swarms,
Modal isolated sandboxes and serverless QLoRA fine-tuning, and Meta Muse models, including Muse Glimmer 30B.
Workers replay memoized deterministic hits at zero token cost, apply Sinan Ozdemir's
specialist-drafter plus distinct-rubric-verifier pattern for structured JSON tasks, pace large
batches safely within rate and lease fences, and emit honest `local_verified` vs `live_api` receipts.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Stamp `local_verified` vs `live_api` honestly; enforce `<= 2,000,000 TPM` sliding windows and pre-flight lease fencing; forbid self-verification by specialist LoRA drafters |
| `spec.five-tier-compute-cascade` | 5-tier escalation order, `$100 x 3` Modal/Baseten/Fireworks credit envelopes, `2M TPM` ceiling and `< 2.0 ms` shim budget |
| `rules.partner-cascade-gates` | Modal sandbox isolation flags, holdout-safe QLoRA trace checks and rubric escalation triggers |
| `tool.partner-cascade` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.cascade-receipt` | JSON Schema for mode, QLoRA peak VRAM fit, sandbox validity, selected adapter and rubric status |
| Worked example | `Muse-Glimmer-30B` QLoRA, sandbox and statute-citation bundle (`example.cascade-bundle`) and recomputed receipt (`example.cascade-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `validate-modal-qlora-and-sandbox` | agent, no model | Check container sandbox isolation flags, holdout-safe QLoRA trace rules and 4-bit NF4 GPU VRAM margin |
| `pace-baseten-fenced-swarm` | agent, worker allowance | Enforce pre-flight fencing-token and lease-TTL checks, then pace async claims under `<= 2,000,000 TPM` |
| `route-fireworks-multilora-and-rubric` | agent, no model | Route structured JSON tasks behind a edge shim and check outputs with a distinct rubric verifier |

## How to use it

Run `make check` in [code/](code/README.md) to compile with warnings treated as errors and run
all unit tests including Modal VRAM/sandbox checks, loopback `2M TPM` swarm pacing and worked-example recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these tasks through Tessera.
- When `MODAL_TOKEN_ID`, `BASETEN_API_KEY`, `FIREWORKS_API_KEY` and `META_API_KEY` are unset, every receipt honestly reports `mode: local_verified` rather than claiming live cloud execution.
- Partner templates grant no spending authority; workers run live jobs only under explicit owner-authorized credentials and budgets.
