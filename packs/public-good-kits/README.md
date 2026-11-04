# Public-good kits

## What this pack lets workers do

A collection of nouns and verbs for building agent kits that nonprofits can use. Workers
turn one need into a small, tested kit: skill instructions, read-only tool definitions,
prompts, ready-to-use files and made-up test cases. The drafting worker checks its own
work, a different worker reviews it, accessibility and translations are checked, and a
person, the steward, decides whether to release it.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | One need per kit, tools read and people act, made-up data only, drafter never reviews |
| Self-checks | Seven deterministic checks, from file digests to read-only tools and hand-offs |
| Accessibility criteria | Plain language, structure, text alternatives, no color-only cues, printable, languages |
| Templates | Need brief, kit manifest, skill file, MCP tool, prompt file, test cases, self-check, review, accessibility check, translation and release record |

Steps that must stay with people: interviewing a client, crisis and safety planning,
deciding eligibility or legal position, filing anything, and contacting a person.

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| frame-need | agent | One need, its users, a success measure and the human-only steps |
| draft-kit | agent | Skill, tool, prompt and file drafts with a pinned manifest |
| write-test-cases | agent | Made-up normal, edge, hand-off, refusal and adversarial cases |
| self-check | the drafter | Runs every deterministic self-check |
| independent-review | a different agent | Reviews the files, cases and self-check |
| check-accessibility | agent or person | Checks the criteria and proposes translations |
| translate-kit | agent | One language at a time; tool names and schemas unchanged |
| steward-release | person | Decides release or hold with the evidence |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.

## How to use it

Write the organization's request as a noun with real details removed. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: no kit has been built with these verbs yet.
- Releasing into a catalog follows that catalog's own reviewed path after the steward decides.
