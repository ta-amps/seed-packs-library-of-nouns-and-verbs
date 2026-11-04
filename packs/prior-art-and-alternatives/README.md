# Prior art and alternatives

## What this pack lets workers do

A collection of nouns and verbs for finding what already exists and what the
alternatives are, before anything new is built. For any brief, a worker searches our
own nouns first, then this library, then outside catalogs, and records what it found,
how well each candidate fits and what it could not search. Another worker lays out at
least three ways forward, always including reuse as is, adapt and do nothing, and
compares them on one rubric. A person, or a rule committed in advance, decides. What is
still missing becomes gap nouns with proposed follow-up verbs, and only the requester
turns proposals into work, under an explicit allowance.

## How it differs from the packs it reuses

| Pack | It covers | This pack adds, and reuses from it |
| --- | --- | --- |
| [Tool discovery](../tool-discovery/README.md) | New tools for named topics | Any brief, inside sources first; reuses discover-repos and run-trial |
| [Code composition](../code-composition/README.md) | Composing tested code nodes instead of rewriting code | Whether to compose, adapt or build at all; points data-step builds at compose-recipe first |
| [Taste palettes](../taste-palettes/README.md) | Options side by side and a person's choice | Reuse, adapt, build or do nothing; reuses draft-embodiments and record-choice when taste decides |
| [Decomposition patterns](../decomposition-patterns/README.md) | Breaking one goal into child verbs | Whether to build at all, and limits on follow-ups; reuses propose-breakdown for a build in parts |
| [Freshness checks](../freshness-checks/README.md) | Staleness of versions nouns already pin | Refreshing surveys; reuses scan-staleness for what a chosen option pins |
| [Benchmark scores](../benchmark-scores/README.md) | Current, reproduced scores | Reuses compare-on-profile when a number decides |
| [Evaluation design](../evaluation-design/README.md) | Fair, pre-registered evaluations | Reuses design-evaluation and commit-pass-marks before any trial |
| [Repository review](../repo-review/README.md) | Evidence-backed review of one repository | Choosing between options first; reuses profile-repo |

## Nouns

| Noun | What it holds |
| --- | --- |
| Survey method | Order (own nouns and the fabric, this library, outside), stop rules, match levels, freshness and refresh rules |
| Source catalog | Eleven sources, from search_nouns and execution recall to package indexes, papers and a hackathon directory, each with how to read it and how long it stays fresh |
| Fit rubric | Acceptance checks and license as hard gates, then maintenance, security, cost and effort to adapt; no combined score |
| License rules | Link and pin; never copy unlicensed code; copyleft and custom licenses go to a person |
| Survey-first rule | A build verb needs a fresh survey of its brief, or proposes survey-existing first |
| 8 templates | Brief, survey, alternatives, comparison, decision, gap, allowance and triage ledger |
| Worked example: this pack | Its own prior-art check: a real survey of this library, then its alternatives, comparison and decision |
| Worked example: PII | A real survey of a hackathon directory of about 740 repositories for a PII redaction tool: seven candidates with licenses and evidence paths, unranked |

## Verbs

| Verb | Who | What happens | Produces |
| --- | --- | --- | --- |
| survey-existing | agent | Searches inside sources before outside ones and records every query | Survey |
| research-alternatives | agent | Three to six options, always reuse as is, adapt and do nothing | Alternatives |
| compare-alternatives | agent | Rubric rows side by side; proposes palettes or trials from other packs | Comparison |
| decide | person or rule | Picks an option, says why and what would reopen it | Decision |
| propose-follow-ups | agent | Turns unmet checks into gaps, each with one proposed verb | Gaps |
| triage-proposals | requester | Admits proposals within the allowance; enqueues nothing itself | Ledger version |
| refresh-survey | agent | Re-reads changed or expired sources and supersedes the survey | Survey |

Each verb can also end with `no_change`, `unknown` or `blocked`. Workers write nouns and
propose verbs; they never enqueue.

## Turning proposals into work

`triage-proposals` is the requester's own management verb, not a server agent. It reads
an allowance noun naming a queue, verb kinds, maximum depth, children per task, attempts
per gap, a total, a spending cap and an expiry date (defaults: depth 3, six children,
four attempts per gap). It fingerprints each proposal, marks duplicates of fresh surveys
and closed gaps, holds anything that would break a limit, and records the rest as
admitted in the one ledger noun the allowance names, by compare-and-set, so two triage
runs cannot spend one budget twice. The requester then enqueues each admitted entry with its own grants under its
recorded task id, so a repeat creates nothing new. Without a valid allowance, triage
proposes only.

## How to use it

Write a brief shaped like `template.brief`. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: no worker has run these verbs, and nothing is admitted or measured.
- The worked surveys read local copies offline. The library survey skipped our own nouns,
  execution memory and outside catalogs; the PII survey searched one outside source and
  ran no candidate, so detection and redaction quality stay unknown. Each says so.
- Examples are checked against their templates' shapes only; the ledger and allowance
  examples are made-up, with placeholder digests.
- Surveys only read; nothing signs up, logs in or contacts anyone.
- No scheduler is activated; refreshes wait for an authorized schedule.
