# Taste palettes

## What this pack lets workers do

A collection of nouns and verbs for comparing options side by side and keeping a
person's choice. Workers make two to four versions of one brief, each with different
adjustable settings, such as how formal or how compact. Any website, app, chat client
or command line can show them side by side. A person picks one or none; the choice
becomes a preference noun that later work uses within its scope, and later choices can
confirm or contradict it.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | Change one to three settings at a time, two to four options, plain labels, shuffled order, always a none option |
| Templates | Brief, option (embodiment), comparison sheet, preference and preference summary |
| Example brief | Synthetic: the tone of a README's first screen, with formality and density as settings |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| draft-embodiments | agent | Makes one option from one settings vector; one attempt per option |
| assemble-comparison | agent | Puts options side by side with a recorded shuffle; deterministic |
| record-choice | person | Picks an option or none, optionally with a reason in their own words |
| update-preferences | agent | Counts agreement with earlier choices and lists contradictions |
| apply-preference | agent | Uses in-scope preferences in new work and says which it applied |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose
follow-up verbs, such as another palette when a choice was close.

## How to use it

Write a brief shaped like `template.brief`. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- Only a person records a choice, and silence is never a preference.
- Preferences stay in the person's scope and apply only until their recheck date.
- One choice gives low confidence; it is a gentle default, not a rule.
