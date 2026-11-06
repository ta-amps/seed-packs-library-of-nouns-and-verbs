# Video and motion with code

## What this pack lets workers do

A collection of nouns and verbs for video and motion made with code. Workers seek any frame
of a scene recipe directly, fit motion formulas to observation traces, draft scene recipes and
compile them into checked 9:16, 4:5 and 16:9 social formats, and plan, render and check a
video with cuts, crossfades, narration, a music bed and captions. Every verb runs the tested
code this pack ships in [code/](code/README.md), pinned by digest, with no model per frame or
per check. Other packs build on it: the video
showcase uses these verbs to render and check, and visual rendering reuses the tool cards.

## Nouns

| Noun | What it holds |
| --- | --- |
| Tool card: the video and motion tools | Where the pack's code is, its digest, commands, Python entrypoints, the `video` extra and the FFmpeg components the verbs need |
| Tool cards: FFmpeg, Playwright, Chromium | Licenses by build, required capabilities, install policy; shared with the other video packs |
| Reference builds | The exact FFmpeg, Chromium and Playwright binaries of the reference render, by SHA-256 |
| Procedural asset catalog | Characters, cards, charts and mechanisms with allowed licenses and definition digests |
| Motion formulas | Six narrative beats with their proportions, five easing curves and two built-in profiles |
| Aspect, caption and audio rules | Sizes, safe zones and keep-outs; caption size, wrapping and timing; ducking and loudness |
| Scene checks | Eight every-frame checks: keep-outs, type, occlusion, flicker, black and frozen runs, flashes, audio peaks, attributions |
| Video checks | Eight post-encode checks: streams, frames, SSIM spot checks, black, frozen, loudness, caption timing, disclosure |
| Scene recipes, demo sequence, sample trace | Example files in `code/examples/`, pinned by path and SHA-256 |
| Templates | Scene recipe, sequence, media, observation trace, motion profile, frame check, deliverable, scene QA report, render manifest, video QA report |

Nouns that state facts about the code carry a `tool_facts` object. The code's own tests
recompute every one and fail on any difference. The library runs the code only in its CI
tests; workers run it under their own permissions, and importing the pack runs none of it.

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| seek-frame | Evaluates frames by number, draws SVGs, proves order invariance | Frame check |
| fit-motion | Fits the beat and easing formula to a trace; optional retarget | Motion profile |
| draft-scene | Writes a scene recipe until every-frame QA passes | Scene recipe |
| compile-social-formats | SVG frames, contact sheets, captions and QA for each aspect | Deliverable record |
| check-social-formats | Reruns the eight scene checks and compares receipts | Scene QA report |
| plan-sequence | Assembles clips, media and captions until pre-render QA passes | Sequence, media |
| render-sequence | Renders MP4s at 1920x1080 and 1080x1920 with tool cards | Media, render manifests |
| check-video | Runs the eight post-encode checks on the decoded video | Video QA reports |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose follow-up
verbs. Checks preferably run on a different worker than the one that made the output.

## How to use it

Install the code from [code/](code/README.md), or use an installation whose files match the
tool card's digest. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to
your team's surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: no worker has claimed these Tasks through the shared work queue. The code itself is tested,
  including real FFmpeg and Chromium renders, locally and by this library's CI job for the pack.
- The demo's narration, music bed and inset image are generated placeholders, labeled as such.
- Pixels depend on the Chromium build and fonts; byte identity holds only for the same builds.
- The renderer accepts only CC0-1.0, CC-BY-4.0, MIT and its own procedural license.
- Scene checks read scene state, not pixels; the flash check is a screening rule, not a
  certification. Caption coverage is measured against narration loudness, not words.
