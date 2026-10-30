# Deep research report

## What this pack lets workers do

A collection of nouns and verbs for answering a research question with a cited report that states
its limits. Workers frame the question and what would change its answer, plan a search that looks
for evidence against the likely answer, collect sources through permitted access, screen them with
recorded reasons, extract claims with exact quotes and locators, synthesize with every sentence
labeled, have a different worker try to break the synthesis, and write a report with the evidence
against it and what was not searched. A person decides what is delivered.

It informs understanding. To choose what to build or adopt, use the
[prior art and alternatives pack](../prior-art-and-alternatives/README.md); for new laws and rules,
the [policy and law watch pack](../policy-and-law-watch/README.md), whose citation, terms, privacy
and person-decides guardrails this pack pins.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Quote exactly with a locator; the search on the record; look for evidence against the answer; label every sentence; plus four pinned from policy and law watch |
| Permitted access rules | Official APIs first; arXiv's and Crossref's limits; retraction checks; robots.txt; Facebook and Instagram only through Meta's official research tools; no paywall bypass |
| Screening rules | Criteria before screening, two passes, fixed exclusion reasons, retractions excluded, a flow that adds up |
| Evidence strength | Four levels for claims, with what cannot make a claim strong by itself |
| Templates | Research question, search plan, source log, screening log, claim extract, synthesis, adversarial review, report |
| Report checks | Eight checks on a report, with one good and eight bad reports the validator recomputes |
| Checklist, sources, test cases | What a person checks before delivery; 8 dated public sources; 9 synthetic cases |
| Worked example | Synthetic: do community fridges reduce household food waste? From question to report, on three stand-in sources |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `frame-question` | agent | One answerable question, or a pointer to the prior art pack |
| `plan-search` | agent | Sources, queries for and against, criteria and stop rules |
| `collect-sources` | agent, no model | Every query run through permitted access, every text pinned |
| `screen-sources` | agent | Two passes, a reason for every exclusion, a flow that adds up |
| `extract-claims` | agent | Exact quotes with locators, direction and strength |
| `synthesize` | agent | Every sentence labeled source, synthesis or open |
| `adversarial-review` | a different agent or a person | Recheck quotes, find overreach, run missed counter searches |
| `write-report` | agent | The report with its evidence against and its limits |
| `decide-delivery` | person | Deliver or hold the reviewed report |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose follow-up verbs.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the requester's question as a noun. Write the nouns in [nouns.json](nouns.json) create-only
with a key scoped to your team's surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The worked example uses three synthetic stand-in sources and reads no real study. The library's
  tests recheck its quotes, flow counts and citations, not the truth of any claim.
- Evidence strength is a reading aid for the person who decides, not a certification.
- Paywalled, private or login-only sources stay out unless the requester already has access.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
