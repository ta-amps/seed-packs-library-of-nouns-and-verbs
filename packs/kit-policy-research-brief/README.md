# Policy research brief kit

## What this pack lets workers do

A collection of nouns and verbs for a small nonprofit's policy research brief: a new public rule or ordinance summarized in plain language with a citation to the clause behind every point, quotes checked against the official text, and open questions where the text is unclear, while what a rule means for the organization or any person, and anything shared publicly, stays with staff and counsel.

Number a new public rule's sections and clauses as the official text does, pull out dates, definitions and duties, and draft a plain-language brief in which every point cites its clause and every quote matches the official text word for word. Staff, with counsel when needed, decide what the rule means for the organization or any person, and the director decides what is shared.

## Nouns

| Noun | What it holds |
| --- | --- |
| Kit | The agent's whole setup as one noun: the step map and pins to every part below |
| Skill `policy-brief-drafter` | Turns an official rule's text into a plain-language brief that cites a clause for every point. |
| Read-only tool card `index_rule_clauses` | Numbers the sections and clauses of an official rule text and extracts dates, defined terms and duty sentences with their clause numbers. |
| File: Policy Brief Outline | Five-section outline for a cited plain-language brief, ending with open questions for staff and counsel. |
| File: Clause Citation Log | One row per point in the brief: the sentence, the clause it cites, the quoted words and whether they match the official text. |
| Checklist | 4 checks a person runs with the kit |
| Sources | 3 dated public sources |
| Test cases | 3 synthetic cases; 1 must go to a person |
| Example request | What an organization might type when it asks for this kit, marked synthetic |
| Templates | an index of a rule's clauses, dates, definitions and duties, a plain-language rule brief with a citation for every point, a citation check of a brief against the official text, and a person's step record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `index-clauses` | agent, no model | Number the rule's clauses and pull out dates, definitions and duties |
| `draft-brief` | agent | Draft the plain-language brief with a citation for every point |
| `check-citations` | agent, no model | Check every citation and quote against the official text |
| `interpret-for-us` | person | Decide what the rule means for the organization |
| `share-brief` | person | Share the brief with staff, partners or the public |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. Workers need keys on the same surface.

The marketplace example `examples/kits/09-policy-research-brief.json` points at this pack's kit and example request
nouns by their value digests, so the kit has one source.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The test cases are synthetic. Passing them shows the kit's shape, not that it helps a real organization.
- The tool cards describe read-only tools; this pack ships no tool code.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
