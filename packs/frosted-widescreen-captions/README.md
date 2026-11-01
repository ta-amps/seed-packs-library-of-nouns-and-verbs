# Frosted widescreen captions

## What this pack lets workers do

A collection of nouns and verbs for planning, wrapping, rendering and checking burned-in widescreen film captions in a 156 px lower band (`y` 924-1080) with a frosted pill centered at `(960, 1002)`, clause-then-balance line breaks, small-gap cue bridging and reading-time checks.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Never draw a native browser caption box (`showing`) over burned-in pills; require `distinct_reviewer` before admitting caption check receipts |
| `spec.film-frame-v6-caption-band` | Canonical `1920x1080` frame split (`y` 4-924 stage, `y` 924-1080 band), `(960, 1002)` pill center, `24 px` edge clearance and `0.5 + words/3.0 s` reading budget |
| `rules.clause-then-balance-wrapping` | Deterministic `2x42` clause-boundary and line-balance penalty weights plus protected model-name tokens |
| `tool.frosted-captions` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.caption-cue-plan` | JSON Schema for wrapped caption cue plans and band dimensions |
| `template.caption-band-check-receipt` | JSON Schema for v6 caption timing, clearance and AST gate receipts |
| Worked example | Made-up v6 caption check receipt (`example.v6-caption-check-receipt`) recomputed by unit tests |

## Verbs

| Verb (task: thing to do) | Who | What happens |
| --- | --- | --- |
| `plan-cues` | agent, no model | Split narration lines into `2x42` clause-balanced cues with bridged visibility spans |
| `render-band` | agent, no model | Render deterministic `1920x156` SVG caption band frames centered at `(960, 1002)` |
| `check-cues` | agent, no model | Independently verify zero `check()` errors and full band/guide clearance (`distinct_reviewer`) |

## How to use it

Run `make check` in [code/](code/README.md) to run all 17 unit tests covering clause wrapping, protected names, gap bridging, reading budgets, `(960, 1002)` geometry, SVG escaping and `ZeroHardcodedValuesAstGate`.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks (things to do) through Tessera.
- Character-advance width estimates support offline planning without font binaries; final video compositors still verify rendered pixel bounds.
