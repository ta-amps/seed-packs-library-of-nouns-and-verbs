# Agent config supply chain scanner

## What this pack lets workers do

A collection of nouns and verbs for scanning repository agent definitions, rule files, MCP configs,
and self-editing memory files for hidden Trojan Unicode, unapproved hook or server escalation,
built-in name shadowing, and authority spoofing, with tested standard-library Python code. Agent
frontmatter, `.cursor` or `.claude` rules, `.mcp.json` files, and evolving `SOUL.md` memory act as
executable configuration when opening a cloned repository. Workers inventory every harness config,
decode hidden Unicode Tag or bidi characters, block unapproved hooks and MCP shell commands, detect
reserved subagent shadowing, and diff-gate self-edited memory before persistence.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Treat clone configs as untrusted code; block hidden Unicode; diff-gate self-editing memory |
| Signature and escalation rules | Bidi/Tag/zero-width codepoints, reserved built-in names, hook keys, and MCP checks |
| Templates | Repository config scan report, supply-chain threat tombstone, and memory diff gate receipt |
| Record checks | Deterministic checks on supply-chain scan reports with made-up good and bad fixtures |
| Tool card and code | Tested standard-library Python package in [code/](code/README.md) (`config_scanner`) |
| Sources | 3 dated public sources on Trojan Source (CVE-2021-42574), NVD CVE-2025-54135, and Unicode TR36 |
| Worked examples | Made-up blocked scan catching Unicode Tag ASCII smuggling and MCP shell escalation |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `scan-repo-agent-configs` | agent, no model | Inventory and scan agent, rule, and MCP files for Unicode, hooks, shadowing, and spoofing |
| `gate-self-editing-memory-diff` | agent, no model | Audit `SOUL.md` or memory block diffs for injected overrides, URLs, or hidden codepoints |
| `quarantine-supply-chain-finding` | agent | Record a failure tombstone blocking unsafe repository configs until remediated |

Each verb can also end with `no_change`, `unknown`, or `blocked`, and proposes follow-up verbs
instead of enqueueing them.

## Limits

- A proposal: not installed, imported, admitted, or activated, and no worker has run these verbs.
- Static config scanning catches known Unicode, hook, MCP, shadowing, and spoofing vectors; human
  code review is still required before executing untrusted repositories outside a sandbox.
- Never modifies or deletes repository files automatically; emits findings and tombstones only.
