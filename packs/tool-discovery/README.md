# Tool discovery

## What this pack lets workers do

A collection of nouns and verbs for discovering, trialing and deciding on new tools,
for motion graphics, video editing and generation, 3D, agent memory and agent
harnesses. Workers find sources and new repositories, scan them, turn real releases
into candidate cards, check hard limits first, run a small fair trial on your own
hardware only for shortlisted tools, decide adopt or no change, and refresh cards and
decisions when they go stale.

## Nouns

| Noun | What it holds |
| --- | --- |
| Profile template and a synthetic example | Topics, interfaces, observed hardware, hard constraints, ranked preferences, budgets and allowed licenses |
| 8 source cards | Suggested starting sources (five arXiv category feeds, a GitHub release-feed pattern, FFmpeg news, Blender releases), all untested |
| Templates | Source card, scan batch, candidate card, trial result and decision |
| 6 comparable-trial definitions | Motion graphics, video editing, video generation, 3D, agent memory and harnesses |
| Daily schedule | A proposal: scans and one refresh daily at 13:00 UTC; not activated |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| discover-sources | Probes candidate sources once and records which respond | Source cards |
| discover-repos | Finds new repositories for the profile's topics | Candidate cards |
| scan-source | Fetches one source with a qualified collector; no model per item | Scan batch |
| propose-candidate | Groups items about one release, checks hard limits first, shortlists | Candidate cards |
| run-trial | Baseline and candidate twice each, in a sandbox, on your hardware | Trial result |
| decide | Adopt, trial more, watch, reject or no change, with a recheck trigger | Decision |
| refresh-candidates | Rechecks stale cards and decisions and proposes trials where something changed | New versions |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose
follow-up verbs, such as a trial for a changed candidate.

## Recurring runs

Recurring execution needs Tessera's flag-gated schedule support, which is being
designed now. **No scheduler is activated by this pack.** The schedule noun only
describes what a future, authorized schedule adapter would enqueue.

## How to use it

Replace the synthetic profile with a pinned profile of your real project and machine. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.
Trials use pass marks committed first, shaped by the [evaluation-design pack](../evaluation-design/README.md).

## Limits

- Source addresses are untested suggestions until `discover-sources` verifies them.
- A decision never adopts anything; `adoption_authorized` is always false.
- No verb signs up, subscribes, buys or logs in anywhere.
