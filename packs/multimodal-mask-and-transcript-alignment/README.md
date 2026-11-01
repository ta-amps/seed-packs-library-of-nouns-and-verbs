# Multimodal mask and transcript alignment

## What this pack lets workers do

A collection of nouns and verbs for aligning image segmentation masks, speech-to-text word timings,
and layout safe zones across multimodal media pipelines, with tested standard-library Python code.
When video or AR pipelines burn captions into fixed bottom bands without checking foreground
segmentation masks or audio-visual word drift, overlays cover tracked objects and lag spoken cues.
Workers normalize bounding-box or polygon masks, group word timestamps into caption spans, measure
spoken-cue to mask-onset drift in milliseconds, and route each caption into a non-occluding safe zone.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Captions must not occlude segmented subjects (`intrusion <= 0.05`); flag audio-visual drift `> 250 ms` |
| Geometry and sync rules | Box IoU, Shoelace polygon area, intrusion ratio, and spoken-token to mask-onset delta |
| Templates | Multimodal timeline input, safe-zone placement record, and alignment verification report |
| Record checks | Deterministic checks on alignment reports with synthetic good and bad fixtures |
| Tool card and code | Tested standard-library Python package in [code/](code/README.md) (`multimodal_align`) |
| Sources | 2 dated public sources on W3C WebVTT cue positioning and ITU-R BT.1359-1 audio-visual sync |
| Worked examples | Synthetic mask-aware caption reroute from `bottom_band` to `top_band` |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `normalize-masks-and-utterances` | agent, no model | Normalize pixel or polygon masks and group word timings into utterances |
| `audit-audiovisual-cue-drift` | agent, no model | Measure millisecond offset between spoken object tokens and mask onset frames |
| `route-non-occluding-safe-zones` | agent, no model | Pick the highest-priority safe zone keeping mask and HUD intrusion within budget |

Each verb can also end with `no_change`, `unknown`, or `blocked`, and proposes follow-up verbs
instead of enqueueing them.

## Limits

- A proposal: not installed, imported, admitted, or activated, and no worker has run these verbs.
- Uses tight polygon bounding boxes for fast safe-zone intrusion checks; concave mask cutouts are
  conservatively over-approximated.
- Does not run segmentation or speech recognition models; consumes their JSON outputs deterministically.
