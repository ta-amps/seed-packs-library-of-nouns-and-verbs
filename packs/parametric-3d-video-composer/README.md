# Parametric 3D video composer

## What this pack lets workers do

A collection of nouns and verbs for planning parametric 3D Product Hub camera trajectories,
realistic browser chrome layouts, safe-area and lower-caption-band boundaries, and
zero-double-exposure transitions in programmatic explainer videos. In plain language, nouns are
**task objects** (3D camera recipes, safe-stage rules, pinned standard-library code, schemas and
worked examples) and verbs are **tasks** a worker claims. Workers plan `1x3` and `2x2` Product Hub
zoom-in and zoom-out sequences, calculate browser tab and viewport geometry inside the upper safe
stage (`x: 96..1824, y: 72..820`), protect the dedicated lower caption band (`y: 836..1080`), block
text-on-text crossfades, and compute subtle aura and edge-packet interpolation curves.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Reserve `y: 836..1080` exclusively for captions; never crossfade two text-bearing shots; clamp aura glow opacity below neon levels |
| `spec.product-hub-camera` | `1x3` and `2x2` Product Hub 3D perspective camera choreography (`overview -> pillar_focus -> bridge_zoom_out -> next_pillar -> finale_hub`) with quintic C2 easing |
| `rules.stage-and-browser-layout` | Upper safe stage (`x: 96..1824, y: 72..820`), `16 px` gutter, lower caption band (`y: 836..1080`), and desktop browser chrome dimensions |
| `rules.transitions-and-auras` | Zero-double-exposure transition rules plus quadratic Bezier edge-packet and clamped card aura curves |
| `tool.parametric-composer` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.composition-check` | JSON Schema for a verified 3D camera, browser layout and transition report |
| Worked example | Made-up `1x3` Product Hub scene (`example.hub-scene-spec`) and recomputed verification (`example.composition-check`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `plan-hub-camera-trajectory` | agent, no model | Plan `1x3` or `2x2` 3D perspective camera poses and quintic easing segments across all pillars |
| `layout-browser-and-verify-safe-band` | agent, no model | Calculate browser window, tab and omnibox rects and verify zero excursions into `y: 836..1080` |
| `validate-transitions-and-curves` | agent, no model | Reject text-on-text crossfades and compute subtle card aura and Bezier edge-packet curves |
| `compile-composition-check` | agent, no model | Emit a conforming composition check report before rendering frames |

## How to use it

Run `make check` in [code/](code/README.md) to compile with warnings treated as errors and run all
camera projection, safe-area collision, transition and worked-example tests.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these Tasks through the shared work queue.
- The worked example in `source.json` is made-up.
- Geometric preflight guarantees coordinate bounds before render; encoded video output still needs
  post-render inspection via [frame-by-frame video QA](../frame-by-frame-video-qa/README.md).
