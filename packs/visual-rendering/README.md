# Visual and 3D rendering

## What this pack lets workers do

A collection of nouns and verbs for rendering images, motion graphics and 3D scenes and
checking the results. Workers turn a visual brief into a scene recipe, assets and motion
written as code, render it deterministically with no model per frame, check it
automatically for size, frames, contrast, safe areas, missing resources, licenses and a
reduced-motion alternative, and have someone else review it.

## Nouns

| Noun | What it holds |
| --- | --- |
| Quality checks | Eleven checks with thresholds and methods |
| Contrast example | Synthetic: five color pairs with their published contrast ratios, which the validator recomputes |
| Tool cards | Blender (GPL-2.0-or-later code; your renders are yours) and three.js (MIT); the [video and motion pack](../video-motion/README.md)'s FFmpeg, Playwright and Chromium cards and media template are reused |
| Templates | Scene recipe, asset recipe, motion profile, render manifest, check report and review notes |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| plan-scene | Writes the scene recipe, asset recipes and motion profiles | Scene, assets, motion |
| prepare-assets | Makes or gathers assets with digests and allowed licenses | Assets |
| render | Renders twice with a pinned renderer; no model per frame | Media, render manifest |
| check-render | Runs every quality check and proposes fixes for failures; deterministic | Check report |
| review-render | A person or a different worker looks and decides | Review notes |

Each verb can also end with `no_change`, `unknown` or `blocked`.

## How to use it

Use a video storyboard scene or a palette brief as the visual brief. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- GPU renders may differ slightly between machines, so repeatability uses SSIM there.
- Scene scripts run only in a sandbox and only when pinned and reviewed.
- A proposal: nothing has been rendered with these verbs yet.
