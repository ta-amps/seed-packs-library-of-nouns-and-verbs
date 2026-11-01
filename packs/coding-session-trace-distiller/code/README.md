# session_distiller

Standard-library Python tools for sanitizing coding-session JSONL transcripts and mining reusable
failure tombstones, tool-error loops, verified fix recipes, and prompt-shim candidates.

## Commands

```bash
python3 -m session_distiller redact session.jsonl
python3 -m session_distiller distill session.jsonl --session-id run-01 --min-loop-repeats 2
make check
```
