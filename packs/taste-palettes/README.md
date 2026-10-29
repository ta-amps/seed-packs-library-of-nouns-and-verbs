# Taste palettes

## What this pack lets workers do

When the right answer is a matter of taste, workers make two to four versions of the
same brief, each with different adjustable settings (for example, how formal or how
compact), and show them side by side on any surface: a website, an app, a chat client
or a command line. A person picks one or none. The choice becomes a preference noun
that later work can use, within its scope, and later choices can confirm or contradict.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | Change one to three settings at a time, two to four options, plain labels, shuffled order, always a none option |
| Templates | Brief, option (embodiment), comparison sheet, preference and preference summary |
| Example brief | Synthetic: the tone of a README's first screen, with formality and density as settings |

## Verbs

| Verb | Who | What happens | Produces |
| --- | --- | --- | --- |
| draft-embodiments | agent | Makes one option from one settings vector; one attempt per option | Option |
| assemble-comparison | agent | Puts options side by side with a recorded shuffle; deterministic | Comparison sheet |
| record-choice | person | Picks an option or none, optionally with a reason in their own words | Preference |
| update-preferences | agent | Counts agreement with earlier choices and lists contradictions | Preference summary |
| apply-preference | agent | Uses in-scope preferences in new work and says which it applied | Option |

Each verb can also end with `no_change`, `unknown` or `blocked`.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only, write a brief shaped like
`template.brief`, then fill `draft-embodiments` from [verbs.json](verbs.json) once per
option with `scripts/build_packs.py --instantiate` and enqueue them yourself.

## Limits

- Only a person records a choice, and silence is never a preference.
- Preferences stay private and apply only in their scope until their recheck date.
- One choice gives low confidence; it is a gentle default, not a rule.
