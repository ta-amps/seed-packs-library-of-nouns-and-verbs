# Deterministic Every-Frame QA Gate

`video_motion/qa.py` audits **every frame** (`[0 .. total_frames - 1]`) of a `SceneRecipe` across `reels_9x16` (`1080x1920`), `feed_4x5` (`1080x1350`) and, when requested, `landscape_16x9` (`1920x1080`) before a deliverable bundle can pass `compile_deliverable()`.

A recipe's `stage_aspect` (default `reels_9x16`) names the safe canvas its actor coordinates are authored in. The original 9:16-to-4:5 rule (remap Y only) is unchanged; every other pair maps normalized positions between safe canvases and scales sizes uniformly to fit. Per-aspect `AspectOverride`s (`dx`, `dy`, `scale_mul`, `opacity_mul`, `rotation_offset_deg`) then adapt the layout, for example restacking a 16:9 diagram vertically for 9:16. All three aspects are available through the library, the command line and the worker tools.

## Dual-Aspect Safe Zones & Reclaimed `4:5` Canvas

| Aspect Profile | Viewport | Platform UI Keep-Out Boxes | Safe Canvas |
|---|---|---|---|
| `reels_9x16` | `1080 x 1920` | Top chrome (`0,0,1080,160`), Right-rail buttons (`900,920,180,760`), Bottom caption drawer (`0,1560,1080,360`) | `x=64..884, y=180..1540` |
| `feed_4x5` | `1080 x 1350` | Top margin (`0,0,1080,60`), Bottom margin (`0,1290,1080,60`) | `x=64..1016, y=72..1278` (reclaims lower-right `x=620..1012, y=920..1266`!) |
| `landscape_16x9` | `1920 x 1080` | Top title overlay (`0,0,1920,64`), Bottom player controls (`0,1004,1920,76`) | `x=96..1824, y=80..984` (90% title-safe width) |

Because `4:5` Feed posts do not overlay a vertical engagement button column on the right edge, `compile_deliverable()` lets auxiliary metric cards and `reclaimed_lower_right` callouts occupy the lower-right `4:5` quadrant while automatically remapping or rejecting collisions on `9:16` Reels.

## The 8 Deterministic QA Checks

1. **`platform_ui_keep_out`**: Verifies that every active caption and callout box stays inside the viewport and has zero intersection area with `ASPECT_PROFILES[aspect].ui_keep_outs`.
2. **`min_font_and_line_balance`**: Requires `font_px >= 38.0` at `1080px` width, at most 3 lines per cue, no line exceeding `max_chars_per_line + 4`, and balanced line widths (`min_len / max_len >= 0.25` when `>= 4` words) so single-word orphans never ship.
3. **`subject_keep_out_occlusion`**: Protects every visible (`opacity >= 0.2`) focal actor's `subject_keep_out` head/hero zone (`is_subject_focus = True`) from caption overlap.
4. **`caption_flicker_jitter`**: Flags cues visible for fewer than `max(4, round(0.14 * fps))` frames, rapid 1–2 frame empty blink gaps between consecutive captions, and inter-frame caption box position jitter (`> 1.5px` on adjacent frames).
5. **`black_or_frozen_frames`**: Detects unintended dark/empty runs (`>= 3` frames with relative luminance `< 0.015` and no visible actors/captions) and unintended frozen visual signatures (`> 1.5s` identical state outside the `hold` beat).
6. **`luminance_flash_rate`**: Checks estimated frame-state luminance jumps (`>= 0.20`) against a threshold of `3` full flashes (`6` transitions) inside a rolling `1.0s` window. This is a parametric screening rule, not pixel-level analysis or independent photosensitivity certification.
7. **`audio_peak_and_caption_overlap`**: Verifies individual stems and combined voiceover-ducked frame envelopes stay `<= -1.0 dBFS`, and rejects overlapping captions on the same anchor or intersecting boxes on the same frame.
8. **`asset_attribution_completeness`**: Confirms every `actor.asset_id` and `audio_cue.asset_id` resolves to an `AssetAttribution` with an allowlisted SPDX license (`CC0-1.0`, `CC-BY-4.0`, `MIT`, `LicenseRef-Video-Motion-Procedural`; legacy `CC0` and `PROCEDURAL` inputs are normalized), non-empty `creator`, and 64-hex `sha256` digest. `digest_basis` says what that digest covers: only `media_bytes` attests file bytes; bundled examples are `illustrative` and procedural catalog entries hash their `procedural_definition`.

Every `QAReport` commits its full check rollup, per-frame findings, and formatted open-license credit line into a canonical SHA-256 `qa_receipt_sha256`.

These checks operate on scene state and declared audio envelopes, not decoded video pixels or audio waveforms. Attribution checks validate license labels and metadata, not ownership or fetched asset bytes. A passing receipt proves these checks ran on this recipe; it does not certify rendered pixels, audio or rights.
