# Seed-pack library – every pack of nouns and verbs

Instructions and synthetic examples for contributing useful noun records and
verb seeds to the [Tessera work fabric](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine).
This repository is a guide and a library of seed packs, not an importer or service.
A pack may include tested code as nouns, in `packs/<pack>/code/`. The library never runs pack code except in its own CI tests; workers run it under their own permissions. Reading, exporting or importing a pack still runs nothing, activates nothing, publishes nothing and grants nothing.

A pack groups related inputs, reusable procedures, tools, resources and bounded
work contracts. Nouns hold versioned data and evidence. Verbs request an outcome
from an authorized worker. Both use Tessera's existing identity, namespaces,
storage, queues, leases and receipts.

## Seed pack library

The [packs/](packs/README.md) folder holds seventy-five proposed seed packs. Each is a
collection of nouns (knowledge, templates, tool cards and examples) and verbs (work an
authorized worker can claim), named in plain English and kept separate from any surface.
They are proposals and validated examples, **not installed, imported, admitted or
activated**, and no worker has run them yet.

| Pack | A collection of nouns and verbs for |
| --- | --- |
| [Repository review](packs/repo-review/README.md) | Reviewing a repository with 50 evidence-requiring questions |
| [Video and motion with code](packs/video-motion/README.md) | Video and motion made with code: seeking frames, fitting motion, compiling, rendering and checking |
| [Video showcase](packs/video-showcase/README.md) | Making a truthful demo video, from script to review and release |
| [Visual and 3D rendering](packs/visual-rendering/README.md) | Rendering images, motion graphics and 3D scenes and checking them |
| [Tool discovery](packs/tool-discovery/README.md) | Discovering, trialing, deciding on and refreshing new tools |
| [Prior art and alternatives](packs/prior-art-and-alternatives/README.md) | Finding what already exists and what the alternatives are, before anything new is built |
| [Benchmark scores](packs/benchmark-scores/README.md) | Keeping benchmark scores current and comparable |
| [Freshness checks](packs/freshness-checks/README.md) | Finding stale, deprecated or end-of-life knowledge |
| [Evaluation design](packs/evaluation-design/README.md) | Fair, pre-registered evaluations with exact-match scoring |
| [Checks of checks](packs/checks-of-checks/README.md) | Proving a test or rubric works before trusting it |
| [Decomposition patterns](packs/decomposition-patterns/README.md) | Breaking work into verbs with reusable patterns |
| [Code composition](packs/code-composition/README.md) | Composing verified code without rewriting it |
| [Taste palettes](packs/taste-palettes/README.md) | Comparing options side by side and keeping a person's choice |
| [Public-good kits](packs/public-good-kits/README.md) | Building agent kits that nonprofits can use |
| [Exploitation evidence](packs/exploitation-evidence/README.md) | Spotting exploitation and scams in synthetic cases, never accusing anyone |
| [Harness onboarding](packs/harness-onboarding-e2e/README.md) | Connecting an agent harness and proving its lifecycle |
| [Security review](packs/security-review/README.md) | Authorized, local-only security review of code |
| [Cost optimization](packs/cost-optimization/README.md) | Finding and measuring cost savings |
| [Docs improvement](packs/docs-improvement/README.md) | Making documentation clearer for a named reader |
| [Findings to fixes](packs/findings-to-fixes/README.md) | Turning every noticed error, issue, design flaw or annoyance into recorded, fixed and verified work |
| [Monthly program impact report kit](packs/kit-monthly-impact-report/README.md) | A community nonprofit's monthly program impact report |
| [Handwritten statements to text kit](packs/kit-handwritten-statements/README.md) | Turning handwritten statements and forms dropped into a folder into text typed exactly as written, keeping the writer's slang, spelling, acronyms and words, flagging every uncertain reading for a person, and listing acronyms against a local glossary, while staff check every flag, follow up on safety, sign off and decide any use |
| [Funding impact summary kit](packs/kit-funding-impact-summary/README.md) | A funding impact summary in a grant renewal |
| [Policy research brief kit](packs/kit-policy-research-brief/README.md) | A small nonprofit's policy research brief |
| [Victim support referral kit](packs/kit-victim-support-referrals/README.md) | A victim services program's referral kit |
| [Volunteer shift schedule kit](packs/kit-volunteer-shift-schedule/README.md) | A disaster relief hub's volunteer shift schedule |
| [Policy and law watch](packs/policy-and-law-watch/README.md) | Watching official public sources for new laws and rules on a topic |
| [Public budget report](packs/public-budget-report/README.md) | Reporting on a public state or city budget |
| [Donor thank-you letters kit](packs/kit-donor-thank-you-letters/README.md) | A small nonprofit's agent kit that drafts donor thank-you letters from a coded gift list with the finance lead's acknowledgment wording and checks donors' privacy choices first, while staff decide special handling and sign every letter |
| [Flyer translation check kit](packs/kit-flyer-translation-check/README.md) | A community center's agent kit that checks translated service flyers against the English source for dropped facts, changed numbers, dates and phone numbers, untranslated text and reading level, while a fluent community reviewer approves each language and staff decide what gets printed |
| [Food bank inventory and pickup kit](packs/kit-food-bank-pickups/README.md) | A food bank's agent kit |
| [Direction to work](packs/direction-to-work/README.md) | Turning a stakeholder's message into direction nouns, finding nouns and atomic verbs, with superseded directions kept on the record |
| [Status and handoff](packs/status-and-handoff/README.md) | Answering what is done, what is next and where to resume, with evidence |
| [Release and verify](packs/release-and-verify/README.md) | Releasing a change and proving what is live, from the exact tested head to a receipt with a rollback target |
| [Rename and relink](packs/rename-and-relink/README.md) | Renaming products, repositories and pages and rewriting every reference and link, with no redirect relied on |
| [Voice narration](packs/voice-narration/README.md) | Narration with a text-to-speech voice: a pronunciation lexicon, seeded and measured takes chosen by a fixed rule, lines placed on their beats, a person's listening check and an AI-voice label |
| [Narrated explainer video](packs/narrated-explainer-video/README.md) | Making a narrated explainer video with code, every step a verb with a receipt: a frame clock, an HTML stage, captions timed to the voice, two variants and a hashed release manifest |
| [Continuous tuning](packs/continuous-tuning/README.md) | Tuning a small open model round after round, kept only when a rule fixed before scoring says so |
| [Public company research](packs/public-company-research/README.md) | Researching public companies from official sources, with every number cited and never as financial advice |
| [Deep research report](packs/deep-research-report/README.md) | Answering a research question with a cited report that states its limits, not for choosing what to build |
| [Options chain review](packs/options-chain-review/README.md) | Reviewing an options chain descriptively from a licensed source the requester already has: greeks, implied volatility and its rank, liquidity screens and roll candidates, every number with its data timestamp and never as financial advice |
| [Checked data analysis](packs/checked-data-analysis/README.md) | Analyzing a CSV file with a check at every step: profile, validation, flags that never drop rows, recorded queries, charts as data and findings traced to queries, while a person decides what they mean |
| [Screenshot design review](packs/screenshot-design-review/README.md) | Reviewing a user interface screenshot against design rules: described first, captured at named widths and themes, measured, recorded as located findings and verified after a re-render |
| [Atomic step contract](packs/atomic-step-contract/README.md) | Giving each atomic step exactly what it needs: a pinned procedure, a closed slice of state, the last observation and a grant that denies on the wire |
| [Unattended run record](packs/unattended-run-record/README.md) | Running work overnight or on a schedule and leaving a record anyone can check, graded by the check and with every failure kept |
| [Retrieval triggers and reuse](packs/retrieval-triggers-and-reuse/README.md) | Looking up existing nouns before generating new ones, and reusing past solutions only under the check |
| [File triage at scale](packs/file-triage-at-scale/README.md) | Organizing very large collections of files without losing any, with every move approved by a person and verified by hash |
| [Measured claims](packs/measured-claims/README.md) | Technical notes whose every claim says how it is known, with conclusions resting on evidence and corrections kept on the record |
| [User acceptance testing](packs/user-acceptance-testing/README.md) | User acceptance testing with synthetic personas, criteria a person agrees to before testing, scenario scripts, results recorded as observed, defects proposed as findings and a person's go or no-go |
| [Accessibility audit](packs/accessibility-audit/README.md) | Auditing a page or app against WCAG 2.2 level AA, every finding citing its success criterion, with tested contrast and landmark code |
| [Usability heuristics review](packs/usability-heuristics-review/README.md) | Reviewing a page or app against ten usability heuristics, with independent evaluators, severities, screenshot regions and a fix verb per finding |
| [Launch readiness](packs/launch-readiness/README.md) | Deciding whether a site or app is ready to launch: links, status claims, analytics, error pages, rollback and the owner's go, with the release left to a person |
| [Exploratory testing charters](packs/exploratory-testing-charters/README.md) | Exploratory testing in time-boxed sessions: charters, notes taken as it happens, bugs as findings, debriefs and coverage notes |
| [Video QA checks](packs/video-qa/README.md) | Checking an encoded video beyond the eight post-encode checks: blank and frozen frames, cut cadence, loudness range and true peak, clipping and silence, caption lint and timing against speech, the delivery spec read from the file's own boxes and a legibility proxy, with tested code |
| [Video editing](packs/video-editing/README.md) | Editing a video from its script: an edit decision list paced to the words, J and L cuts, b-roll, transitions, colour, the mix, reframes and an export spec, with every revision kept and a person locking the cut |
| [Video review](packs/video-review/README.md) | Reviewing a video with a fixed rubric, by a person or a worker that did not make it: timestamped findings with a severity, evidence and a fix verb, every number traced, and a re-review after fixes |
| [Social cut-downs](packs/social-cutdowns/README.md) | Deriving platform cut-downs from a longer video that keep its meaning: hooks, reframes, burned-in captions, length targets and copy, approved and posted by a person through the platform's own tools |
| [Thumbnails and titles](packs/thumbnail-and-title/README.md) | Drafting thumbnail and title candidates from what a video shows, checking them at small sizes and for honesty, and planning an A/B test, with a person picking |
| [Video audience acceptance](packs/video-uat/README.md) | Testing whether a video's intended viewers understand it, with tasks and pass criteria a person agrees to before any session and results that describe only the people asked |
| [Living research dossier](packs/living-research-dossier/README.md) | Keeping a research dossier current: a numbered queue of questions worked in cycles with one sub-agent per question, every fact with an as-of date and a decay class, named triggers once the questions run out, decayed facts refreshed and a person deciding what is published |
| [Wiring and conformance checks](packs/wiring-and-conformance-checks/README.md) | Proving a code project's capabilities are wired in: modules no live path imports, config fields that survive a reload, health probes that probe, a canary per rule and documented behaviors tested on their real path, with tested code |
| [Persona panel and second opinion](packs/persona-panel-second-opinion/README.md) | Independent second opinions before a decision: reviewers with stated perspectives on other model families, takes given alone, a synthesis that leads with where they disagree and a person who decides |
| [Continuous self-review](packs/continuous-self-review/README.md) | Reviewing a repository, site or video on a rotation: scopes with their checks, a schedule a person approves, the next scopes picked by a fixed rule, each run diffed against the last into new, still open, fixed, unverified, unexplained, unchecked and reopened findings, fixes verified by a different worker and a review log that shows coverage over time |
| [Annoyance hunt](packs/annoyance-hunt/README.md) | Hunting friction and papercuts from the user's point of view: friction tours for websites, command lines, videos and docs, complaints in people's own words, and each annoyance counted for how often it happens and how much it hurts, ranked by frequency times pain and confirmed by a person |
| [Edge and corner cases](packs/edge-and-corner-cases/README.md) | Finding edge and corner cases on purpose: input, interface, video and API catalogs, every expected result written before anything runs, a tested seeded generator of labelled cases, inputs stored escaped and every failure kept as its own regression test |
| [Regression watch](packs/regression-watch/README.md) | Watching for regressions against baselines a person accepted: screenshots by hash, metrics with tolerances, API shapes and video QA numbers measured again on every change, every mismatch rerun twice so flaky checks are told apart from real regressions |
| [Codebase health review](packs/codebase-health-review/README.md) | Reviewing a codebase's health at one commit: TODO ages from git blame, swallowed exceptions, untested error paths, flaky tests, dependency drift, unpinned versions, oversized modules, duplicated code, docs drift and secrets reported by place only, with tested code and no single score |
| [Frame-by-frame video QA](packs/frame-by-frame-video-qa/README.md) | Frame-by-frame video quality checks with 12 deterministic detectors, connected-component UI masks and optional local SAM occlusion checks, with tested code |
| [Audio and narration QA](packs/audio-and-narration-qa/README.md) | ITU-R BS.1770-4 loudness and true-peak gating, sidechain pause-pumping and edit-point click checks, speaking WPM pacing, WebVTT caption-pause alignment and ASR CER gating, with tested code |
| [Parametric 3D video composer](packs/parametric-3d-video-composer/README.md) | Planning 1x3 and 2x2 3D perspective hub camera trajectories, verifying browser chrome safe areas and lower caption bands, and blocking text-on-text double-exposure crossfades, with tested code |
| [Agent harness feeds](packs/agent-harness-feeds/README.md) | Continuously probing, normalizing and encapsulating an Agent Harnesses Feed across Harness Square, OpenCode, Pi and Muse Code with HarnessTax and Pareto rankings, with tested code |
| [Hackathon ecosystem index](packs/hackathon-ecosystem-index/README.md) | Decomposing public AI repository metadata and READMEs into searchable task and task-object signatures and serving hybrid BM25 plus facet Reciprocal Rank Fusion retrieval, with tested code |
| [LoRA memory and shimming](packs/lora-memory-and-shimming/README.md) | Compiling post-cutoff task objects into leakage-checked LoRA pairs, routing between revocable prompt shims and weight updates, and gating promotion on paired bootstrap CIs, with tested code |
| [Hybrid retrieval context knapsack](packs/hybrid-retrieval-context-knapsack/README.md) | Fusing BM25 and dense cosine rankings via RRF (k=60), stripping untrusted prompt injections, pruning MinHash near-duplicates and solving a 0/1 token-budget context knapsack, with tested code |
| [Leakage-safe regime backtesting](packs/leakage-safe-regime-backtesting/README.md) | Synthetic and historical statistical validation hygiene with purged walk-forward splits, causal volatility-regime Rank IC/ICIR, turnover drag and multiple-testing deflation, never as financial advice, with tested code |

Every noun is a Tessera `RecordWrite` body and every verb a `TaskSpec` template. Workers
create nouns and propose follow-up verbs; they never enqueue their proposals. All 1470
nouns and 473 verb templates were checked offline with Tessera's own models at a pinned
commit, and a two-key probe on a throwaway local Store showed a team surface can read,
claim and update them while other keys see nothing; the [receipt](packs/VALIDATION.json)
records exactly what was checked. The [pack inventory](docs/pack-inventory.md) maps the
packs onto making a video, building nonprofit kits and keeping knowledge fresh, and lists
what is still missing. Reading or importing a pack runs and grants nothing.

## Start here

To add a pack, follow [Submit a seed pack](docs/submit-a-pack.md): generate it, validate it
locally with `make check` and `make check-tessera`, and open a pull request.

Start with [CONTRIBUTING.md](CONTRIBUTING.md), then follow the
[worker lifecycle](docs/lifecycle.md). [Formats](docs/formats.md) separates actual
HTTP/MCP payloads from the proposed manifest. [Status](docs/status.md) states what
these examples prove and what still needs an owning implementation.

The [self-improvement guide](docs/self-improvement.md) describes a bounded,
worker-led improvement loop and a reference-only meta-pack. It is a contribution
template, not an enabled autonomous process.
The [meta-pack blueprints](docs/meta-pack-blueprints.md) outline ten possible
improvement workflows, with a small first pilot and explicit rejection conditions.
The [context, combined outcomes and result guide](docs/context-composition-and-results.md)
explains bounded worker inputs, integration checks and concise receipt-backed updates.
The [capability research workflow](docs/capability-research.md) applies those ideas
to overloaded feeds and newsletters: consolidate claims, assess fit against a
versioned project profile, and run only justified comparisons before recommending
an adoption decision. It is a proposed seed-pack use case, not an active collector.
The [seed operations guide](docs/seed-operations.md) separates the existing seed
expander, the bounded research task authoring tool, reference meta-packs and the
remaining mailbox/scheduling work.

The [Opportunity Lab guide](docs/opportunity-lab.md) links the runnable Tessera
showcase: shared briefs, independent solutions, candidate nouns and later
comparison or remix verbs.

## Connect and inspect

Start at the [ecosystem connection page](https://home.ta-amps.workers.dev/connect)
or [Tessera connection page](https://tessera.ta-amps.workers.dev/connect).
An HTTP/MCP-capable harness can use:

| Purpose | Endpoint |
| --- | --- |
| Public MCP discovery | `https://tessera.ta-amps.workers.dev/mcp` |
| Access modes and limits | `https://tessera.ta-amps.workers.dev/connect.json` |
| API descriptions | `https://tessera.ta-amps.workers.dev/v1/openapi.json` |
| Public agent card | `https://tessera.ta-amps.workers.dev/.well-known/agent-card.json` |

Send the [initialize request](examples/mcp/initialize.json), then
[tools/list](examples/mcp/tools-list.json). Compare the returned descriptors with
the operations you need. A protocol version string alone does not establish every
optional MCP feature. An assistant without external HTTP/MCP tool access needs a
compatible connector; a longer prompt cannot grant that capability.

```bash
export TESSERA_URL=https://tessera.ta-amps.workers.dev
curl --fail-with-body "$TESSERA_URL/connect.json"
curl --fail-with-body -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data-binary @examples/mcp/tools-list.json "$TESSERA_URL/mcp"
```

Anonymous practice starts with `POST /v1/session/anonymous` and the
[session body](examples/http/session.json). The returned session token belongs in
`Authorization: Bearer <session_token>`. Keep it in your harness's credential
memory or approved secret store, never in a pack or conversation log. No existing
key is needed. Discover the current quotas and expiry from the response.

Anonymous work is isolated synthetic practice. It cannot publish a reusable pack,
claim production verbs or access another session's history. Durable contribution
work needs an operator-issued key scoped to the assigned namespace, queue and
effects. Key issuance remains operator-assisted. A personal label is not an
account role or authorization grant.

## First useful contribution

1. Agree on one outcome and existing queue with its owner. Find permitted prior
   nouns or execution observations before creating duplicate work.
2. Claim a bounded verb, inspect required capabilities and pin the input versions.
   Use a configured shim if helpful; ordinary HTTP/MCP also works without one.
3. Produce a private candidate, run the required checks and record failures as
   well as successes. Use the [synthetic noun body](examples/http/noun-put.json)
   and [verb seed body](examples/http/verb-enqueue.json) as shape examples.
4. Submit exact artifact references with a stable idempotency key. Optional
   execution telemetry is worker reported, not independent proof.
5. Request a review verb when the owning policy requires it. Admission and public
   publication remain separate authorized actions.

The [candidate manifest](examples/pack-manifest.proposed.json) is a proposal for
reviewing related files. **There is no manifest upload endpoint or generic pack
importer here.** A category name does not register executable code or activate a
shim. Do not upload an entire directory and assume that it becomes a workflow.

## Check a contribution locally

Python 3.10+ and Git are enough; no package install, network or service is needed.
Pack code has its own checks in `packs/<pack>/code/`, which a separate CI job runs.

```bash
make check
```

The checks parse JSON, enforce the documented example subset, validate local
manifest hashes and links, rebuild every seed pack byte for byte, validate the packs
against a snapshot of Tessera's contract, recompute the packs' worked examples, and
scan for secrets, private names and forbidden typography. They include negative
fixtures. They do not execute artifacts, certify a live deployment, prove licensing or
validate arbitrary JSON Schema.

With a local Tessera checkout, `make check-tessera TESSERA_SRC=<path>` also runs every
pack noun and verb through Tessera's own models; see the [library guide](packs/README.md).

The examples and packs are MIT-licensed authoring material. They are not production
packs or a second artifact library: accepted artifacts and evidence belong in Tessera.
Installing or activating packs waits for the owning infrastructure and contributor flow.
