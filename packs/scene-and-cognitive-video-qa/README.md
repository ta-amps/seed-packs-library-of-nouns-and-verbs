# Scene and cognitive video QA

## What this pack lets workers do

A collection of nouns and verbs for multi-frame scene, transition, camera-zoom stability,
reading-speed and split-attention cognitive-load, live desktop web-journey provenance, and
widescreen lower-band frosted-caption geometry checks. In plain language, nouns are **task objects**
(multi-frame thresholds, frosted-caption geometry rules, pinned standard-library code, schemas and
synthetic worked examples) and verbs are **tasks** a worker claims. Going beyond single-frame pixel
checks, workers evaluate groups of frames across scene cuts for sub-second flash cards and
text-over-text crossfades, block unmotivated Ken Burns zoom or pan drift on static slides and
terminals, catch stage prose that outpaces human reading or competes with concurrent speech, verify
that website recordings show an authentic desktop browser landing page and click transition without
submitting live forms, and check that burned-in frosted-glass rounded-pill captions sit centered in
the widescreen lower horizontal space.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Bind reports to exact MP4 SHA-256; never submit live forms during synthetic captures; lock static slides, cards and terminals at 1:1 scale unless a focal target is named |
| `spec.scene-cognitive-gates` | Shot dwell (`>= 1.6 s`), text crossfade (`<= 4` frames), static-slide scale lock (`< 0.003` drift), reading time (`>= 0.45 + words/3.5 s`), speech-vs-stage lexical overlap (`>= 0.35` for `>= 12`-word prose), desktop web provenance (`>= 1280 px`, entry + click) and lower-band caption centering (`(960, 1006) +/- 3 px` in `y=932..1080`) |
| `rules.frosted-caption-pill` | Deterministic widescreen lower-band frosted-glass rounded-pill layout (`18 px` radius, blurred backdrop, specular rim, clause-balanced two-line wrapping, native fullscreen `<track>` disabled) |
| `tool.scene-cognitive-qa` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.scene-cognitive-qa-report` | JSON Schema for a digest-pinned multi-frame scene and cognitive video QA report |
| Worked example | Synthetic defective video bundle (`example.scene-cognitive-bundle`) and recomputed QA report (`example.qa-report`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `audit-shot-dwell-and-transitions` | agent, no model | Check multi-frame shot durations and block ghosting text-over-text crossfades across cuts |
| `audit-camera-and-slide-stability` | agent, no model | Flag unmotivated Ken Burns zoom or pan drift on static slides, cards, terminals and browser captures |
| `audit-reading-and-cognitive-load` | agent, no model | Check on-screen reading speed, disallowed `must_read=False` escapes, and split-attention prose conflicts against concurrent speech |
| `audit-web-journey-and-captions` | agent, no model | Verify `>= 1280 px` desktop website landing-and-click provenance and centered frosted-glass lower-band captions |
| `compile-scene-cognitive-report` | agent, no model | Combine all five multi-frame and cognitive checks into one digest-pinned QA report |

## How to use it

Run `make check` in [code/](code/README.md) to compile with warnings treated as errors and execute
all unit tests plus the worked-example recomputation from `source.json`.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these tasks through Tessera.
- The worked example in `source.json` is synthetic.
- Automated multi-frame and cognitive gates catch structural timing, drift, provenance and layout
  defects, while a human viewer still judges tone, clarity and visual craft.
