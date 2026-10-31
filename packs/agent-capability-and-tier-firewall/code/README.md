# tier_firewall

Standard-library Python pre-dispatch firewall enforcing ordered effect-class ceilings, path and
store allowlists, credential and high-entropy secret redaction, and model data-tier routing guards
(blocking internal, confidential, or secret payloads from training-enabled or contributor-shared
endpoints).

## Commands

```bash
python3 -m tier_firewall evaluate request.json --policy policy.json
make check
```
