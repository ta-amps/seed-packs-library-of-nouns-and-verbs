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
| Storyboard and shot list | Video showcase: storyboard | Exists | scene_recipe (storyboard, shot list, capture plan) | solve_draft | capture-screen per capture, render-scenes |
| Screen capture of real products | Video showcase: capture-screen | Exists | scene_recipe (media), code_node (Playwright, Chromium cards) | compile_dag | |
| Narration, a person's verb | Video showcase: record-narration | Exists | scene_recipe (media) | solve_draft (human) | transcribe-captions |
| Transcribed captions | Video showcase: transcribe-captions | Exists | scene_recipe (caption track) | ingest | |
| Motion graphics as code | [Visual and 3D rendering](../packs/visual-rendering/README.md): plan-scene, render | Added now | motion_profile, scene_recipe (scene, asset) | solve_draft, compile_dag | prepare-assets |
| Audio layers, sound effects and music with license checks | Video showcase: prepare-audio, asset policy | Added now | skill_pack (asset policy), scene_recipe (audio cue sheet) | compile_dag | |
| Video layers and styles | Video showcase: style presets, layered sequence | Added now | skill_pack (style presets), scene_recipe (sequence with layers) | compile_dag (assemble) | |
| Render and encode | Video showcase: render-scenes, assemble; Visual and 3D rendering: render | Exists, extended | eval_run (render manifest), code_node (FFmpeg, Blender, three.js) | compile_dag | video-qa |
| Every-frame and loudness QA | Video showcase: video-qa; Visual and 3D rendering: check-render | Exists, extended | benchmark_suite (thresholds, quality checks), eval_run (QA report) | verify_gate | fixes for failed checks |
| Independent review | Video showcase: review-video | Exists | eval_run (review notes) | verify_gate (person or different agent) | |
| Release, a person's verb | Video showcase: record-publication | Added now | eval_run (publication record) | verify_gate (human) | |
| Tool and benchmark freshness for video and motion tools | [Tool discovery](../packs/tool-discovery/README.md), [Benchmark scores](../packs/benchmark-scores/README.md) | Exists, added now | code_node (candidates), eval_run (scores), benchmark_suite (trials) | probe_source, fetch_feed, recheck_fragility, benchmark_harness | run-trial, compare-on-profile |

**Still needed for video:** caption translation into other languages; an audio
description track for blind viewers; narration audio checks for noise floor and
clipping; delivery presets per platform; and sourcing of licensed music and stock clips.

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

## Work that supports every goal

[Repository review](../packs/repo-review/README.md), [Decomposition patterns](../packs/decomposition-patterns/README.md),
[Taste palettes](../packs/taste-palettes/README.md), [Harness onboarding](../packs/harness-onboarding-e2e/README.md),
[Cost optimization](../packs/cost-optimization/README.md) and [Docs improvement](../packs/docs-improvement/README.md)
exist in this library. Decomposition patterns is where verbs most clearly create verbs:
a breakdown becomes child task previews, and the requester enqueues them.

## Not packs

These are infrastructure, not seed packs, and are not built here: Tessera's flag-gated
schedule support that the daily proposals need; any importer that writes a pack's nouns;
and delivery of results to people. Every schedule noun in this library says it is not
activated.
