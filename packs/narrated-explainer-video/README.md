# Narrated explainer video

## What this pack lets workers do

A collection of nouns and verbs for making a narrated explainer video with code, as one pipeline of
claimed verbs that each end with a receipt. Workers lay out a script and cut plan on one frame
clock, narrate it with the [voice narration pack](../voice-narration/README.md), write scenes on a
frame-addressable HTML stage and render them losslessly, time captions to the measured voice and
check them against what it said, compose a caption-free master and an open-captions variant,
check and frame-sheet the encoded files, list every step's receipt, and hash every delivered file
for the owner's decision. The script, storyboard, review and release record come from the
[video showcase pack](../video-showcase/README.md); encoding and post-encode checks come from the
[video and motion pack](../video-motion/README.md).

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Every step a claimed verb with a receipt; one frame clock; every claim checked against its record; every layer disclosed; the voice pack's AI-voice label |
| Frame clock rules | Clip and beat spans from frames and crossfades, narration placement, frame-sheet times, exact rounding |
| HTML stage rules | Scenes as pure functions of time, embedded fonts, no network, a pinned browser, lossless slices, a determinism probe |
| Caption rules | Text from the script, splits snapped to measured pauses, the style guide's limits, WebVTT and SRT, a round-trip check |
| Tool card | The pack's tested code in [code/](code/README.md), pinned by digest: clock, captions, manifest and ledger checks |
| Templates | Cut plan, stage, slice recordings, caption cues, caption check, compose record, frame sheet, receipts ledger, release manifest |
| Release checks | Eight checks on a release manifest, with one good and eight bad manifests the validator recomputes |
| Checklist, sources, test cases | What a person checks before release; 7 dated public sources; 9 synthetic cases |
| Worked example | Synthetic: a 20-second cut, the voice pack's two placed lines, four cues with WebVTT and SRT, and a manifest with real digests |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `plan-cut` | agent | Lay out every cut on one frame clock |
| `build-stage-scenes` | agent | Write the scenes on the HTML stage and pass the determinism probe |
| `render-slices` | agent, no model | Render and encode every slice losslessly, with digests |
| `time-captions` | agent, no model | Cues from the placed lines, timed to the measured voice, with sidecars |
| `check-captions` | a different agent, no model | Recheck the rules and transcribe each line; list deviations, never fix them |
| `compose-cut` | agent, no model | Check every claim and the closing line, then build both variants |
| `make-frame-sheet` | agent, no model | One decoded frame per clip from the delivered file |
| `compile-receipts` | agent, no model | Every step's receipt and failed attempts, read from Tessera |
| `assemble-release-manifest` | agent, no model | Hash every delivered file; released stays false |

The whole flow, in the descriptor noun, also runs the video showcase pack's `draft-script`,
`storyboard`, `review-video` and `record-publication`, the voice narration pack's six verbs, and the
video and motion pack's `render-sequence` and `check-video`. Each verb can also end with
`no_change`, `unknown` or `blocked`, and can propose follow-up verbs.

## How to use it

Run `make check` in [code/](code/README.md) to recompute the worked example. Write the nouns in
[nouns.json](nouns.json) create-only with a key scoped to your team's surface, then fill a template
from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has claimed these verbs
  through Tessera. They package the pipeline ta-amps is using for its own explainer video, run as
  local verbs on a local store; that production was still in draft runs when this pack was written,
  and nothing here claims its result.
- The worked example is synthetic and renders no video; only its cut plan and sidecar digests are
  real. The code checks timing, captions, manifests and ledgers; it renders nothing.
- Pixel identity holds only for the same browser build, fonts and flags.
- A round-trip recognizer is a proxy: it cannot hear stress or warmth, so a person still listens.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
