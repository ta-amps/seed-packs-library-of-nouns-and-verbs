# Video showcase

## What this pack lets workers do

A collection of nouns and verbs for making a truthful demo video. Workers draft a
script, storyboard it, capture real screens with demo data, transcribe a person's
narration into captions, and lay in music and sound under a license policy. Drawn
scenes, assembly, rendering in 16:9 with an optional 9:16 cut and the encoded-video
checks use the [video and motion pack](../video-motion/README.md). A reviewer runs the
showcase checks and watches the cut; the owner releases it and records where. Every
number on screen links to the test run, record or source it came from.

## Nouns

| Noun | What it holds |
| --- | --- |
| Style guide and style presets | Formats, content rules, caption and audio defaults; title, lower-third, caption, highlight and end-card styles |
| Asset policy | Which music, sound, still and clip licenses are allowed, and how to attribute them |
| Showcase checks | Evidence coverage, asset licenses, generated-media labels, duration against the brief and caption style |
| Templates | Brief, script, storyboard, shot list, capture plan, audio cue sheet, evidence link, captions, review notes, publication record |

Tool cards for FFmpeg, Playwright and Chromium, the media template and the encoded-video
checks live in the video and motion pack, so each is defined once.

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| draft-script | agent | Timed beats; every number listed as a claim with an evidence-link draft |
| storyboard | agent | Scenes, shots and step-by-step capture plans |
| capture-screen | agent or person | Scripted captures of local or demo targets |
| record-narration | person | Reads the script in their own voice; no model |
| transcribe-captions | agent | Timed captions, with differences from the script listed |
| prepare-audio | agent | Music, sound effects and ambience under the asset policy, mixed into one bed |
| review-video | person or different agent | Runs the showcase checks, watches it, checks every claim, decides |
| record-publication | person | The owner releases or holds the approved cut and records which |

Between them, the flow uses the video and motion pack's draft-scene for drawn scenes,
plan-sequence, render-sequence and check-video. Each verb can also end with `no_change`,
`unknown` or `blocked`, and can propose follow-up verbs.

## How to use it

Write a video brief shaped like `template.video-brief`. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: no video has been made with these verbs yet.
- Workers never release anything; only the owner does, outside the fabric.
- Loudness and caption numbers are common web defaults, not measured requirements; the
  style guide's loudness becomes the sequence's target.
- The renderer accepts only CC0-1.0, CC-BY-4.0, MIT and its own procedural license, so
  owner-recorded captures and narration need one of those before they can be rendered.
