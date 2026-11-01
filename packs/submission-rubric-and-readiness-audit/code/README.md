# rubric_audit

Standard-library Python auditor for scoring engineering repositories against weighted readiness
rubrics while separating wired source-code model integrations from unverified README claims.

## Commands

```bash
python3 -m rubric_audit audit manifest.json
python3 -m rubric_audit score-directory /path/to/repo --probes probes.json --commits-in-window 8
make check
```
