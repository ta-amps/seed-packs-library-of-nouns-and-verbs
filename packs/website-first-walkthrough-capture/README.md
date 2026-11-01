# Website-first walkthrough capture

## What this pack lets workers do

A collection of nouns and verbs for checking website-first walkthrough shot lists and generating deterministic browser recorder plans in the v6 capture window (`1280x613` CSS px at device scale `1.5`) with real surface hosts, take ids, request-band anchors, `1.8 s` minimum shots, reading-speed holds, no status stamps and zero camera drift.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Keep footage on permitted live HTTPS pages at camera scale `1.000` with `0 px` drift, forbid credentials in URLs, require `#step-split..#step-ready` anchors on request-status shots, and require `distinct_reviewer` |
| `spec.film-frame-v6-footage-and-pacing` | `1280x613` CSS px window (`1920x920` device px at `1.5x`), `1.8 s` minimum shot duration, `800 CSS px/s` max scroll speed and `8`-word callout cap during speech |
| `tool.walkthrough-capture` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.storyboard-check-receipt` | JSON Schema for pre-recording storyboard check receipts |
| `template.walkthrough-capture-plan` | JSON Schema for per-cut browser recorder plans |
| Worked example | Three-cut storyboard v3 check receipt (`example.storyboard-v3-check-receipt`) verified by unit tests |

## Verbs

| Verb (task: thing to do) | Who | What happens |
| --- | --- | --- |
| `check-shot-list` | agent, no model | Independently check a walkthrough storyboard against all v6 footage, pacing, URL-hygiene and wording rules (`distinct_reviewer`) |
| `plan-takes` | agent, no model | Write the per-shot browser recorder plan (`1280x613` CSS px, `1.5x` scale, take ids, anchors and scroll rules) |

## How to use it

Run `make check` in [code/](code/README.md) to run all 10 unit tests covering the three-cut storyboard v3 fixture, flash-cut/stamp/Ken-Burns/off-site/URL-credential/anchor/retired-name rejections and `ZeroHardcodedValuesAstGate`.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks (things to do) through Tessera.
- Pre-recording checks validate shot-list contracts offline; real browser recording and frame inspection still run during production.
