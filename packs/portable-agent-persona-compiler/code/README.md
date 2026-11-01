# persona_compiler

Standard-library Python compiler and linter for portable multi-harness agent role definitions,
delegation description scoring, permission-routing separation, and persona fluff stripping.

## Commands

```bash
python3 -m persona_compiler lint role_spec.json
python3 -m persona_compiler compile role_spec.json --targets claude_code,codex,cursor,opencode
make check
```
