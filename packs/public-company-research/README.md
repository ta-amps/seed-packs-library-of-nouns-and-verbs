# Public company research

## What this pack lets workers do

A collection of nouns and verbs for researching public companies from official sources, never as
financial advice. Workers fetch filings through the SEC's EDGAR APIs under its fair-access rules
and read a company's investor-relations releases as their terms permit, extract metrics with the
filing, period and unit behind every number, compare periods and peers, summarize risk factors,
build a dated catalyst calendar, and write a cited brief marked Not financial advice. A different
worker reviews every number, and a person decides what is delivered. No verb trades or places an
order. Reviews and delivery records reuse the [policy and law watch pack](../policy-and-law-watch/README.md).

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails, defined once | Not financial advice; no trades or orders; a person decides (pinned from policy and law watch); cite every number; respect each data provider's terms |
| EDGAR access rules | The documented endpoints, a declared User-Agent, a rate well under 10 requests a second, caching, backing off |
| Metric rules | Reported concepts, derived margins, free cash flow and missing quarters, restatements, company-defined measures, peers |
| Risk factor rules | Exact headings from Item 1A, plain categories, year-over-year status, no judgments of likelihood |
| Catalyst rules | Only dated events from official sources; filing deadlines by filer status; no rumors or price levels |
| Templates | Research request, filing index, metric table, comparison, risk factor summary, catalyst calendar, cited brief, brief review |
| Brief checks | Six checks on a brief, with one good and six bad briefs the validator recomputes |
| Checklist, sources, test cases | What a person checks before delivery; 7 dated SEC sources; 9 synthetic cases |
| Worked example | Synthetic: a fictional retailer and a peer, a derived fourth quarter, a restatement, risk factor changes, two dates due by rule and a cited brief |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `fetch-filings` | agent, no model | Filings from EDGAR and investor-relations pages, as their terms permit |
| `extract-metrics` | agent, no model | Every number with its concept, period, unit, form and accession |
| `compare-periods-and-peers` | agent, no model | Changes from two cited values, on aligned periods only |
| `summarize-risk-factors` | agent | Exact headings, plain categories, what changed since last year |
| `build-catalyst-calendar` | agent | Dated events, confirmed or due by a cited rule |
| `write-cited-brief` | agent | A plain brief, every number cited, marked Not financial advice |
| `review-brief` | a different agent or a person | Every number recomputed and every phrase checked |
| `decide-delivery` | person | Deliver or hold the reviewed brief |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose follow-up verbs.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write a research request shaped like `template.research-request`. Write the nouns in
[nouns.json](nouns.json) create-only with a key scoped to your team's surface, then fill a template
from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- Not financial advice. Briefs describe what filings say; any decision about money stays with a person.
- The worked example is synthetic: its companies and identifiers are made up and start with X so they
  never match a real filer. The library's tests recompute its arithmetic and dates, not real filings.
- The SEC's limits and endpoints can change. It may answer with a rate-limit page even at low rates,
  for example from a shared address; the rules say to stop and back off, never to rotate addresses.
- Third-party prices and estimates are out of scope unless the requester licenses them.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
