# Video showcase

## What this pack lets workers do

A collection of nouns and verbs for making a truthful demo video. Workers draft a
script, storyboard it, capture real screens with demo data, render title cards and
diagrams, transcribe a person's narration into captions, lay in music and sound under
a license policy, assemble layered 16:9 video with an optional 9:16 cut, check every
frame and the loudness, and review it. The owner releases it and records where. Every
number on screen links to the test run, record or source it came from.

## Nouns

| Noun | What it holds |
| --- | --- |
| Style guide and style presets | Formats, content rules, caption and audio defaults; title, lower-third, caption, highlight and end-card styles |
| Asset policy | Which music, sound, still and clip licenses are allowed, and how to attribute them |
| QA thresholds | Eleven checks with commands: black and frozen frames, loudness, format, duration, captions, frame spot checks, licenses, evidence, labels |
| Tool cards | FFmpeg (license depends on the build), Playwright (Apache-2.0), Chromium (BSD-3-Clause plus bundled licenses) |
| Templates | Brief, script, storyboard, shot list, capture plan, media, audio cue sheet, evidence link, captions, render manifest, sequence with layers, QA report, review notes, publication record |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| draft-script | agent | Timed beats; every number listed as a claim with an evidence-link draft |
| storyboard | agent | Scenes, shots and step-by-step capture plans |
| capture-screen | agent or person | Scripted captures of local or demo targets |
| record-narration | person | Reads the script in their own voice; no model |
| transcribe-captions | agent | Timed captions, with differences from the script listed |
| render-scenes | agent | Deterministic title cards and diagrams; no model per frame |
| prepare-audio | agent | Music, sound effects and ambience under the asset policy, ducked under narration |
| assemble | agent | Cuts, crossfades, layers, captions; 16:9 and optional 9:16 |
| video-qa | agent | Every QA check with its measurement |
| review-video | person or different agent | Watches it, checks every claim, decides |
| record-publication | person | The owner releases or holds the approved cut and records which |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose
follow-up verbs. These words match the other visual packs: scene recipe, media,
sequence, render and QA.

## How to use it

Write a video brief shaped like `template.video-brief`. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: no video has been made with these verbs yet.
- Tool cards pin no build; workers record the exact version and binary digest they used.
- Workers never release anything; only the owner does, outside the fabric.
- Loudness and caption numbers are common web defaults, not measured requirements.
