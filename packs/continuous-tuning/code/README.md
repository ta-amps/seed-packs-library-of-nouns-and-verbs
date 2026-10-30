# Promotion check

Recomputes a continuous-tuning promotion decision from its evaluations, so a reviewer can check it
without the trainer's code: the SHA-256 counter draws, the paired bootstrap, the pre-registered
rule's checks and outcome, a frozen test receipt against its rows, and contamination counts.
Python 3.10 or later, standard library only.

```bash
make check                                      # compile, then every test
python -m promotion_check decide --rule RULE.json --evaluations EVALS.json --integrity INTEGRITY.json
python -m promotion_check digest RULE.json
```

Its draws, bootstraps and decisions match Tessera's `examples/continuous_tuning` at commit
`2e7d6ab4d7e084a413ba0c3c83cebc10d81c9a98`; `tests/test_compatibility.py` pins values recorded from
that code. The other tests recompute the pack's worked example from [source.json](../source.json).
Nothing here trains, loads or calls a model, opens a network connection or moves a champion pointer.
MIT license, written for this pack by ta-amps.
