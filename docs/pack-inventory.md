# Pack inventory

Which seed packs we need to make real things with the whole system, which exist in
this library, which were added now, and what is still missing. Dated October 29, 2026.

A seed pack is a collection of nouns (reusable things) and verbs (claimable work). Every
pack below is a **proposal**: validated offline against Tessera's models, but not
installed, imported, admitted or run by any worker. "Exists" means it was in this
library before today's owner direction; "Added now" means this change built it;
"Needed" means nobody has built it yet.

Noun and verb kinds are Tessera's registered categories, without the `noun.` and `verb.`
prefixes. "Proposes" lists follow-up verbs a worker returns in `proposed_verbs`; an
authorized requester decides whether to enqueue them.

## 1. Making a video from start to finish

| Step | Pack and verb | Status | Noun kinds | Verb kinds | Proposes |
| --- | --- | --- | --- | --- | --- |
| Script and story | [Video showcase](../packs/video-showcase/README.md): draft-script | Exists | scene_recipe (script), eval_run (evidence links), seed_hypothesis (brief) | solve_draft | storyboard |
| Storyboard and shot list | Video showcase: storyboard | Exists | scene_recipe (storyboard, shot list, capture plan) | solve_draft | capture-screen per capture, draft-scene |
| Screen capture of real products | Video showcase: capture-screen | Exists | scene_recipe (media in the video and motion format), code_node (Playwright, Chromium cards from video and motion) | compile_dag | |
| Narration, a person's verb | Video showcase: record-narration | Exists | scene_recipe (media) | solve_draft (human) | transcribe-captions |
| Transcribed captions | Video showcase: transcribe-captions | Exists | scene_recipe (caption track) | ingest | |
| Motion graphics as code | [Visual and 3D rendering](../packs/visual-rendering/README.md): plan-scene, render; Video and motion: seek-frame, fit-motion, draft-scene | Added now | motion_profile (formulas, traces, profiles), scene_recipe (scene, asset) | solve_draft, compile_dag, ingest | prepare-assets, compile-social-formats |
| Audio layers, sound effects and music with license checks | Video showcase: prepare-audio, asset policy | Added now | skill_pack (asset policy), scene_recipe (audio cue sheet) | compile_dag | |
| Video layers and styles | Video showcase: style presets; [Video and motion](../packs/video-motion/README.md): plan-sequence | Added now | skill_pack (style presets, caption and audio rules), scene_recipe (sequence) | solve_draft | render-sequence |
| Render and encode | Video and motion: draft-scene, compile-social-formats, render-sequence; Visual and 3D rendering: render | Exists, extended; the video and motion tools are tested | eval_run (render manifest), code_node (video and motion tools, FFmpeg, Playwright, Chromium, Blender, three.js) | compile_dag | check-video |
| Every-frame and loudness QA | Video and motion: check-social-formats, check-video; Visual and 3D rendering: check-render; Video showcase: showcase checks in review-video | Exists, extended | benchmark_suite (thresholds, quality checks), eval_run (QA report) | verify_gate | fixes for failed checks |
| Independent review | Video showcase: review-video | Exists | eval_run (review notes) | verify_gate (person or different agent) | |
| Release, a person's verb | Video showcase: record-publication | Added now | eval_run (publication record) | verify_gate (human) | |
| One frame clock for picture, voice and captions | [Narrated explainer video](../packs/narrated-explainer-video/README.md): plan-cut | Added now | scene_recipe (cut plan), reflex_procedure (frame clock rules), code_node (explainer checks) | solve_draft | build-stage-scenes |
| Narration in a synthetic voice, labeled as AI | [Voice narration](../packs/voice-narration/README.md): prepare-lexicon, synthesize-lines, measure-lines, select-takes, place-on-beats, listen-and-approve (a person's verb) | Added now | skill_pack (lexicon), model_spec (voice model card), eval_run (synthesis log, measurements, take choice, listening record), scene_recipe (narration track) | generate_seed, compile_dag, verify_gate | listen-and-approve |
| Scenes as code on an HTML stage, rendered losslessly | Narrated explainer video: build-stage-scenes, render-slices | Added now | scene_recipe (stage), eval_run (slice recordings) | solve_draft, compile_dag | render-slices |
| Captions timed to the voice, as WebVTT, SRT and open captions | Narrated explainer video: time-captions, check-captions (a different worker) | Added now | scene_recipe (caption cues, caption track), eval_run (caption check) | compile_dag, verify_gate | compose-cut |
| Two variants, a frame sheet, every receipt and a hashed release manifest | Narrated explainer video: compose-cut, make-frame-sheet, compile-receipts, assemble-release-manifest | Added now | scene_recipe (sequences), eval_run (compose record, frame sheet, receipts ledger, release manifest) | compile_dag, verify_gate | review-video, record-publication |
| Tool and benchmark freshness for video and motion tools | [Tool discovery](../packs/tool-discovery/README.md), [Benchmark scores](../packs/benchmark-scores/README.md) | Exists, added now | code_node (candidates), eval_run (scores), benchmark_suite (trials) | probe_source, fetch_feed, recheck_fragility, benchmark_harness | run-trial, compare-on-profile |

**Still needed for video:** caption translation into other languages; an audio
description track for blind viewers; delivery presets per platform; and sourcing of
licensed music and stock clips. Narration noise-floor and clipping checks are now in the
voice narration pack.

## 2. Building agent kits for nonprofits

| Step | Pack and verb | Status | Noun kinds | Verb kinds | Proposes |
| --- | --- | --- | --- | --- | --- |
| The need or brief | [Public-good kits](../packs/public-good-kits/README.md): frame-need | Added now | seed_hypothesis (need brief) | problemize | draft-kit |
| Skill, MCP tool and prompt files | Public-good kits: draft-kit | Added now | skill_pack (manifest, skill file), mcp_server (read-only tool), prompt_shim (prompt file) | solve_draft | write-test-cases, self-check |
| Synthetic test cases | Public-good kits: write-test-cases | Added now | benchmark_suite (test cases) | generate_seed | |
| Self-check | Public-good kits: self-check | Added now | benchmark_suite (self-checks), eval_run (results) | verify_gate | independent-review |
| Independent review by a different worker | Public-good kits: independent-review | Added now | eval_run (review) | verify_gate | |
| Accessibility and translation | Public-good kits: check-accessibility, translate-kit | Added now | benchmark_suite (criteria), skill_pack (translation) | verify_gate, solve_draft | translate-kit per missing language, a fluent review |
| Steward release, a person's verb | Public-good kits: steward-release | Added now | eval_run (release record) | verify_gate (human) | |
| Checking the kit's own code and tools | [Security review](../packs/security-review/README.md), [Checks of checks](../packs/checks-of-checks/README.md) | Exists | seed_hypothesis (findings), benchmark_suite (checks) | verify_gate, solve_draft | |

**Still needed for kits:** feedback and incident intake from organizations using a kit;
a privacy check for kits that touch personal data; upgrade notes when a kit changes
under people already using it; and freshness checks for legal and referral sources,
which need human-sensitive handling and a person in every decision.

## 3. Keeping knowledge fresh

| Step | Pack and verb | Status | Noun kinds | Verb kinds | Proposes |
| --- | --- | --- | --- | --- | --- |
| New-tool discovery | Tool discovery: discover-sources, scan-source, propose-candidate | Exists | public_source, feed_source (sources), code_node (candidates) | probe_source, fetch_feed, generate_seed | run-trial |
| New-repository discovery | Tool discovery: discover-repos | Added now | code_node (candidates) | probe_source | propose-candidate |
| Refreshing tool cards and decisions | Tool discovery: refresh-candidates, daily schedule proposal | Added now | code_node, seed_hypothesis (decision, schedule) | recheck_fragility | run-trial, decide |
| Daily benchmark refresh | Benchmark scores: refresh-scores, flag-stale, daily schedule proposal | Added now | eval_run (scores), reflex_procedure (staleness policy) | recheck_fragility, verify_gate | refresh-scores, compare-on-profile |
| Deprecation and staleness checks | [Freshness checks](../packs/freshness-checks/README.md): scan-staleness, check-deprecations, propose-replacements, record-tombstone | Added now | seed_hypothesis (watch item), public_source (notice), negative_tombstone | recheck_fragility, probe_source, generate_seed, verify_gate | check-deprecations, run-trial, record-tombstone |
| Fair comparisons when something changes | [Evaluation design](../packs/evaluation-design/README.md) | Exists | benchmark_suite, eval_run, seed_hypothesis (pass marks) | problemize, ingest, benchmark_harness, verify_gate | run-arm twice per arm |

**Still needed for freshness:** scoring which sources are worth reading; newsletter
intake; and a person-led verb for resolving contradictions between sources.

## 4. Steering, status, releases and renames

Added October 30, 2026, for work that comes back in almost every project: turning a person's
direction into rules and verbs, answering status questions with evidence, releasing changes and
proving what is live, and renaming things without leaving old names or broken links behind.

| Step | Pack and verb | Status | Noun kinds | Verb kinds | Proposes |
| --- | --- | --- | --- | --- | --- |
| A message becomes typed parts | [Direction to work](../packs/direction-to-work/README.md): split-message | Added now | seed_hypothesis (intake) | situate | draft-directions, record-finding, plan-work, decide-or-ask |
| Directions with scope, source and supersession | Direction to work: draft-directions, find-conflicts, confirm-directions, a person's verb | Added now | seed_hypothesis (direction, conflict, confirmation), reflex_procedure (supersession, term rules, ask policy) | distill_reflex, recheck_fragility, reconcile_conflict (human) | find-conflicts, confirm-directions |
| Requests become atomic verbs; choices are decided or asked once | Direction to work: plan-work, decide-or-ask | Added now | seed_hypothesis (work plan, decision) | decompose_dag, solve_draft | propose-breakdown, record-finding |
| Later work follows the directions | Direction to work: sweep-compliance | Added now | eval_run (compliance report) | verify_gate | record-finding per violation |
| What is done, what is next and where to resume | [Status and handoff](../packs/status-and-handoff/README.md): take-snapshot, write-status, recheck-claims, rank-next-steps, write-handoff, resume-from-handoff | Added now | eval_run (snapshot, status, claim check, resume check), seed_hypothesis (next steps, handoff), recovery_playbook (resume) | probe_source, situate, verify_gate, decompose_dag, solve_draft, recover_fault | record-finding for contradicted claims |
| Releasing a change and proving what is live | [Release and verify](../packs/release-and-verify/README.md): plan-release, check-head, record-release (the release owner's verb), verify-parity, run-smoke, write-receipt, prepare-rollback | Added now | seed_hypothesis (plan, rollback brief), eval_run (head check, record, parity, smoke, receipt), benchmark_suite (smoke checklist) | decompose_dag, verify_gate, benchmark_harness, recover_fault | prepare-rollback, record-finding |
| Renames that reach every reference | [Rename and relink](../packs/rename-and-relink/README.md): build-inventory, plan-rewrites, rewrite-references, record-host-renames (the owner's verb), check-links, sweep-old-names, write-archive-notice | Added now | seed_hypothesis (map, plan), eval_run (inventory, link check, record, sweep), code_node (rewrite), public_source (notice) | probe_source, decompose_dag, solve_draft, verify_gate | record-finding for names that come back |

**Still needed here:** review of a screenshot sent with little or no text, turned into findings
with a capture matrix of widths and themes; mining past session prompts into categories and
reusable verbs under strict privacy rules; and finishing the most valuable work first when a
usage allowance is about to run out.

## 5. Research, company research and model tuning

Added October 30, 2026, for topics people asked for by name: research that ends in a cited report,
research on public companies that is never financial advice, and tuning a small model that keeps a
change only when a rule fixed in advance says so.

| Step | Pack and verb | Status | Noun kinds | Verb kinds | Proposes |
| --- | --- | --- | --- | --- | --- |
| A question framed, a search planned for and against the answer | [Deep research report](../packs/deep-research-report/README.md): frame-question, plan-search | Added now | seed_hypothesis (question, search plan), reflex_procedure (access, screening and strength rules) | problemize, expand_seed | collect-sources |
| Sources collected, screened and quoted exactly | Deep research report: collect-sources, screen-sources, extract-claims | Added now | public_source (source log), eval_run (screening log), seed_hypothesis (claims) | probe_source, verify_gate, ingest | synthesize |
| A labeled synthesis, an adversarial review and a report with limits | Deep research report: synthesize, adversarial-review (a different worker), write-report, decide-delivery (a person's verb) | Added now | seed_hypothesis (synthesis, report), eval_run (review), benchmark_suite (report checks) | solve_draft, verify_gate | counter searches the review missed |
| Filings fetched under the SEC's fair-access rules | [Public company research](../packs/public-company-research/README.md): fetch-filings | Added now | public_source (filing index), reflex_procedure (EDGAR access rules) | probe_source | extract-metrics |
| Metrics, comparisons, risk factors and a dated calendar | Public company research: extract-metrics, compare-periods-and-peers, summarize-risk-factors, build-catalyst-calendar | Added now | seed_hypothesis (metric table, comparison, risk factors, calendar) | ingest, situate, solve_draft | fetch-filings for a peer |
| A cited brief, never advice, reviewed and decided by people | Public company research: write-cited-brief, review-brief (a different worker), decide-delivery (a person's verb) | Added now | seed_hypothesis (brief), eval_run (review), benchmark_suite (brief checks) | solve_draft, verify_gate | |
| Owned examples, curated and frozen before any scoring | [Continuous tuning](../packs/continuous-tuning/README.md): register-rule (a person's verb), generate-examples, curate-dataset, freeze-test-set | Added now | code_node (promotion rule), benchmark_suite (batches, frozen test receipts) | verify_gate, solve_draft, ingest | train-adapter |
| An adapter trained, scored, reloaded and decided by the rule | Continuous tuning: train-adapter, evaluate, check-reload, decide-promotion (a different worker), promote-or-roll-back | Added now | model_spec (adapter card, champion pointer), eval_run (runs, reload check, decision, roll back) | solve_draft, benchmark_harness, verify_gate | the next round's generate-examples |

**Still needed here:** a descriptive options-chain review (greeks, implied volatility and roll
candidates, described and never ordered); checked analysis of a CSV file; and research intake
from newsletters and feeds.

## Work that supports every goal

[Repository review](../packs/repo-review/README.md), [Decomposition patterns](../packs/decomposition-patterns/README.md),
[Taste palettes](../packs/taste-palettes/README.md), [Harness onboarding](../packs/harness-onboarding-e2e/README.md),
[Cost optimization](../packs/cost-optimization/README.md) and [Docs improvement](../packs/docs-improvement/README.md)
exist in this library. Decomposition patterns is where verbs most clearly create verbs:
a breakdown becomes child task previews, and the requester enqueues them.
[Findings to fixes](../packs/findings-to-fixes/README.md), added later on October 29, turns every
error, issue, design flaw or annoyance noticed in any of this work into recorded, fixed and
verified work.

## Not packs

These are infrastructure, not seed packs, and are not built here: Tessera's flag-gated
schedule support that the daily proposals need; any importer that writes a pack's nouns;
and delivery of results to people. Every schedule noun in this library says it is not
activated.
