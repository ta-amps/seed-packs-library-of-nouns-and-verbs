# Handwritten statements to text kit

## What this pack lets workers do

A collection of nouns and verbs for turning handwritten statements and forms dropped into a folder into text typed exactly as written, keeping the writer's slang, spelling, acronyms and words, flagging every uncertain reading for a person, and listing acronyms against a local glossary, while staff check every flag, follow up on safety, sign off and decide any use.

Type each handwritten page in a drop folder exactly as written, keeping slang, spelling, grammar, acronyms, crossings-out and the writer's own words, and flag every word the agent is unsure of. A local acronym glossary helps readers without ever changing the text. A person checks every flag against the page, trained staff follow up on anything about safety, and the program lead signs off and decides how a statement is used.

## Nouns

| Noun | What it holds |
| --- | --- |
| Kit | The agent's whole setup as one noun: the step map and pins to every part below |
| Skill `verbatim-transcriber` | Types handwritten pages exactly as written and flags every uncertain reading for a person. |
| Skill `acronym-glossary-assistant` | Lists acronyms and local terms in a transcription with their glossary meanings, without changing the text. |
| Read-only tool card `list_dropped_pages` | Lists the page images in the intake drop folder with page numbers, sizes and SHA-256 digests, without moving or changing them. |
| File: Verbatim Transcription Rules | The rules every transcription follows: type exactly what is written, flag what is uncertain, and leave the writer's words alone. |
| File: Transcription Sheet | One row per written line: the batch, page, line, the text as written, whether it holds a flag, the alternatives and whether a reviewer checked it. |
| File: Local Acronym Glossary | Acronyms, local terms and common writing abbreviations with their meanings, as a reading aid that never changes a transcription. |
| Checklist | 5 checks a person runs with the kit |
| Sources | 1 dated public sources |
| Test cases | 4 made-up cases; 2 must go to a person |
| Need, in its own words | One or two plain sentences an organization might say about this work, marked made-up |
| Templates | one page typed exactly as written, with every flag located, acronyms and local terms found in a transcription, and a person's step record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `transcribe-pages` | agent | Type each page exactly as written |
| `list-acronyms` | agent, no model | List acronyms and local terms against the glossary |
| `verify-readings` | person | Check every flagged reading against the original page |
| `safety-follow-up` | person | Follow up in person when a statement raises safety |
| `sign-off-statement` | person | Sign off the transcription and decide how it is used |
| `share-statement` | person | Share a statement outside the organization |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

The marketplace example `examples/kits/07-handwritten-statements-to-text.json` points at this pack's kit and need nouns by
their value digests, so the kit has one source.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The test cases are made-up. Passing them shows the kit's shape, not that it helps a real organization.
- The tool cards describe read-only tools; this pack ships no tool code.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
