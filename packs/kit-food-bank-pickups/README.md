# Food bank inventory and pickup kit

## What this pack lets workers do

A collection of nouns and verbs for a food bank's agent kit: weekly stock counts turned into a restock and use-first list, and booked pickup slots spread across volunteer shifts, while household exceptions and reminders stay with the coordinator.

Turn a food bank's weekly stock counts into a restock and use-first list, and spread its booked pickup slots across volunteer shifts. The agent drafts both from coded sheets; the pantry coordinator decides every household exception and does every reminder call or text.

## Nouns

| Noun | What it holds |
| --- | --- |
| Kit | The agent's whole setup as one noun: the step map and pins to every part below |
| Skill `pickup-plan-drafter` | Drafts a weekly restock and use-first list and a balanced pickup plan from stock counts and booked slot codes. |
| Read-only tool card `summarize_stock_and_slots` | Totals stock counts by item and area, lists items below restock level and inside the use-first window, and counts booked slots per pickup window. |
| File: Weekly Stock Count Sheet | Count sheet by item and storage area, with restock levels and the date label a person checks. No personal data. |
| File: Pickup Slot Sheet | Slot codes, pickup windows and the other windows each household said would work, with no names or contact details. |
| Checklist | 4 checks a person runs with the kit |
| Sources | 2 dated public sources |
| Test cases | 3 made-up cases; 1 must go to a person |
| Need, in its own words | One or two plain sentences an organization might say about this work, marked made-up |
| Templates | a draft restock and use-first list for one week, a draft pickup plan by window, with suggested moves and open exceptions, and a person's step record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `count-stock` | agent, no model | Total this week's stock counts and flag items to hand out first |
| `plan-pickups` | agent | Spread booked pickup slots across volunteer shifts |
| `decide-exceptions` | person | Decide household exceptions, such as extra food or a late pickup |
| `send-reminders` | person | Send pickup reminders and schedule changes to households |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

The marketplace example `examples/kits/12-food-bank-pickup-scheduling.json` points at this pack's kit and need nouns by
their value digests, so the kit has one source.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The test cases are made-up. Passing them shows the kit's shape, not that it helps a real organization.
- The tool cards describe read-only tools; this pack ships no tool code.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
