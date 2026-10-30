# Flyer translation check kit

## What this pack lets workers do

A collection of nouns and verbs for a community center's agent kit that checks translated service flyers against the English source for dropped facts, changed numbers, dates and phone numbers, untranslated text and reading level, while a fluent community reviewer approves each language and staff decide what gets printed.

Check each translated service flyer against its English source: every fact present, numbers, dates, times and phone numbers matching exactly, words left in English, and sentences above the reading level. The agent lists questions for a fluent community reviewer, who approves each language; staff decide what gets printed and put up.

## Nouns

| Noun | What it holds |
| --- | --- |
| Kit | The agent's whole setup as one noun: the step map and pins to every part below |
| Skill `flyer-fact-checker` | Compares a translated flyer with its English source for dropped or changed facts, exact numbers and dates, and untranslated text. |
| Read-only tool card `compare_flyer_facts` | Extracts dates, times, phone numbers and amounts from the source and each translation and lists any that differ or are missing. |
| File: Translation Review Sheet | What a fluent community reviewer confirms for each language before a flyer is printed. |
| File: Flyer Fact List | One row per fact and language: the source text, the translated text and whether it matches, changed or is missing. |
| Checklist | 3 checks a person runs with the kit |
| Sources | 2 dated public sources |
| Test cases | 2 synthetic cases; 1 must go to a person |
| Need, in its own words | One or two plain sentences an organization might say about this work, marked synthetic |
| Templates | facts compared across a flyer's languages, questions for the fluent reviewer of one language, and a person's step record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `compare-facts` | agent, no model | Compare facts across the source and each translation |
| `draft-reviewer-questions` | agent | Draft questions for the fluent reviewer |
| `fluent-review` | person | Approve each translation (fluent community reviewer) |
| `print-and-post` | person | Decide what gets printed and posted |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

The marketplace example `examples/kits/14-multilingual-flyer-translation-check.json` points at this pack's kit and need nouns by
their value digests, so the kit has one source.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The test cases are synthetic. Passing them shows the kit's shape, not that it helps a real organization.
- The tool cards describe read-only tools; this pack ships no tool code.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
