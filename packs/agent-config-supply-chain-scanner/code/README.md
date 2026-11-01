# config_scanner

Standard-library Python supply-chain scanner for repository agent definitions, rule files, MCP
configs, and self-editing memory files (`SOUL.md` / `MemFS`).

## Commands

```bash
python3 -m config_scanner scan /path/to/repo --allow-mcp-commands uvx,node
python3 -m config_scanner diff-memory before_SOUL.md after_SOUL.md
make check
```
