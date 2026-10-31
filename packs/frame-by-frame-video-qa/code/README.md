# frame-by-frame-video-qa code

Local computer-vision and segmentation checks for `packs/frame-by-frame-video-qa`:

- `frame_qa`: samples every frame of an encoded video, runs nine deterministic visual detectors (cut-off content, cut-off windows, overlaps, small text, transitions, freezes and motion, caption collisions, contrast, layered edges), clusters frame hits into shot-indexed findings, renders annotated evidence images and timelines, draws seeded review samples, and computes reviewer precision with Wilson intervals.
- `frame_qa.ui_masks`: segments rectangular UI controls, buttons, inputs, badges and panels via connected components, includes an optional local Meta SAM (`facebook/sam-vit-base`) mask adapter with offline fallback, and flags caption or callout occlusions over interactive UI regions.

Run `make check` to compile with warnings treated as errors and execute the unit and clip test suites.
