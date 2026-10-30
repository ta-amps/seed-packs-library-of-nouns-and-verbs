# Victim support referral kit

## What this pack lets workers do

A collection of nouns and verbs for a victim services program's referral kit: referral options drafted from a public services directory by service type, language, hours and access needs, and a plain referral checklist, while every conversation, safety step, decision and contact stays with trained advocates and nothing accuses anyone.

Prepare referral options from a public services directory, filtered only by the service needs an advocate enters, with each entry's last verified date, and draft a plain checklist for the referral. The agent never sees a person's story, name, contact details or location. Trained advocates hold every conversation, do all safety planning, and make every referral with the person's consent.

## Nouns

| Noun | What it holds |
| --- | --- |
| Kit | The agent's whole setup as one noun: the step map and pins to every part below |
| Skill `referral-options-assistant` | Prepares referral options from a public services directory by service type, language, hours and access needs, with each entry's last verified date. |
| Read-only tool card `filter_service_directory` | Filters a public services directory by service type, language, hours and access needs, and flags entries not verified recently. |
| File: Referral Options Sheet | One row per matching service from the public directory, with languages, hours, cost, access features, intake as listed and the last verified date. No details about the person. |
| File: Referral Checklist for Advocates | What an advocate confirms with a service before a referral, ending with the person's choice and consent. |
| Checklist | 4 checks a person runs with the kit |
| Sources | 3 dated public sources |
| Test cases | 3 synthetic cases; 2 must go to a person |
| Need, in its own words | One or two plain sentences an organization might say about this work, marked synthetic |
| Templates | referral options matched to entered service needs, what the advocate confirms before a referral, and a person's step record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `draft-referral-options` | agent, no model | Draft referral options from the public services directory |
| `draft-referral-checklist` | agent | Draft the referral checklist for the advocate |
| `support-conversation` | person | Hold the support conversation |
| `safety-planning` | person | Do safety planning with the person |
| `make-referral` | person | Decide and make the referral with the person's consent |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

The marketplace example `examples/kits/08-victim-support-referrals.json` points at this pack's kit and need nouns by
their value digests, so the kit has one source.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The test cases are synthetic. Passing them shows the kit's shape, not that it helps a real organization.
- The tool cards describe read-only tools; this pack ships no tool code.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
