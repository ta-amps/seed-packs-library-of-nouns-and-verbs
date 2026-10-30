# Video pipeline: from nouns to a checked MP4

These worker tools turn a pinned **sequence noun** into H.264/AAC MP4 files at
1920x1080 (16:9) and 1080x1920 (9:16), then check the encoded files. A worker does this
inside a claimed verb: the render and check verbs of the
[video and motion pack](../../README.md), which ships this code, name these tools. Nothing here schedules work, publishes video or calls a model; the
commands below are how a worker runs the tools.

```bash
uv sync --all-groups --extra video        # Playwright + Chromium driver, bundled ffmpeg
uv run playwright install chromium-headless-shell   # once per machine, if not installed
uv run video-motion video demo --out /tmp/video-motion-demo
```

The demo renders [the bundled showcase sequence](../examples/sequences/hackathon-demo.json)
in both cuts, runs every post-encode check and prints a JSON summary. The
[October 29 evidence](evidence/video-demo-plain-name-2026-10-29.json) records one local run.

## The four kinds of thing

| Kind | In this pipeline |
| --- | --- |
| **Nouns** | Scene recipes; the **sequence** (clips, cuts, crossfades, overlays, narration, music bed, caption track); **media** (a recording, image or audio file, with its bytes digest, SPDX license and provenance); **tool cards** (each ffmpeg, Chromium and Playwright binary used); the **video tool** source manifest; render manifests and QA reports produced by the verbs |
| **Verbs** | **Render** (`verb.compile_dag`): sequence to MP4s, sidecar captions, manifests and tool cards. **Check** (`verb.verify_gate`): post-encode QA of those files. Script, storyboard, screen capture and human review are separate verbs done by people or reasoning workers |
| **Surfaces** | None in this pack. The finished video appears on whichever surface publishes it. The `video-motion video` commands are the worker tools' entrypoints, not a surface |
| **Infrastructure** | Tessera: versioned records, bucket objects for media bytes, leases, fencing and receipts |

The pack pins the demo sequence, its media nouns, the reference tool builds and this
code by digest, and defines the render and check verbs. See [the pack](../../README.md).

## Nouns in detail

**Media noun.** One file: kind (`recording`, `image`, `audio`), MIME type, the SHA-256
of its bytes (`blob_sha256`), size, dimensions or duration, SPDX license, creator,
source, provenance (`captured`, `generated` or `licensed`), a plain `disclosure`
sentence, and either the Tessera object holding the bytes or, for generated media,
the generator and parameters that rebuild them exactly.

**Media element.** A media noun placed into a sequence. It pins the noun by
`{store, key, version, value_sha256}` and repeats the bytes digest. It can trim
(`trim_in_s`, `trim_out_s`), crop the source, place the result in a box per output
aspect, set opacity and gain, and mark **keep-out boxes** that captions must not cover.
Every time a worker resolves an element, the tools re-check the value digest, the kind
and the SHA-256 of the actual bytes. Any mismatch stops the render.

**Sequence noun.** Ordered clips: scene recipes or full-frame media. Each clip after
the first enters with a cut or a crossfade. Scenes can carry media overlays. The
sequence also has narration and an optional music bed (ducked under narration), a
caption track, a loudness target (default −14 LUFS) and a true-peak limit (default
−1 dBTP). `plan_sequence()` lays it all out on exact frame numbers.

**Tool card.** Name, version, SPDX license (and where it was read), SHA-256 and size of
the binary that ran, where it came from, and the capabilities it was probed for. Cards
hold no local paths. `video-motion video probe-tools` prints them.

## Render verb

`render_sequence()` refuses to start if pre-render QA fails, a pin or digest does not
match, or ffmpeg lacks a required component. Then it:

1. Rasterizes every scene frame and each caption to PNG in headless Chromium.
2. Places narration, ducks the music bed, and normalizes the mix to the loudness target
   with two linear ffmpeg `loudnorm` passes.
3. Composites clips, crossfades, cuts, overlays and burned-in captions in one ffmpeg
   graph (BT.709, 4:4:4 internally) and encodes H.264 High 4:2:0 + AAC 48 kHz stereo,
   with `title` and a `comment` that says what is synthetic or generated.
4. Writes SRT and WebVTT sidecars and a `render-manifest.json` per aspect: every frame's
   scene-evaluation hash and PNG digest, caption digests, audio digests and loudness
   measurements, the exact commands, tool cards and the tool package's source digests.

Manifests carry no timestamps or local paths. With the same tool builds and fonts,
repeat renders are byte-identical, including across rasterizer process counts.

## Check verb

`check_rendered_video()` first confines the manifest, every render input and every QA
destination to the resolved render directory. It refuses absolute paths, traversal,
protocol paths and symlinks that leave that directory. Before starting FFmpeg, it
verifies the manifest's hashes for the MP4, SRT/WebVTT sidecars, audio mix/master/stem,
copied media, caption PNGs and scene PNGs. Source-file hashes, tool cards and recorded
commands are provenance; the checker never executes the manifest's commands.

It then decodes the MP4 and writes `video-qa.json` with a receipt digest. Every check
must pass:

| Check | What is measured | Pass when |
| --- | --- | --- |
| `container_and_streams` | Codec, pixel format, size, frame rate, audio codec, rate and channels | H.264 yuv420p at the aspect's size and the plan's fps; AAC 48 kHz stereo |
| `duration_and_frames` | Decoded frame count (framemd5) and container duration | Frames equal the plan; duration within one frame plus 50 ms |
| `frame_hash_spot_checks` | 12 frames that show one scene clip | Manifest frame hash equals a fresh `evaluate_frame()`; reference PNG unchanged; decoded-frame SSIM ≥ 0.95 against the reference (with active captions applied), and higher than against a visibly different frame of the same clip |
| `black_frames` | `blackdetect` (runs ≥ 0.5 s) | No black run |
| `frozen_frames` | `freezedetect` (runs ≥ 2 s) | Each freeze lies inside a planned hold (up to 0.75 s of easing tail) |
| `integrated_loudness` | EBU R128 (`ebur128`) | Within 1 LU of the target; true peak at or below the limit |
| `caption_timing_coverage` | `silencedetect` on the narration stem, sidecar SRT | Captions cover ≥ 95% of measured speech, no cue shows without speech, sidecar timings equal the track |
| `synthetic_disclosure` | File metadata (`ffmetadata`) | Title and disclosure comment are exactly what the manifest records |

Pre-render QA (`audit_sequence()`) already ran every-frame scene QA and checked the
caption track: safe zones, minimum size and contrast, reading speed (≤ 20 characters
per second), minimum display time, blink gaps, overlap, scene subjects and media
keep-out boxes.

## 16:9 and layout across cuts

The 16:9 profile keeps the 90% title-safe width (x 96–1824) between a top title overlay
and the bottom player controls. A scene's `stage_aspect` says which safe canvas its
coordinates use. Other aspects map positions between safe canvases and scale sizes to
fit; per-aspect overrides (`dx`, `dy`, `scale_mul`, `opacity_mul`,
`rotation_offset_deg`) then adapt the layout. The demo's diagram runs left to right on
16:9 and top to bottom on 9:16 from one recipe.

## Limits

- The demo's narration, music bed and inset image are generated placeholders. They are
  labeled in metadata and manifests. Replace them with real narration and screen
  captures (as captured media nouns) before publishing.
- Pixels depend on the Chromium build and system fonts. Another machine may produce
  different bytes and still pass QA; byte identity holds for the same builds.
- Keep the render directory stable during checking. Path and digest preflight is not
  an operating-system sandbox against another process concurrently replacing files.
- Spot checks cover frames that show exactly one scene clip. Transitions, overlays and
  recording clips are covered by the stream, black, freeze and loudness checks only.
- Caption coverage is measured against narration loudness, not words. It does not check
  that captions say what the narrator says.
- The library's `video-motion code` CI job runs every test with real renders and the pinned
  Tessera, then the demo. This version has been checked locally; it has not run on GitHub yet.
