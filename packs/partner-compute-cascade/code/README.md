# Partner compute cascade (`partner_cascade`)

Executable runners, dry-run validators and deterministic simulators for Modal, Baseten, Fireworks AI and Meta open-weight models (Muse Glimmer 30B and Meta's open-weight 3B model).

## Modules
- `modal_qlora_and_sandbox.py`: Runnable Modal app for isolated container sandbox verification, serverless A100/L4 QLoRA fine-tuning (`Muse-Glimmer-30B` and Meta's open-weight 3B model), and `@modal.fastapi_endpoint` serving, with `--dry-run-validate` when `MODAL_TOKEN_ID` is unset.
- `baseten_2m_tpm_swarm.py`: Async sliding token-bucket (`<= 2,000,000 TPM`) worker swarm client with fenced lease pre-flight safety, `429 Retry-After` attempt preservation and loopback mock-server verification.
- `fireworks_multilora_shim.py`: Sub-2ms deterministic edge shim plus specialist multi-LoRA structured JSON router and distinct-adapter rubric verifier following Sinan Ozdemir's agentic routing patterns.
- `cascade_simulator.py`: End-to-end validation and `$100 + $100 + $100` partner credit throughput envelope calculator, emitting honest `local_verified` vs `live_api` receipts.

## Verification
```bash
make check
```
