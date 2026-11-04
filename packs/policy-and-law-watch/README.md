# Policy and law watch

## What this pack lets workers do

A collection of nouns and verbs for watching official public sources for new laws and rules on a topic: reading them only through permitted official access, extracting their clauses, writing a summary that cites a clause for every point and is marked not legal advice, having a different worker review every citation, and delivering it only when a person decides.

Check official public sources for new laws and rules on a topic, extract each new text's clauses, and write a plain-language summary that cites a clause for every point and is marked not legal advice. A different worker reviews every citation, and a person decides whether the summary is delivered.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrail: public sources only | Official public sources, read only through the access each source permits |
| Guardrail: no scraping against terms | Read each source's terms first, and stop when they forbid automated reading |
| Guardrail: no personal data | No names, contact details or case details, even when a public source shows them |
| Guardrail: a citation for every claim | Every point cites its clause, page or line; uncited claims are removed |
| Guardrail: a person decides | Workers draft and review; a person decides what is delivered |
| Templates | Watch profile, rule candidates, clause extract, cited summary marked not legal advice, citation review, delivery record |
| Worked examples | A made-up stand-in ordinance, its clause extract and a cited summary, each checked against its template |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `check-sources` | agent | Check official sources for new laws and rules on a topic |
| `extract-clauses` | agent, no model | Extract each new rule's clauses, dates, definitions and duties |
| `write-cited-summary` | agent | Write a plain-language summary that cites a clause for every point |
| `review-citations` | a different agent or a person | Review every citation (a different worker) |
| `decide-delivery` | person | Decide whether the reviewed summary is delivered (a person) |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. The worked examples use made-up stand-in sources only and need no network.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- Summaries are marked not legal advice. Interpreting a rule for any person or organization stays with people.
- The stand-in sources are made-up; the pack names no real source and fetches nothing offline.
