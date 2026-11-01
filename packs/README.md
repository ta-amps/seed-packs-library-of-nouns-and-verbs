# Seed pack library

A seed pack is a collection of **nouns** (reusable knowledge, templates, tool cards and
examples) and **verbs** (work an authorized worker can claim). That is all a pack
contains. A pack may include tested code as nouns, in `packs/<pack>/code/`. The library never runs pack code except in its own CI tests; workers run it under their own permissions. Reading, exporting or importing a pack still runs nothing, activates nothing, publishes nothing and grants nothing. Packs are separate from surfaces: a website, app or chat client can show what a
pack produces, but no pack is part of a surface, and packs carry plain-English names, not
product names. A pack adds no new kind of entity, runtime, agent authority or scheduler.
Reading, exporting or importing a pack runs nothing, activates nothing, admits or
publishes nothing, copies no credential and grants no permission. Tessera stays the
authority for identity, storage, leases and receipts.

**Status, October 29, 2026:** every pack here is a proposal and a validated example.
None is installed, imported, admitted or activated, and no worker has run these verbs.

## The packs

| Pack | A collection of nouns and verbs for | Nouns | Verbs |
| --- | --- | --- | --- |
| [Repository review](repo-review/README.md) | Reviewing a code repository with 50 evidence-requiring questions | 66 | 6 |
| [Video and motion with code](video-motion/README.md) | Video and motion made with code: seeking frames, fitting motion, compiling, rendering and checking | 28 | 8 |
| [Video showcase](video-showcase/README.md) | Making a truthful demo video, from script to review and release | 15 | 8 |
| [Visual and 3D rendering](visual-rendering/README.md) | Rendering images, motion graphics and 3D scenes and checking them | 11 | 5 |
| [Tool discovery](tool-discovery/README.md) | Discovering, trialing, deciding on and refreshing new tools | 23 | 7 |
| [Prior art and alternatives](prior-art-and-alternatives/README.md) | Finding what already exists and what the alternatives are, before anything new is built | 21 | 7 |
| [Benchmark scores](benchmark-scores/README.md) | Keeping benchmark scores current and comparable | 10 | 5 |
| [Freshness checks](freshness-checks/README.md) | Finding stale, deprecated or end-of-life knowledge | 7 | 4 |
| [Evaluation design](evaluation-design/README.md) | Fair, pre-registered evaluations with exact-match scoring | 10 | 7 |
| [Checks of checks](checks-of-checks/README.md) | Proving a test or rubric works before trusting it | 8 | 4 |
| [Decomposition patterns](decomposition-patterns/README.md) | Breaking work into verbs with reusable patterns | 24 | 4 |
| [Code composition](code-composition/README.md) | Composing verified code without rewriting it | 35 | 7 |
| [Taste palettes](taste-palettes/README.md) | Comparing options side by side and keeping a person's choice | 8 | 5 |
| [Public-good kits](public-good-kits/README.md) | Building agent kits that nonprofits can use | 15 | 8 |
| [Exploitation evidence](exploitation-evidence/README.md) | Spotting exploitation and scams in synthetic cases, never accusing anyone | 70 | 11 |
| [Harness onboarding](harness-onboarding-e2e/README.md) | Connecting an agent harness and proving its lifecycle | 9 | 5 |
| [Security review](security-review/README.md) | Authorized, local-only security review of code | 11 | 6 |
| [Cost optimization](cost-optimization/README.md) | Finding and measuring cost savings | 8 | 6 |
| [Docs improvement](docs-improvement/README.md) | Making documentation clearer for a named reader | 8 | 5 |
| [Findings to fixes](findings-to-fixes/README.md) | Turning every noticed error, issue, design flaw or annoyance into recorded, fixed and verified work | 24 | 10 |
| [Monthly program impact report kit](kit-monthly-impact-report/README.md) | A community nonprofit's monthly program impact report | 13 | 5 |
| [Handwritten statements to text kit](kit-handwritten-statements/README.md) | Turning handwritten statements and forms dropped into a folder into text typed exactly as written, keeping the writer's slang, spelling, acronyms and words, flagging every uncertain reading for a person, and listing acronyms against a local glossary, while staff check every flag, follow up on safety, sign off and decide any use | 16 | 6 |
| [Funding impact summary kit](kit-funding-impact-summary/README.md) | A funding impact summary in a grant renewal | 13 | 5 |
| [Policy research brief kit](kit-policy-research-brief/README.md) | A small nonprofit's policy research brief | 14 | 5 |
| [Victim support referral kit](kit-victim-support-referrals/README.md) | A victim services program's referral kit | 13 | 5 |
| [Volunteer shift schedule kit](kit-volunteer-shift-schedule/README.md) | A disaster relief hub's volunteer shift schedule | 14 | 5 |
| [Policy and law watch](policy-and-law-watch/README.md) | Watching official public sources for new laws and rules on a topic | 15 | 5 |
| [Public budget report](public-budget-report/README.md) | Reporting on a public state or city budget | 7 | 5 |
| [Donor thank-you letters kit](kit-donor-thank-you-letters/README.md) | A small nonprofit's agent kit that drafts donor thank-you letters from a coded gift list with the finance lead's acknowledgment wording and checks donors' privacy choices first, while staff decide special handling and sign every letter | 14 | 5 |
| [Flyer translation check kit](kit-flyer-translation-check/README.md) | A community center's agent kit that checks translated service flyers against the English source for dropped facts, changed numbers, dates and phone numbers, untranslated text and reading level, while a fluent community reviewer approves each language and staff decide what gets printed | 13 | 4 |
| [Food bank inventory and pickup kit](kit-food-bank-pickups/README.md) | A food bank's agent kit | 13 | 4 |
| [Direction to work](direction-to-work/README.md) | Turning a stakeholder's message into direction nouns, finding nouns and atomic verbs, with superseded directions kept on the record | 17 | 7 |
| [Status and handoff](status-and-handoff/README.md) | Answering what is done, what is next and where to resume, with evidence | 15 | 6 |
| [Release and verify](release-and-verify/README.md) | Releasing a change and proving what is live, from the exact tested head to a receipt with a rollback target | 16 | 7 |
| [Rename and relink](rename-and-relink/README.md) | Renaming products, repositories and pages and rewriting every reference and link, with no redirect relied on | 17 | 7 |
| [Voice narration](voice-narration/README.md) | Narration with a text-to-speech voice: a pronunciation lexicon, seeded and measured takes chosen by a fixed rule, lines placed on their beats, a person's listening check and an AI-voice label | 28 | 6 |
| [Narrated explainer video](narrated-explainer-video/README.md) | Making a narrated explainer video with code, every step a verb with a receipt: a frame clock, an HTML stage, captions timed to the voice, two variants and a hashed release manifest | 26 | 9 |
| [Continuous tuning](continuous-tuning/README.md) | Tuning a small open model round after round, kept only when a rule fixed before scoring says so | 33 | 9 |
| [Public company research](public-company-research/README.md) | Researching public companies from official sources, with every number cited and never as financial advice | 27 | 8 |
| [Deep research report](deep-research-report/README.md) | Answering a research question with a cited report that states its limits, not for choosing what to build | 29 | 9 |
| [Options chain review](options-chain-review/README.md) | Reviewing an options chain descriptively from a licensed source the requester already has: greeks, implied volatility and its rank, liquidity screens and roll candidates, every number with its data timestamp and never as financial advice | 27 | 7 |
| [Checked data analysis](checked-data-analysis/README.md) | Analyzing a CSV file with a check at every step: profile, validation, flags that never drop rows, recorded queries, charts as data and findings traced to queries, while a person decides what they mean | 32 | 8 |
| [Screenshot design review](screenshot-design-review/README.md) | Reviewing a user interface screenshot against design rules: described first, captured at named widths and themes, measured, recorded as located findings and verified after a re-render | 28 | 6 |
| [Atomic step contract](atomic-step-contract/README.md) | Giving each atomic step exactly what it needs: a pinned procedure, a closed slice of state, the last observation and a grant that denies on the wire | 17 | 7 |
| [Unattended run record](unattended-run-record/README.md) | Running work overnight or on a schedule and leaving a record anyone can check, graded by the check and with every failure kept | 17 | 7 |
| [Retrieval triggers and reuse](retrieval-triggers-and-reuse/README.md) | Looking up existing nouns before generating new ones, and reusing past solutions only under the check | 18 | 7 |
| [File triage at scale](file-triage-at-scale/README.md) | Organizing very large collections of files without losing any, with every move approved by a person and verified by hash | 18 | 9 |
| [Measured claims](measured-claims/README.md) | Technical notes whose every claim says how it is known, with conclusions resting on evidence and corrections kept on the record | 12 | 4 |
| [User acceptance testing](user-acceptance-testing/README.md) | User acceptance testing with synthetic personas, criteria a person agrees to before testing, scenario scripts, results recorded as observed, defects proposed as findings and a person's go or no-go | 21 | 7 |
| [Accessibility audit](accessibility-audit/README.md) | Auditing a page or app against WCAG 2.2 level AA, every finding citing its success criterion, with tested contrast and landmark code | 23 | 13 |
| [Usability heuristics review](usability-heuristics-review/README.md) | Reviewing a page or app against ten usability heuristics, with independent evaluators, severities, screenshot regions and a fix verb per finding | 25 | 5 |
| [Launch readiness](launch-readiness/README.md) | Deciding whether a site or app is ready to launch: links, status claims, analytics, error pages, rollback and the owner's go, with the release left to a person | 18 | 8 |
| [Exploratory testing charters](exploratory-testing-charters/README.md) | Exploratory testing in time-boxed sessions: charters, notes taken as it happens, bugs as findings, debriefs and coverage notes | 15 | 4 |
| [Video QA checks](video-qa/README.md) | Checking an encoded video beyond the eight post-encode checks: blank and frozen frames, cut cadence, loudness range and true peak, clipping and silence, caption lint and timing against speech, the delivery spec read from the file's own boxes and a legibility proxy, with tested code | 20 | 7 |
| [Video editing](video-editing/README.md) | Editing a video from its script: an edit decision list paced to the words, J and L cuts, b-roll, transitions, colour, the mix, reframes and an export spec, with every revision kept and a person locking the cut | 31 | 9 |
| [Video review](video-review/README.md) | Reviewing a video with a fixed rubric, by a person or a worker that did not make it: timestamped findings with a severity, evidence and a fix verb, every number traced, and a re-review after fixes | 26 | 7 |
| [Social cut-downs](social-cutdowns/README.md) | Deriving platform cut-downs from a longer video that keep its meaning: hooks, reframes, burned-in captions, length targets and copy, approved and posted by a person through the platform's own tools | 25 | 5 |
| [Thumbnails and titles](thumbnail-and-title/README.md) | Drafting thumbnail and title candidates from what a video shows, checking them at small sizes and for honesty, and planning an A/B test, with a person picking | 24 | 6 |
| [Video audience acceptance](video-uat/README.md) | Testing whether a video's intended viewers understand it, with tasks and pass criteria a person agrees to before any session and results that describe only the people asked | 16 | 5 |
| [Living research dossier](living-research-dossier/README.md) | Keeping a research dossier current: a numbered queue of questions worked in cycles with one sub-agent per question, every fact with an as-of date and a decay class, named triggers once the questions run out, decayed facts refreshed and a person deciding what is published | 24 | 10 |
| [Wiring and conformance checks](wiring-and-conformance-checks/README.md) | Proving a code project's capabilities are wired in: modules no live path imports, config fields that survive a reload, health probes that probe, a canary per rule and documented behaviors tested on their real path, with tested code | 25 | 8 |
| [Persona panel and second opinion](persona-panel-second-opinion/README.md) | Independent second opinions before a decision: reviewers with stated perspectives on other model families, takes given alone, a synthesis that leads with where they disagree and a person who decides | 32 | 6 |
| [Continuous self-review](continuous-self-review/README.md) | Reviewing a repository, site or video on a rotation: scopes with their checks, a schedule a person approves, the next scopes picked by a fixed rule, each run diffed against the last into new, still open, fixed, unverified, unexplained, unchecked and reopened findings, fixes verified by a different worker and a review log that shows coverage over time | 26 | 7 |
| [Annoyance hunt](annoyance-hunt/README.md) | Hunting friction and papercuts from the user's point of view: friction tours for websites, command lines, videos and docs, complaints in people's own words, and each annoyance counted for how often it happens and how much it hurts, ranked by frequency times pain and confirmed by a person | 25 | 6 |
| [Edge and corner cases](edge-and-corner-cases/README.md) | Finding edge and corner cases on purpose: input, interface, video and API catalogs, every expected result written before anything runs, a tested seeded generator of labelled cases, inputs stored escaped and every failure kept as its own regression test | 27 | 7 |
| [Regression watch](regression-watch/README.md) | Watching for regressions against baselines a person accepted: screenshots by hash, metrics with tolerances, API shapes and video QA numbers measured again on every change, every mismatch rerun twice so flaky checks are told apart from real regressions | 22 | 7 |
| [Codebase health review](codebase-health-review/README.md) | Reviewing a codebase's health at one commit: TODO ages from git blame, swallowed exceptions, untested error paths, flaky tests, dependency drift, unpinned versions, oversized modules, duplicated code, docs drift and secrets reported by place only, with tested code and no single score | 22 | 8 |
| [Frame-by-frame video QA](frame-by-frame-video-qa/README.md) | Frame-by-frame video quality checks with 12 deterministic detectors, connected-component UI masks and optional local SAM occlusion checks, with tested code | 14 | 7 |
| [Audio and narration QA](audio-and-narration-qa/README.md) | ITU-R BS.1770-4 loudness and true-peak gating, sidechain pause-pumping and edit-point click checks, speaking WPM pacing, WebVTT caption-pause alignment and ASR CER gating, with tested code | 10 | 5 |
| [Parametric 3D video composer](parametric-3d-video-composer/README.md) | Planning 1x3 and 2x2 3D perspective hub camera trajectories, verifying browser chrome safe areas and lower caption bands, and blocking text-on-text double-exposure crossfades, with tested code | 11 | 4 |
| [Agent harness feeds](agent-harness-feeds/README.md) | Continuously probing, normalizing and encapsulating an Agent Harnesses Feed across Harness Square, OpenCode, Pi and Muse Code with HarnessTax and Pareto rankings, with tested code | 16 | 5 |
| [Hackathon ecosystem index](hackathon-ecosystem-index/README.md) | Decomposing public AI repository metadata and READMEs into searchable task and task-object signatures and serving hybrid BM25 plus facet Reciprocal Rank Fusion retrieval, with tested code | 9 | 3 |
| [LoRA memory and shimming](lora-memory-and-shimming/README.md) | Compiling post-cutoff task objects into leakage-checked LoRA pairs, routing between revocable prompt shims and weight updates, and gating promotion on paired bootstrap CIs, with tested code | 10 | 3 |
| [Hybrid retrieval context knapsack](hybrid-retrieval-context-knapsack/README.md) | Fusing BM25 and dense cosine rankings via RRF (k=60), stripping untrusted prompt injections, pruning MinHash near-duplicates and solving a 0/1 token-budget context knapsack, with tested code | 10 | 3 |
| [Leakage-safe regime backtesting](leakage-safe-regime-backtesting/README.md) | Synthetic and historical statistical validation hygiene with purged walk-forward splits, causal volatility-regime Rank IC/ICIR, turnover drag and multiple-testing deflation, never as financial advice, with tested code | 10 | 3 |
| [Scene and cognitive video QA](scene-and-cognitive-video-qa/README.md) | Multi-frame shot dwell and text-crossfade transition checks, static-slide Ken Burns zoom stability, reading-speed and split-attention prose conflict checks, desktop web-journey provenance and widescreen frosted-caption geometry, with tested code | 10 | 5 |
| [Meta ARE scenario matrix](meta-are-scenario-matrix/README.md) | Generating 1,000 dynamic environments, 1,000 decomposition methods, 1,000 operator personas and 1,000 multi-position stakeholders, evaluating 4D Latin-hypercube or 10^12 tuples and digesting safe trajectories into candidate tasks (things to do) and task objects, with tested code | 10 | 3 |
| [SIRA self-learning RAG](sira-self-learning-rag/README.md) | Offline corpus-discriminative Seed Pack enrichment (SIRA), cross-domain structural isomorphism indexing (RA-RFT), execution-report reflection into sub-2ms edge shim rules (MR-Search) and bounded DGM-H proposals gated by an independent verifier, with tested code | 10 | 3 |
| [Partner compute cascade](partner-compute-cascade/README.md) | Routing public-good tasks across a sub-2ms edge shim, Fireworks AI multi-LoRA specialist adapters, Baseten <= 2,000,000 TPM fenced swarms, Modal isolated sandboxes and QLoRA fine-tuning, and Meta Muse / Llama models with honest local_verified vs live_api receipts, with tested code | 10 | 3 |
| [Combinatorial niche spider](combinatorial-niche-spider/README.md) | Minting combinatorial multi-domain search cells, advancing non-repeating page cursors, expanding a persistent BFS spider frontier, refreshing star-surge movers and HTTP 404 rot, and scoring candidates on 8 separate 0-100 axes with query-family yield benchmarks, with tested code | 10 | 3 |
| [Agent capability and tier firewall](agent-capability-and-tier-firewall/README.md) | Enforcing scoped effect ceilings, credential and high-entropy secret redaction, and model data-tier routing guards that block non-public payloads from training or contributor endpoints before dispatch, with tested code | 14 | 4 |
| [Agent config supply chain scanner](agent-config-supply-chain-scanner/README.md) | Scanning repository agent definitions, rule files, MCP configs, and self-editing memory files for hidden Trojan Unicode, unapproved hook or server escalation, built-in name shadowing, and authority spoofing, with tested standard-library Python code, with tested code | 14 | 3 |
| [Brainstorm chunking and situation miner](brainstorm-chunking-and-situation-miner/README.md) | Deduplicating noisy raw notes, chunking unstructured text into content-addressed records, and clustering real-world situations into candidate seed-pack categories, with tested standard-library Python code, with tested code | 14 | 4 |
| [Coding session trace distiller](coding-session-trace-distiller/README.md) | Mining sanitized multi-hour AI coding session JSONL transcripts into reusable failure tombstones, tool-error loops, verified fix recipes, and prompt-shim candidates, with tested standard-library Python code, with tested code | 16 | 5 |
| [Configuration grids and bounds](configuration-grids-and-bounds/README.md) | Declarative multi-dimensional configuration grids, runtime parameter clamping, verified cell lifecycles, contextual regime selection, saturated boundary auto-expansion and AST magic-literal gates, with tested code | 9 | 3 |
| [Declarative chart and diagram SVG](declarative-chart-and-diagram-svg/README.md) | Compiling structured data tables and component message traces into publication-grade accessible SVGs (confidence-interval forest plots, progression bars, and edge-packet diagrams) with deterministic WCAG contrast and label-collision checks, with tested code | 13 | 4 |
| [Execution hooks and verifiers](execution-hooks-and-verifiers/README.md) | Compiling four-stage portable execution hooks across coding harnesses, enforcing pre-tool safety and spend guards, running topological pre-submit verifier DAGs, auditing verifier mutation sensitivity and extracting dead-end negative tombstones, with tested code | 9 | 3 |
| [Film and surface rule evaluator](film-and-surface-rule-evaluator/README.md) | Evaluating declarative film and surface rule nouns, blocking forbidden synthetic or non-functional stamps, scoring frosted-pill caption centering and dual-channel cognitive load, repointing dead repository links to SHA-256-pinned source mirrors and verifying llms.txt parity against MCP tools, with tested code | 9 | 3 |
| [Grep, string and format rules](grep-string-and-format-rules/README.md) | Aho-Corasick literal scanning, portable grep rules, Unicode and entropy security checks and strict JSON and copy formatting, with tested code | 9 | 3 |
| [Loops schedules and heuristics](loops-schedules-and-heuristics/README.md) | Inert window-keyed schedule compilation, fragility half-life urgency ranking, AIMD claim pacing, UCB1 anti-stall bandit loops, seven-tier compute resource cascades and six advice-only swappable learners, with tested code | 9 | 3 |
| [Multimodal mask and transcript alignment](multimodal-mask-and-transcript-alignment/README.md) | Aligning image segmentation masks, speech-to-text word timings, and layout safe zones across multimodal media pipelines, with tested standard-library Python code, with tested code | 12 | 3 |
| [Portable agent persona compiler](portable-agent-persona-compiler/README.md) | Compiling portable agent role definitions across coding harnesses, scoring delegation descriptions, separating routing from permissions, and stripping accuracy-degrading persona fluff, with tested standard-library Python code, with tested code | 13 | 3 |
| [Probabilistic filters and sketches](probabilistic-filters-and-sketches/README.md) | Cache-line blocked Bloom filters, deletable Cuckoo filters, static Xor filters, multi-probe LSH and streaming sketches, with tested code | 9 | 3 |
| [Social video reframe and hooks](social-video-reframe-and-hooks/README.md) | Planning vertical 9:16 and square 1:1 video cutdowns from 16:9 demos with subject-safe crop trajectories, hook-beat scoring, caption-band reflow, and claim-preservation gates, backed by standard-library Python code, with tested code | 15 | 5 |
| [Submission rubric and readiness audit](submission-rubric-and-readiness-audit/README.md) | Auditing engineering repositories against weighted evaluation rubrics covering problem specificity, verified open-weight and multimodal model usage, modular source and CI depth, and live deployment plus video walkthrough completeness, with tested standard-library Python code, with tested code | 12 | 3 |
| [Trigger and shim rules](trigger-and-shim-rules/README.md) | Three-tier trigger compilation with Role-Filler Frame isomorphism, conversation-aware submodular context-shim knapsacks, step-slicing HarnessTax break-even routing and privacy-safe compatibility matching, with tested code | 9 | 3 |
| [Byte latent patch and entropy chunker](byte-latent-patch-and-entropy-chunker/README.md) | Segmenting byte streams into lossless variable-length patches at conditional Shannon entropy spikes and allocating downstream compute proportional to cumulative information surprise, with tested code | 9 | 3 |
| [Coconut latent and thought budget routing](coconut-latent-and-thought-budget-routing/README.md) | Routing reasoning tasks across four compute regimes, compressing verbose multi-turn traces into continuous latent state plus invariant checkpoints and halting repetitive overthinking cycles, with tested code | 9 | 3 |
| [DoRA, SpinQuant and adapter merging](dora-spinquant-and-adapter-merging/README.md) | Walsh-Hadamard outlier rotation quantization, weight-decomposed low-rank adapter analysis and subspace interference routing across static fusion and co-resident switching, with tested code | 9 | 3 |
| [FAISS IVF-PQ and ANN index cascade](faiss-ivf-pq-and-ann-index-cascade/README.md) | K-means++ Voronoi inverted-file partitioning, residual uint8 product quantization, asymmetric distance lookup tables and exact top-R reranking, with tested code | 9 | 3 |
| [JEPA world-state and action simulator](jepa-world-state-and-action-simulator/README.md) | Action-conditioned latent world-state prediction, representation-space epistemic energy anomaly gating and counterfactual multi-step rollout planning, with tested code | 9 | 3 |
| [Rule of Two and agent guardrails](rule-of-two-and-agent-guardrails/README.md) | Enforcing monotone Rule of Two capability lattices across multi-step tool DAGs, bidirectional typed privacy placeholder vaults and model license-tier routing firewalls, with tested code | 9 | 3 |
| [Seeded defect and proof-carrying review](seeded-defect-and-proof-carrying-review/README.md) | Mutation-guided reviewer calibration across six seeded defect classes, proof-carrying refusal and approval verification and exact Wilson score plus paired bootstrap confidence intervals, with tested code | 9 | 3 |
| [Self-rewarding and iterative DPO flywheel](self-rewarding-and-iterative-dpo-flywheel/README.md) | Iterative RPO preference curation, rubric-judge calibration gating against deterministic verifiers and pre-registered holdout flywheel promotion, with tested code | 9 | 3 |
| [Self-constructing node and waterfall](self-constructing-node-and-waterfall/README.md) | Stateless contract-hydrated worker nodes, continuous per-step state profiling, <6h keyword resource hydration, five-rung deterministic-to-CLI-harness waterfalls, multi-persona vector ratings and quorum capability-spinout proposals, with tested code | 9 | 3 |
| [Frosted widescreen captions](frosted-widescreen-captions/README.md) | Laying out, bridging, contrast-checking and rendering two-line frosted caption pills inside a 1920x1080 widescreen lower caption band, with tested code | 9 | 3 |
| [Partner compute telemetry cards](partner-compute-telemetry-cards/README.md) | Verifying partner compute receipts and formatting truthful local_verified vs live_api telemetry cards with honest speed-ratio attribution, with tested code | 7 | 2 |
| [Request status UI](request-status-ui/README.md) | Reducing append-only request lifecycle events into plain-language status timelines, replay schedules and identifier-free requester views, with tested code | 8 | 2 |
| [Website-first walkthrough capture](website-first-walkthrough-capture/README.md) | Auditing widescreen walkthrough storyboards against footage, anchor and pacing gates and emitting headless viewport capture plans, with tested code | 8 | 2 |

Together: 1819 nouns and 581 verb templates across one hundred and nine packs. The
[pack inventory](../docs/pack-inventory.md) maps them onto three goals (making a video,
building nonprofit kits and keeping knowledge fresh) and lists what is still missing.

## What is in each pack folder

| File | What it is |
| --- | --- |
| `README.md` | A short, plain explanation, starting with what the pack lets workers do |
| `source.json` | The authored content. Edit this file |
| `nouns.json` | Generated. One Tessera `RecordWrite` body per line: create-only, `surface_only`, quarantined |
| `verbs.json` | Generated. One Tessera `TaskSpec` template per line, with unfilled input slots |
| `manifest.json` | Generated. File digests, each noun's value SHA-256 and each verb's identity |
| `code/` | Optional. Tested code the pack's tool nouns point at, with its own tests. The manifest pins every file by digest; the library runs it only in CI |

## Workers create nouns and verbs

Every verb template says what its worker creates. The worker **writes nouns**: the ones
listed in the template's output contract, returned with their pins. The worker also
**proposes verbs**: follow-up work the results justify, such as a breakdown into smaller
verbs, a trial of a changed tool or a research follow-up, returned in the output's
`proposed_verbs` with the pins they need, and nouns worth creating later in
`proposed_nouns`. Workers never enqueue their proposals; an authorized requester enqueues
the ones worth doing. Examples: repository review's `select-questions` proposes one
`investigate-family` verb per family, `flag-stale` proposes refreshes and comparisons,
and decomposition's breakdowns become child task previews.

## How the pieces fit

- A **pin** is a Tessera `NounRef`: store, key, version and `value_sha256`, the SHA-256
  of the value's canonical JSON. Keys carry the pack version, so a new version never
  collides with an old one. Version 1 pins assume a create-only write succeeded; read the
  noun back and compare the digest before relying on it.
- A **verb template** lists pinned pack nouns, typed slots you fill with your own pins,
  typed input and output schemas, acceptance checks, a network mode and the outcomes it
  may end with. Every template can end with `no_change`, `unknown` or `blocked`, each
  with a required explanation. `scripts/build_packs.py --instantiate` fills a template,
  checks the result against its input schema and prints it, optionally for your queue
  with `--queue`; it never enqueues.
- Each template carries an optional **execution report** in Tessera's version-1 format.
  Its contract copies the typed schemas, so runs of the same template share one shape
  fingerprint. What went right, what went wrong, next steps and ideas go in the task
  output's `run_notes`, because the version-1 report has no fields for them.
- **Scope.** Payloads are `surface_only`. Import them with a key scoped to your team's
  surface; Tessera records that surface as the producer. Workers, requesters and
  reviewers on the same surface can then read the nouns, claim the verbs and read each
  other's outputs, while keys on other surfaces, or with none, see nothing. Workers write
  their outputs the same way.

## Choices worth knowing

- **Only registered categories.** Every noun and verb uses one of Tessera's 20 noun
  and 18 verb categories, with `category_reason` where the fit is not obvious. Tessera
  has no category for profiles or preferences, so those use `noun.seed_hypothesis`: they
  are assumptions later evidence can confirm or contradict.
- **No invented scores.** Tessera requires four quality dimensions on every category.
  Each starts at its lowest value with tier `unverified` and a `dimension_basis` saying
  nothing was measured. Success records keep `trials` and `successes` null, so Tessera's
  rankings list them as unranked instead of scoring them from a prior.
- **Typed relations only**, of the kinds each category allows.
- **No branding.** Surface and product names appear only in a descriptor's
  `provenance_notes`, which say where an idea came from, or in `source.json`'s
  `moved_from`, the one field that records the repository and commit a pack moved from.

## How the packs are checked

| Check | What it does | Where it runs |
| --- | --- | --- |
| `scripts/build_packs.py --check` | Rebuilds every pack and fails if any committed byte differs | `make check`, CI |
| `scripts/validate_packs.py` | Shapes, categories, relations, pins, outcomes, scope, network modes, authority limits, instructions to contact or publish, branding, template and example conformance, README rules, the counts stated in these docs and the forty-five worked examples, against [a snapshot](tessera-contract.json) of Tessera's contract | `make check`, CI |
| `scripts/validate_against_tessera.py` | Every noun and verb through Tessera's own `RecordWrite`, `TaskSpec`, tag projection, `validate_category_payload`, `NounRef` and execution-report code, ten negative probes, and a two-key lifecycle probe on a throwaway local Store | Locally, with a clean Tessera checkout |

The last check writes [VALIDATION.json](VALIDATION.json) with the Tessera commit, whether
its files were clean, and the digests it validated. `make check` fails if a pack changed
after that validation, so the receipt cannot silently go stale. None of these checks
calls a service or a model or writes to a real fabric.

## Changing a pack

1. Edit `packs/<pack>/source.json` or its README.
2. Run `python3 scripts/build_packs.py` to regenerate the payloads.
3. Run `make check-tessera TESSERA_SRC=<clean Tessera checkout> TESSERA_ARGS=--write`
   with that checkout's Python environment.
4. Run `make check` before committing.
