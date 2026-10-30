# Hard rules for the video and motion pack's code

This folder is a noun of the video and motion seed pack: tested code the pack's tool card pins by
digest. The library runs it only in its own CI tests; workers run it under their own permissions.
Read the library's [AGENTS.md](../../../AGENTS.md) first.

1. **Pure frame-addressable evaluation.** Never introduce wall-clock reads (`time`, `datetime`) or mutable global RNG state into `video_motion/timeline.py`. Every `FrameState` and rendered SVG is a pure function of `(recipe, frame_index, aspect)`.
2. **Clean-room, media-free motion learning.** `video_motion/motion.py` extracts beat proportions, easing curves and waypoints from observation traces. Never embed personal media files, local paths or unattributed clips.
3. **License-gated casting and Standard mode only.** `SceneFactory` casts only `CC0-1.0`, `CC-BY-4.0`, `MIT` or `LicenseRef-Video-Motion-Procedural` assets with a creator and a SHA-256 digest, and refuses every `-contributor` model id.
4. **The pack states this code's facts.** A change to anything the pack's nouns state (their `tool_facts`) needs a matching change in `../source.json`; `tests/test_library_pack.py` fails until they agree. Rebuild the library and rerun its checks after any change here, because the tool card pins this folder's digest.
5. **No surface and no authority.** Do not add a server, HTTP or MCP API, website, scheduler, queue, importer or model caller. The `video-motion` command is how a worker runs this code inside a claimed verb.
6. **Checks.** Run `make check` here with `VIDEO_MOTION_REQUIRE_VIDEO=1 VIDEO_MOTION_REQUIRE_TESSERA=1 VIDEO_MOTION_REQUIRE_PACK=1`, then the library's `make check` from its root.
