# Volunteer shift schedule kit

## What this pack lets workers do

A collection of nouns and verbs for a disaster relief hub's volunteer shift schedule: registered volunteers matched to posted tasks by skills, availability and recorded training, and one-page site briefings, while placements, site safety and every message to volunteers stay with the coordinator and site lead.

Match registered volunteer codes to posted relief tasks by skills, availability and the training each task requires, leaving gaps unmatched with a reason, and draft a one-page briefing for each site. The coordinator confirms every placement, the site lead decides whether a site is safe, and people do all messaging.

## Nouns

| Noun | What it holds |
| --- | --- |
| Kit | The agent's whole setup as one noun: the step map and pins to every part below |
| Skill `relief-task-matcher` | Suggests volunteer-to-task matches from skills, availability and recorded training, leaving gaps for the coordinator. |
| Skill `shift-briefing-drafter` | Drafts a one-page site briefing with check-in and check-out steps, tasks and gear lists. |
| Read-only tool card `match_volunteers_to_tasks` | Lists candidate volunteer codes for each task by skill, availability and required training, and lists unmatched tasks with reasons. |
| File: Volunteer Roster Template | Coded roster with skills, recorded training, available shifts and an adults-only mark. No names or contact details. |
| File: Relief Site Shift Briefing | One-page briefing rules every volunteer hears before a relief shift, with check-in, check-out and the stop-work line. |
| Checklist | 4 checks a person runs with the kit |
| Sources | 2 dated public sources |
| Test cases | 3 synthetic cases; 2 must go to a person |
| Need, in its own words | One or two plain sentences an organization might say about this work, marked synthetic |
| Templates | suggested volunteer matches and unmatched tasks, a one-page site shift briefing, and a person's step record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `match-volunteers` | agent | Draft the shift schedule from posted tasks and volunteer availability |
| `draft-shift-briefing` | agent | Draft the shift briefing with check-in and check-out steps |
| `confirm-placements` | person | Confirm each volunteer's placement |
| `site-safety-call` | person | Decide site safety and stop or move work |
| `send-shift-assignments` | person | Send shift assignments and briefings to volunteers |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

The marketplace example `examples/kits/11-volunteer-shift-schedule.json` points at this pack's kit and need nouns by
their value digests, so the kit has one source.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The test cases are synthetic. Passing them shows the kit's shape, not that it helps a real organization.
- The tool cards describe read-only tools; this pack ships no tool code.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
