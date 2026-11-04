# Example Recipes & Motion Traces

Clean-room, open-licensed (SPDX `LicenseRef-Video-Motion-Procedural`, `CC0-1.0`, `CC-BY-4.0`, `MIT`) scene recipes and AI-generated motion traces exercised by `make demo` and `pytest`. The video and motion seed pack pins each file below by SHA-256. The scenes are illustrative: chart values are examples, not measurements, and attribution digests are placeholders (`digest_basis: illustrative`) that attest no media bytes.

- [01-pov-role-skit.json](01-pov-role-skit.json) -- 16.0s two-character POV role skit demonstrating beat cadence, face keep-out protection, voiceover ducking, and dual-aspect framing.
- [02-kinetic-data-chart.json](02-kinetic-data-chart.json) -- 12.0s animated benchmark chart with progressive `draw_progress` bar/polyline reveal and `4:5` lower-right canvas reclamation.
- [03-algorithm-race-explainer.json](03-algorithm-race-explainer.json) -- 15.0s side-by-side mechanism explainer comparing wall-clock capture drift against deterministic `seek(frame_index)`.
- [sample-motion-trace.json](sample-motion-trace.json) -- 16.0s made-up timestamped motion, cut, and trajectory observation trace consumed by `video-motion learn` to fit a reusable `MotionProfile`.
- [sequences/hackathon-demo.json](sequences/hackathon-demo.json) -- 21.4s video sequence noun (16:9-staged title card, animated nouns → verbs → workers diagram and closing card; crossfade and cut; placeholder narration tone, music bed and inset test card; six captions) rendered by `video-motion video demo`. Regenerate it with `scripts/build_demo_sequence.py`.
- [sequences/hackathon-demo.media.json](sequences/hackathon-demo.media.json) -- its three generated media nouns, each with the generator and parameters that rebuild the exact bytes.
- [sequences/reference-tools.json](sequences/reference-tools.json) -- tool cards (FFmpeg, Chromium, Playwright) recorded by `video-motion video probe-tools` on the reference render worker.
