# Video and motion code

The tested code behind the [video and motion seed pack](../README.md). It is one of the
pack's nouns: the pack's tool card points at this folder and pins every file by digest, and
each of the pack's verbs runs it inside a claimed task. The library runs this code only in its
own CI tests; workers run it under their own permissions. Reading, exporting or importing the
pack runs none of it.

## What it does

- **Seek any frame.** `evaluate_frame(recipe, frame_index, aspect)` is a pure function of the
  recipe, the frame number and the aspect. Forward, backward or shuffled evaluation gives the
  same bytes, and `render_svg_frame()` draws a standalone SVG of any frame.
- **Fit motion.** `learn_motion_profile()` fits six narrative beats and five easing curves to a
  timestamped observation trace, with no media copied; `retarget_motion()` applies the formula
  to a new cast and duration.
- **Compile social formats.** One scene recipe becomes 9:16 (1080x1920), 4:5 (1080x1350) and
  16:9 (1920x1080) SVG frames and contact sheets, SRT and WebVTT captions, an attribution
  manifest and an eight-check every-frame QA report with a receipt digest.
- **Plan, render and check a video.** A pinned sequence of scenes and media, with cuts,
  crossfades, narration, a ducked music bed and captions, is planned onto exact frames and
  checked before rendering. A worker renders it to H.264/AAC MP4 at 1920x1080 and 1080x1920
  with headless Chromium and FFmpeg, records a tool card for every binary it ran, and runs
  eight post-encode checks on the decoded pixels and audio.

## Run the checks

From this folder, with Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```bash
make setup     # the code, its video extra (Playwright, a bundled FFmpeg) and the pinned Tessera
uv run playwright install chromium-headless-shell
VIDEO_MOTION_REQUIRE_VIDEO=1 VIDEO_MOTION_REQUIRE_TESSERA=1 VIDEO_MOTION_REQUIRE_PACK=1 make check
make demo
make video-demo
```

The three flags turn a missing Chromium or FFmpeg, a missing Tessera test dependency or a
missing pack source into failures instead of skips. `tests/test_library_pack.py` recomputes
every fact the pack's `source.json` states about this code and fails on any difference. The
commands a worker uses are `video-motion recipes`, `qa`, `render`, `learn`, `demo` and
`video plan`, `probe-tools`, `render`, `check` and `demo`; `VIDEO_MOTION_FFMPEG` and
`VIDEO_MOTION_CHROMIUM` name specific binaries.

## What is real and what is not

- Real, checked on October 29, 2026: every test passes with real FFmpeg 7.0.2 and Chromium 156
  renders and Tessera at commit `55458514`. The 21.4-second demo passes all eight post-encode
  checks in both cuts, and repeat renders are byte-identical with the same tool builds. See the
  [evidence](docs/evidence/video-demo-plain-name-2026-10-29.json).
- Not yet: no worker has claimed the pack's verbs through Tessera. The demo's narration, music
  and inset image are generated placeholders, labeled as such. Pixels depend on the Chromium
  build and fonts.

## Where things are

| Path | What it holds |
| --- | --- |
| `video_motion/` | The package: schemas, timeline, motion, QA, social formats, media, sequences, tool cards, FFmpeg graphs, video checks and the worker render tools |
| `tests/` | Unit tests, real-render end-to-end tests, the pinned-Tessera contract tests and the pack check |
| `examples/` | Scene recipes, the demo sequence and its generated media, the sample motion trace and reference tool builds, all pinned by the pack |
| `scripts/build_demo_sequence.py` | How the demo sequence and its media nouns were authored; a test checks the files match it |
| `docs/` | The [video pipeline](docs/video-pipeline.md), [every-frame QA](docs/every-frame-qa.md), [motion learning](docs/motion-learning.md) and the demo evidence |
