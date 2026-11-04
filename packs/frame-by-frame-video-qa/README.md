# Frame-by-frame video QA

## What this pack lets workers do

A collection of nouns and verbs for inspecting every frame of an encoded video with nine
deterministic computer-vision detectors and UI region masks. In plain language, nouns are **task
objects** (specs, question banks, safe-area rules, pinned code, templates and worked examples) and
verbs are **tasks** a worker claims. Workers decode every frame into a SHA-256-pinned cache, measure
temporal changes and spatial text, panel and edge layouts, check UI control masks for caption or
callout occlusions, cluster nearby frame hits into shot-indexed findings with annotated PNG crops,
draw a seeded stratified sample for human labelling, and compute Wilson precision intervals.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Bind every cache and finding to the exact video SHA-256; run offline with model-free fallbacks; quote precision only from independently labelled samples |
| `spec.detectors` | Sampling cadence, safe areas, nine visual detectors (`cut_off_content`, `cut_off_windows`, `overlaps`, `small_text`, `transitions`, `freezes_and_motion`, `caption_collisions`, `contrast`, `layered_edges`) and clustering rules |
| `spec.ui-masks` | Connected-component UI region segmentation and optional local Meta SAM (`facebook/sam-vit-base`) mask adapter with UI occlusion thresholds |
| `questions` | Concrete QA question bank paired with each of the nine detectors |
| `rules.safe-areas` | Title-safe (`5%`), action-safe (`3.5%`), caption-band (`18%`) and `390 px` phone legibility constants |
| `tool.frame-qa` | Tested code in [code/](code/README.md), pinned by path, file count and SHA-256 digest |
| Templates | `template.findings` for multi-cut QA reports and `template.review-labels` for human precision labels |
| Worked example | Made-up 90-frame 1080p measurements (`example.measurements`), recomputed clustered findings (`example.findings`) and labelled precision (`example.review-labels`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `sample-frames` | agent, no model | Decode every frame locally and write temporal and spatial measurements pinned to the video digest |
| `run-detectors` | agent, no model | Run the nine visual detectors over the cached measurements and optional WebVTT cues |
| `segment-ui-masks` | agent, local optional | Segment UI buttons, inputs and panels via connected components or local SAM masks and flag caption or callout occlusions |
| `cluster-findings` | agent, no model | Join frame hits across short gaps into shot-indexed findings with crops, timelines and [findings to fixes](../findings-to-fixes/README.md) records |
| `draw-review-sample` | agent, no model | Draw a seeded stratified sample of findings covering every firing detector |
| `label-review-sample` | human | Inspect sampled crops and label each finding as `true_positive` or `false_positive` |
| `compute-precision` | agent, no model | Compute per-detector and overall Wilson 95 percent precision intervals from the labels |

## How to use it

Run `make install && make check` in [code/](code/README.md) to compile with warnings as errors, run
made-up clip renders, test connected-component and SAM mask adapters, and recompute the worked
example from `source.json`.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these tasks through Tessera.
- The worked example in `source.json` is made-up and tests deterministic agreement between the
  pack schema and `code/frame_qa`.
- Optional local OCR (`rapidocr-onnxruntime`) and optional local Meta SAM (`facebook/sam-vit-base`)
  adapters never download weights over the network; when absent, model-free OpenCV connected
  components run instead.
- Automated detector hits are candidates, never release approval; a person watches the cut and
  weighs style intent via the [video review pack](../video-review/README.md).
