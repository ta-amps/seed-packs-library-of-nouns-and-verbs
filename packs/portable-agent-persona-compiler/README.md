# Portable agent persona compiler

## What this pack lets workers do

A collection of nouns and verbs for compiling portable agent role definitions across coding
harnesses, scoring delegation descriptions, separating routing from permissions, and stripping
accuracy-degrading persona fluff, with tested standard-library Python code. Empirical studies show
expert role-play lines add zero factual accuracy while biographical filler and demographic framing
degrade agentic accuracy by 26 to 30 percentage points, and instructions drift within 8 rounds.
Workers strip degrading fluff, verify prose never grants undeclared tool permissions, score routing
descriptions, and compile one canonical spec cleanly across 8 coding-harness formats.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Hierarchy routes without authorizing; strip demographic/backstory fluff; re-anchor within 8 rounds |
| Compilation and lint rules | Fluff regex classes, 4-part routing description rubric, and 8-harness target mappings |
| Templates | Portable role spec, lint audit report, and multi-harness compiled bundle |
| Record checks | Deterministic checks on compiled role bundles with made-up good and bad fixtures |
| Tool card and code | Tested standard-library Python package in [code/](code/README.md) (`persona_compiler`) |
| Sources | 3 dated public arXiv sources on persona accuracy ablation, irrelevant details, and 8-round drift |
| Worked examples | Made-up read-only schema-auditor compiled across Claude Code, Codex, and OpenCode |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `strip-degrading-persona-fluff` | agent, no model | Remove expert superlatives, novice framing, hobbies, and demographic attributes |
| `score-and-verify-role-contract` | agent, no model | Score delegation description clarity and block undeclared permission claims in prose |
| `compile-multi-harness-role-bundle` | agent, no model | Render deterministic config artifacts and unmapped-field warnings across harnesses |

Each verb can also end with `no_change`, `unknown`, or `blocked`, and proposes follow-up verbs
instead of enqueueing them.

## Limits

- A proposal: not installed, imported, admitted, or activated, and no worker has run these verbs.
- Emits candidate config artifacts in memory or staging output; never overwrites user dotfiles on its own.
- Harnesses evolve frontmatter fields over time; check `warnings` on each compiled target before use.
