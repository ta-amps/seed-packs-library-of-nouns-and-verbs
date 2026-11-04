# Video QA checks

## What this pack lets workers do

A collection of nouns and verbs for automated checks on an encoded video beyond the eight
post-encode checks of the [video and motion pack](../video-motion/README.md). Workers hash the exact
file, run pinned FFmpeg analyses on it and keep every log, then check blank and frozen frames against
the holds the plan declared, the cut cadence and stretches with almost no visual change, loudness
range, true peak, the quietest window, silence gaps and clipping. They lint the WebVTT and SRT
sidecars for line length, reading speed, gaps and parity and time every cue against measured speech,
read the delivery spec from the MP4's own boxes, and run a legibility proxy for text whose size is
known. One report binds every row to the file's SHA-256. A person still watches and listens.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Measure the exact bytes; declare holds, pauses and black before measuring; not run is never a pass; checks are not approval |
| Extended checks | Nine checks with thresholds: blank frames, frozen stretches, cut cadence, loudness, silence gaps, clipping, captions, file spec, legibility |
| Measurement rules | The exact FFmpeg runs whose logs the checks read, and the gotchas that bit one production |
| Tool card | The pack's tested code in [code/](code/README.md), pinned by digest |
| Templates | QA plan, measurement set, text items, check rows and the extended QA report |
| Report checks | Six checks on a report, with one good and six bad summaries the validator recomputes |
| Checklist, sources, test cases | What a person does with a report; 9 dated public sources; 7 made-up cases |
| Worked example | Made-up: a 12-second vertical cut's logs, sidecars and MP4 facts, and the report the code computes from them |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `collect-measurements` | agent, no model | Hash the file, run the pinned FFmpeg analyses, keep every log with its digest |
| `lint-captions` | agent, no model | Lint both sidecars, compare them and time cues against speech; never fix them |
| `check-picture` | agent, no model | Blank and flat frames, frozen stretches and cut cadence, honoring declared spans only |
| `check-sound` | agent, no model | Loudness against the target, true peak, range, the quietest window, silence and clipping |
| `check-file-spec` | agent, no model | The MP4's boxes against the export spec, from fast start to the size budget |
| `check-legibility` | agent, no model | Text size against role floors and the smallest display, reading time and safe areas |
| `compile-qa-report` | agent, no model | One report per file with a verdict that follows from its rows, and fix proposals |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs, such
as [findings to fixes](../findings-to-fixes/README.md) `record-finding` for each failure, instead of
enqueueing them. The [video review pack](../video-review/README.md) reads the report as evidence.
The page and player around a video, with its captions track, controls and audio description, are
the [accessibility audit pack](../accessibility-audit/README.md)'s `check-media`; this pack measures
the encoded file. Its contrast follows that pack's method, and the code's tests check it against
that pack's recorded ratios. A single frame with known layout can go through the
[screenshot design review pack](../screenshot-design-review/README.md).

## How to use it

Run `make check` in [code/](code/README.md) to recompute the worked example. Write the nouns in
[nouns.json](nouns.json) create-only with a key scoped to your team's surface, then fill a template
from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has claimed these verbs
  through Tessera. The checks were run by hand on ta-amps's own 3:00 explainer film while this pack
  was written; that is a trial of the code, not a run of these verbs.
- The worked example is made-up. Its logs follow FFmpeg 7's formats, and its scene scores and luma
  ranges are sampled twice per second for brevity, where a real run samples every frame.
- Thresholds are defaults from one production, not standards. A dissolve or camera move rarely
  scores as a cut, so shot lengths are upper bounds and still stretches are only warnings.
- The legibility proxy needs each text's size from the stage, the layout or a measurement. It cannot
  see weight, stroke, motion, blur or a busy background, and its 12 px floor comes from a web audit
  that Lighthouse has since removed.
- Loudness rows measure levels, not how a mix sounds; a person listens. Sources were checked on
  2026-10-30. Recheck them before relying on them.
