# Video showcase

## What this pack lets workers do

Make a truthful demo video as ordinary claimed work. Workers draft a script, storyboard
it, capture real screens with demo data, render title cards and diagrams, transcribe
a person's narration into captions, assemble and encode 16:9 (plus an optional 9:16
cut), check the file automatically and review it. Every number on screen links to the
test run, record or source it came from.

## Nouns

| Noun | What it holds |
| --- | --- |
| Style guide | Formats, content rules, caption and audio defaults the brief can override |
| QA thresholds | Ten checks with thresholds and FFmpeg commands: black and frozen frames, loudness, format, duration, captions, frame digests, evidence, labels |
| Tool cards | FFmpeg (license depends on the build), Playwright (Apache-2.0) and Chromium (BSD-3-Clause plus bundled licenses) |
| Templates | Video brief, script, storyboard, shot list, capture plan, media, evidence link, caption track, render manifest, sequence, QA report and review notes |

## Verbs

| Verb | Who | What happens | Produces |
| --- | --- | --- | --- |
| draft-script | agent | Timed beats; every number listed as a claim | Script, evidence-link drafts |
| storyboard | agent | Scenes, shots and step-by-step capture plans | Storyboard, shot list, capture plan |
| capture-screen | agent or person | Scripted captures of local or demo targets | Media |
| record-narration | person | Reads the script in their own voice; no model | Narration media |
| transcribe-captions | agent | Timed captions, with differences from the script listed | Caption track |
| render-scenes | agent | Deterministic title cards and diagrams; no model per frame | Media, render manifest |
| assemble | agent | Cuts, crossfades, narration mix, captions, 16:9 and optional 9:16 | Sequence, encoded media |
| video-qa | agent | Runs every QA check and records each measurement | QA report |
| review-video | person or different agent | Watches it, checks every claim, decides | Review notes |

Each verb can also end with `no_change`, `unknown` or `blocked`.

## Kinema alignment

Kinema is being extended on a separate branch with 16:9 output, media and sequence
nouns, and render and QA verbs. This pack uses the same words in the same sense:
**scene recipe**, **media** (a hash-pinned recording, image or audio file),
**sequence** (ordered clips with cuts and crossfades), **render** and **QA**.
`render-scenes` hands pinned Kinema scene recipes to Kinema's renderer when it is
installed and qualified. Nothing here depends on that branch landing.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only in your assigned scope, write a
video brief shaped like `template.video-brief`, then fill `draft-script` from
[verbs.json](verbs.json) with `scripts/build_packs.py --instantiate` and enqueue it
yourself. Later verbs take the pins of the nouns earlier verbs produced.

## Limits

- A proposal: no video has been made with these verbs yet.
- Tool cards pin no build. A worker records the exact version, configuration and
  binary digest it used; this pack installs nothing.
- Publishing the video is the owner's separate decision; every verb keeps outputs private.
- Loudness and caption numbers are common web defaults, not measured requirements.
