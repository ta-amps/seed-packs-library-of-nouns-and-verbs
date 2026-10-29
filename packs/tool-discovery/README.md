# Tool discovery

## What this pack lets workers do

Keep up with new tools for motion graphics, video editing and generation, 3D, agent
memory and agent harnesses without reading every feed yourself. Workers find good
sources, scan them, turn real releases into candidate cards, check hard limits first,
run a small fair trial on your own hardware only for shortlisted tools, and write an
adopt or no-change decision with the evidence behind it.

## Nouns

| Noun | What it holds |
| --- | --- |
| Profile template and a synthetic example | Topics, interfaces, observed hardware, hard constraints, ranked preferences, budgets and allowed licenses |
| 8 source cards | Suggested starting sources (five arXiv category feeds, a GitHub release-feed pattern, FFmpeg news, Blender releases), all marked untested |
| Source card, scan batch, candidate card, trial result and decision templates | The shapes the verbs produce |
| 6 comparable-trial definitions | Motion graphics, video editing, video generation, 3D, agent memory and harnesses: task, fixtures, baseline, metrics and pass marks |
| Daily scan schedule | A proposal: daily at 13:00 UTC, one outstanding scan, skip missed windows; not activated |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| discover-sources | Probes candidate sources once and records which respond | Source cards |
| scan-source | Fetches one source with a qualified collector; no model per item | Scan batch |
| propose-candidate | Groups items about one release, checks hard limits first, shortlists | Candidate cards |
| run-trial | Baseline and candidate twice each, in a sandbox, on your hardware | Trial result |
| decide | Adopt, trial more, watch, reject or no change, with a recheck trigger | Decision |

Each verb can also end with `no_change`, `unknown` or `blocked`. Most scanned items
should stop at a cheap relevance check.

## Recurring runs

Recurring execution needs Tessera's flag-gated schedule support, which is being
designed now. **No scheduler is activated by this pack.** The schedule noun only
describes what a future, authorized schedule adapter would enqueue: one `scan-source`
per source per day, with duplicate ticks never creating duplicate tasks.

## How to use it

Replace the synthetic profile with a pinned profile of your real project and machine,
write the nouns in [nouns.json](nouns.json) create-only, then fill `discover-sources`
from [verbs.json](verbs.json) with `scripts/build_packs.py --instantiate` and enqueue it
yourself. Trials use pass marks committed first, shaped by the
[evaluation-design pack](../evaluation-design/README.md).

## Limits

- Source addresses are untested suggestions until `discover-sources` verifies them.
- A decision never adopts anything; `adoption_authorized` is always false.
- Candidates run only inside a sandbox with no credentials. No verb signs up,
  subscribes, buys or logs in anywhere.
- Vendor and author claims stay "reported, not reproduced" until a trial reproduces them.
