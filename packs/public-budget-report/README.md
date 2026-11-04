# Public budget report

## What this pack lets workers do

A collection of nouns and verbs for reporting on a public state or city budget: finding the official budget document through permitted access, extracting one program area's line items with their pages and lines, writing a report that cites every figure, having a different worker review it, and delivering it only when a person decides.

Find a jurisdiction's official budget document, extract the line items for one program area with their pages and lines, and write a plain report in which every figure is cited and every change is computed from cited figures. A different worker reviews every figure, and a person decides whether the report is delivered.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | The five guardrails of the policy and law watch pack, pinned from it: public sources only, no scraping against terms, no personal data, a citation for every claim, a person decides |
| Templates | Budget source, line items with pages and lines, cited budget report; reviews and delivery records use the policy and law watch templates |
| Worked examples | Two pages of a made-up stand-in city budget, its Library Services line items and a cited report, each checked against its template |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `find-budget-document` | agent | Find the official budget document and read its terms |
| `extract-line-items` | agent, no model | Extract one program area's line items with pages and lines |
| `write-budget-report` | agent | Write a cited report on the program area's budget |
| `review-budget-report` | a different agent or a person | Review every figure in the report (a different worker) |
| `decide-delivery` | person | Decide whether the reviewed report is delivered (a person) |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose the next verb.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and enqueue
the printed task yourself. The worked examples use made-up stand-in sources only and need no network.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- Reports describe figures; they are not financial or legal advice.
- The stand-in budget is made-up; real budgets are read only through access their publishers permit.
