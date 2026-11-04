# Donor thank-you letters kit

## What this pack lets workers do

A collection of nouns and verbs for a small nonprofit's agent kit that drafts donor thank-you letters from a coded gift list with the finance lead's acknowledgment wording and checks donors' privacy choices first, while staff decide special handling and sign every letter.

Check a coded gift list for each donor's anonymous, mail and listing choices, hold rows with a missing choice, and draft one thank-you letter per gift with merge fields for names and the finance lead's acknowledgment wording word for word. The development lead decides special handling, the finance lead confirms the wording, and staff sign every letter.

## Nouns

| Noun | What it holds |
| --- | --- |
| Kit | The agent's whole setup as one noun: the step map and pins to every part below |
| Skill `donor-letter-drafter` | Drafts personal thank-you letters from a coded gift list, keeping names and addresses as merge fields. |
| Skill `gift-list-privacy-checker` | Checks a coded gift list for missing privacy choices and rows that must not get a letter or a public listing. |
| Read-only tool card `check_gift_list_privacy` | Lists gift rows with missing privacy choices, rows marked no mail or anonymous, and rows with goods or services given in return. |
| File: Coded Gift List | Gift rows by code with date, amount, program, privacy choices and the value of any goods given in return. Names and addresses stay in the donor system. |
| File: Thank-You Letter Template | Letter template with merge fields for the donor's name and address, and a place for the finance lead's acknowledgment wording. |
| Checklist | 4 checks a person runs with the kit |
| Sources | 2 dated public sources |
| Test cases | 2 made-up cases; 1 must go to a person |
| Need, in its own words | One or two plain sentences an organization might say about this work, marked made-up |
| Templates | privacy check results for a coded gift list, thank-you letter drafts with merge fields, and a person's step record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `check-privacy-choices` | agent, no model | Check the gift list against donors' privacy choices |
| `draft-letters` | agent | Draft a thank-you letter for each gift |
| `decide-special-handling` | person | Decide special handling for donors |
| `confirm-acknowledgment-wording` | person | Confirm the gift acknowledgment wording |
| `sign-and-send` | person | Sign and send each letter |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

The marketplace example `examples/kits/13-donor-thank-you-letters.json` points at this pack's kit and need nouns by
their value digests, so the kit has one source.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The test cases are made-up. Passing them shows the kit's shape, not that it helps a real organization.
- The tool cards describe read-only tools; this pack ships no tool code.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
