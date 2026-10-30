# Thumbnails and titles

## What this pack lets workers do

A collection of nouns and verbs for thumbnail and title candidates, checked for small sizes and
honesty, tested by plan and picked by a person. Workers draft three to six titles and several frame
or designed covers from what the video actually shows, check every cover's text at the small sizes
people see it and its contrast unrounded, and check every candidate's honesty: each claim traced to
the video's claim trace, no banned clickbait pattern, and a moment that keeps each promise. The
candidates that pass go side by side for a person to pick, and an A/B plan with its decision rule
fixed before any result is written for a person to run in the platform's own test tool.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Promise only what the video delivers; a person picks; no spoilers for reveals; a person runs every test |
| Small-size rules | Text size at each display width with a 12 CSS px floor, five words or fewer, contrast, designed frames |
| Honesty rules | Traced claims with their qualifiers, a banned pattern a requester may only extend, plain titles |
| A/B plan rules | One variable, two or three variants, the platform's own measure, rules fixed in advance |
| Templates | Title candidates, thumbnail candidates, size check, honesty check, A/B plan, A/B result |
| Title checks | Five checks on a title and cover, with one good and five bad pairs the validator recomputes |
| Contrast example | Three covers' text colours with WCAG ratios the validator recomputes |
| Checklist, sources, test cases | What a person checks before picking; 4 dated public sources; 5 synthetic cases |
| Worked examples | Synthetic: titles, covers, their size and honesty checks, and an A/B plan |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `draft-titles` | agent | Titles from what the video shows, with their claims and kept promises |
| `draft-thumbnails` | agent | Frame and designed covers, spoiler-free for reveals |
| `check-thumbnails` | agent, no model | Text CSS pixels at every display width, word counts and contrast |
| `check-honesty` | a different agent | Claims traced, banned patterns, promises kept |
| `plan-ab-test` | agent | An A/B plan fixed before any result, for a person to run |
| `record-ab-result` | person | What the platform's test reported and the decision by the plan's rule |

The [taste palettes pack](../taste-palettes/README.md)'s `assemble-comparison` and `record-choice` set
candidates side by side and keep a person's pick. Size and contrast use the
[video QA pack](../video-qa/README.md)'s code; a cover rendered from a layout can also go through the
[screenshot design review pack](../screenshot-design-review/README.md). Each verb can also end with `no_change`, `unknown` or
`blocked`, and proposes follow-up verbs instead of enqueueing them.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has claimed these verbs.
- Display widths are inputs, not facts about any platform, and the 12 px floor comes from a web audit
  that Lighthouse has since removed. A banned-pattern list catches wording, not every misleading cover.
- No test is run here, and a test's result says which variant won on one video, not why.
- The worked examples are synthetic; the library recomputes their sizes and contrast. Sources were
  checked on 2026-10-30. Recheck them before relying on them.
