"""Worker video render and post-encode QA on real pixels and audio (needs the `video` extra).

Skipped when ffmpeg or Playwright's Chromium is unavailable; CI's video job sets
VIDEO_MOTION_REQUIRE_VIDEO=1 so a missing tool fails instead.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from video_motion.media import (
    LocalMediaLibrary,
    MediaAsset,
    MediaElement,
    MediaGenerator,
    MediaLibraryEntry,
    MediaPinError,
    describe_generated,
    generate_media_bytes,
    media_noun_value,
    media_pin,
)
from video_motion.schemas import AspectOverride, Box2D, CaptionCue, SceneRecipe
from video_motion.sequence import VideoSequence

video_worker = pytest.importorskip("video_motion.video_worker")


def _tools_or_skip() -> Path:
    try:
        ffmpeg = video_worker.locate_ffmpeg()
        import playwright.sync_api  # noqa: F401
    except (ImportError, video_worker.VideoToolError) as exc:
        if os.environ.get("VIDEO_MOTION_REQUIRE_VIDEO") == "1":
            raise
        pytest.skip(f"video tools unavailable: {exc}")
    return Path(ffmpeg)


FPS = 12


def _scene(recipe_id: str, label: str, accent: str) -> SceneRecipe:
    tracks = [
        {"property": "x", "keyframes": [{"t_s": 0.0, "value": 960.0, "easing": "linear"}]},
        {"property": "y", "keyframes": [{"t_s": 0.0, "value": 420.0, "easing": "linear"}]},
        {
            "property": "scale",
            "keyframes": [
                {"t_s": 0.0, "value": 1.2, "easing": "ease_out_cubic"},
                {"t_s": 1.5, "value": 1.8, "easing": "step_hold"},
            ],
        },
        {
            "property": "draw_progress",
            "keyframes": [
                {"t_s": 0.0, "value": 0.0, "easing": "linear"},
                {"t_s": 1.5, "value": 1.0, "easing": "step_hold"},
            ],
        },
    ]
    reels = AspectOverride(dx=0.0, dy=-90.0, scale_mul=1.6).model_dump()
    return SceneRecipe.model_validate(
        {
            "recipe_id": recipe_id,
            "title": label,
            "fps": FPS,
            "duration_s": 2.0,
            "stage_aspect": "landscape_16x9",
            "background_hex": "#1b2744",
            "beats": [
                {"phase": "hook", "start_s": 0.0, "end_s": 0.5},
                {"phase": "setup", "start_s": 0.5, "end_s": 1.5},
                {"phase": "hold", "start_s": 1.5, "end_s": 2.0},
            ],
            "actors": [
                {
                    "actor_id": "card",
                    "kind": "card",
                    "label": label,
                    "asset_id": "video-motion-card-primitive",
                    "width": 520.0,
                    "height": 140.0,
                    "fill_hex": "#0f172a",
                    "accent_hex": accent,
                    "tracks": tracks,
                    "aspect_overrides": {"reels_9x16": reels},
                }
            ],
            "attributions": [
                {
                    "asset_id": "video-motion-card-primitive",
                    "license": "LicenseRef-Video-Motion-Procedural",
                    "creator": "video-motion vector studio",
                    "sha256": "1" * 64,
                    "digest_basis": "illustrative",
                }
            ],
        }
    )


def _recording(ffmpeg: Path, folder: Path) -> tuple[MediaAsset, Path]:
    path = folder / "testsrc.mp4"
    subprocess.run(
        [
            str(ffmpeg),
            *("-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi"),
            *("-i", "testsrc2=size=640x360:rate=30:duration=2"),
            *("-c:v", "libx264", "-pix_fmt", "yuv420p", "-fflags", "+bitexact", str(path)),
        ],
        check=True,
    )
    payload = path.read_bytes()
    asset = MediaAsset(
        media_id="test-recording",
        kind="recording",
        mime_type="video/mp4",
        title="Synthetic test-pattern recording",
        blob_sha256=hashlib.sha256(payload).hexdigest(),
        byte_size=len(payload),
        width=640,
        height=360,
        duration_s=2.0,
        fps=30.0,
        license="CC0-1.0",
        creator="Test fixture",
        source_uri="urn:video-motion:test:testsrc2",
        provenance="captured",
        synthetic=True,
        disclosure="Synthetic test pattern captured from ffmpeg testsrc2 for a test.",
    )
    return asset, path


def _generated(media_id: str, generator: MediaGenerator, disclosure: str) -> MediaAsset:
    return describe_generated(
        media_id=media_id,
        title=media_id,
        generator=generator,
        disclosure=disclosure,
        payload=generate_media_bytes(generator),
    )


def _element(asset: MediaAsset, element_id: str, **fields: Any) -> MediaElement:
    return MediaElement.model_validate(
        {
            "element_id": element_id,
            "media": media_pin(asset).model_dump(),
            "blob_sha256": asset.blob_sha256,
            "kind": asset.kind,
            **fields,
        }
    )


def _build(ffmpeg: Path, folder: Path) -> tuple[VideoSequence, LocalMediaLibrary]:
    folder.mkdir(parents=True, exist_ok=True)
    recording, recording_path = _recording(ffmpeg, folder)
    narration = _generated(
        "tone",
        MediaGenerator(
            tool="video_motion.media:tone_bursts_wav",
            params={"duration_s": 4.5, "windows": [[0.4, 1.7], [2.3, 4.0]]},
        ),
        "Placeholder tone.",
    )
    music = _generated(
        "pad", MediaGenerator(tool="video_motion.media:pad_wav", params={"duration_s": 4.5}), "Pad."
    )
    card = _generated(
        "card",
        MediaGenerator(
            tool="video_motion.media:placeholder_card_png", params={"width": 320, "height": 180}
        ),
        "Test card.",
    )
    entries = []
    for asset, payload in (
        (recording, recording_path.read_bytes()),
        *((a, generate_media_bytes(a.generator)) for a in (narration, music, card) if a.generator),
    ):
        relative = f"{asset.media_id}.bin"
        (folder / relative).write_bytes(payload)
        value = media_noun_value(asset)
        entries.append(MediaLibraryEntry(pin=media_pin(asset), value=value, path=relative))
    inset = {
        "landscape_16x9": {"box": Box2D(x=1300.0, y=600.0, width=480.0, height=270.0).model_dump()},
        "reels_9x16": {"box": Box2D(x=180.0, y=900.0, width=480.0, height=270.0).model_dump()},
    }
    sequence = VideoSequence.model_validate(
        {
            "sequence_id": "worker-e2e",
            "title": "Worker e2e",
            "fps": FPS,
            "outputs": ["landscape_16x9", "reels_9x16"],
            "clips": [
                {
                    "kind": "scene",
                    "clip_id": "a",
                    "recipe": _scene("scene-a", "FIRST SCENE", "#38bdf8").model_dump(),
                    "overlays": [
                        _element(
                            recording,
                            "pip",
                            trim_in_s=0.25,
                            duration_s=1.0,
                            start_s=0.5,
                            placements=inset,
                        ).model_dump()
                    ],
                },
                {
                    "kind": "scene",
                    "clip_id": "b",
                    "recipe": _scene("scene-b", "SECOND SCENE", "#34d399").model_dump(),
                    "transition_in": {"kind": "crossfade", "duration_s": 0.5},
                    "overlays": [
                        _element(
                            card, "inset-card", start_s=1.0, duration_s=0.9, placements=inset
                        ).model_dump()
                    ],
                },
                {
                    "kind": "media",
                    "clip_id": "c",
                    "element": _element(
                        recording, "clip", trim_in_s=0.5, duration_s=1.0
                    ).model_dump(),
                },
            ],
            "narration": [_element(narration, "narration", duration_s=4.5).model_dump()],
            "music_bed": _element(music, "music", duration_s=4.5, gain_db=-6.0).model_dump(),
            "captions": [
                CaptionCue(
                    cue_id="c1", text="First caption line.", start_s=0.3, end_s=1.8
                ).model_dump(),
                CaptionCue(
                    cue_id="c2", text="Second caption line.", start_s=2.2, end_s=4.1
                ).model_dump(),
            ],
        }
    )
    return sequence, LocalMediaLibrary(folder, entries)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    ffmpeg = _tools_or_skip()
    root = tmp_path_factory.mktemp("video")
    sequence, library = _build(ffmpeg, root / "library")
    manifests = video_worker.render_sequence(sequence, library, root / "render", processes=1)
    return {
        "ffmpeg": ffmpeg,
        "root": root,
        "sequence": sequence,
        "library": library,
        "manifests": manifests,
    }


def test_render_produces_checked_mp4s_with_tool_cards(rendered: dict[str, Any]) -> None:
    sequence, root = rendered["sequence"], rendered["root"]
    for manifest in rendered["manifests"]:
        assert {card.tool_id for card in manifest.tools} == {"ffmpeg", "chromium", "playwright"}
        ffmpeg = next(card for card in manifest.tools if card.tool_id == "ffmpeg")
        assert ffmpeg.sha256 == hashlib.sha256(Path(rendered["ffmpeg"]).read_bytes()).hexdigest()
        assert not ffmpeg.missing_capabilities and ffmpeg.license_spdx.startswith(("GPL", "LGPL"))
        assert manifest.total_frames == 54
        assert manifest.synthetic_media == ["clip", "inset-card", "music", "narration", "pip"]
        assert "/" + "home" not in json.dumps(manifest.model_dump(mode="json"))
        report = video_worker.check_rendered_video(sequence, root / "render", manifest.aspect)
        failed = {c.check: c.measured for c in report.checks if not c.passed}
        assert report.passed, failed
        assert (root / "render" / manifest.aspect / "video-qa.json").is_file()


def test_repeat_render_is_byte_identical_across_process_counts(
    rendered: dict[str, Any], tmp_path: Path
) -> None:
    again = video_worker.render_sequence(
        rendered["sequence"], rendered["library"], tmp_path / "again", processes=2
    )
    for first, second in zip(rendered["manifests"], again, strict=True):
        assert first.outputs["mp4_sha256"] == second.outputs["mp4_sha256"]
        assert first.model_dump(mode="json") == second.model_dump(mode="json")


def _rewrite(
    rendered: dict[str, Any], tmp_path: Path, video_filter: str | None, silent: bool
) -> Path:
    """Copy the render, re-encode the 16:9 MP4 with a defect, and update its manifest digest."""
    target = tmp_path / "render"
    shutil.copytree(rendered["root"] / "render", target)
    manifest_path = target / "landscape_16x9" / "render-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    mp4 = target / manifest["outputs"]["mp4"]
    broken = target / "broken.mp4"
    args = [str(rendered["ffmpeg"]), "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4)]
    if silent:
        args += [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-shortest",
        ]
    if video_filter:
        args += ["-vf", video_filter]
    args += [
        "-c:v",
        "libx264" if video_filter else "copy",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
    ]
    args += ["-metadata", f"title={manifest['disclosure'] and rendered['sequence'].title}"]
    args += ["-metadata", f"comment={manifest['disclosure']}", str(broken)]
    subprocess.run(args, check=True)
    broken.replace(mp4)
    manifest["outputs"]["mp4_sha256"] = hashlib.sha256(mp4.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return target


def test_qa_catches_black_frames_and_misplaced_pixels(
    rendered: dict[str, Any], tmp_path: Path
) -> None:
    target = _rewrite(
        rendered, tmp_path, "drawbox=enable='between(n,0,29)':color=black:t=fill", False
    )
    report = video_worker.check_rendered_video(rendered["sequence"], target, "landscape_16x9")
    results = {c.check: c.passed for c in report.checks}
    assert not report.passed and not results["black_frames"]
    assert not results["frame_hash_spot_checks"]


def test_qa_catches_silent_audio(rendered: dict[str, Any], tmp_path: Path) -> None:
    target = _rewrite(rendered, tmp_path, None, True)
    report = video_worker.check_rendered_video(rendered["sequence"], target, "landscape_16x9")
    assert not {c.check: c.passed for c in report.checks}["integrated_loudness"]


def test_tampering_and_bad_pins_stop_before_any_claimed_result(
    rendered: dict[str, Any], tmp_path: Path
) -> None:
    target = tmp_path / "render"
    shutil.copytree(rendered["root"] / "render", target)
    mp4 = next(target.glob("*-landscape_16x9.mp4"))
    mp4.write_bytes(mp4.read_bytes() + b"\0")
    with pytest.raises(video_worker.VideoRenderError, match="changed after rendering"):
        video_worker.check_rendered_video(rendered["sequence"], target, "landscape_16x9")
    library: LocalMediaLibrary = rendered["library"]
    entry = next(e for e in library.entries() if "test-recording" in e.path)
    forged = tmp_path / "library"
    shutil.copytree(library.root, forged)
    (forged / entry.path).write_bytes(b"not the pinned recording")
    with pytest.raises(MediaPinError, match="bytes do not match"):
        video_worker.render_sequence(
            rendered["sequence"], LocalMediaLibrary(forged, library.entries()), tmp_path / "x"
        )
    sequence: VideoSequence = rendered["sequence"]
    covering = sequence.captions[0].model_copy(update={"font_px": 20.0})
    bad = sequence.model_copy(update={"captions": [covering, *sequence.captions[1:]]})
    with pytest.raises(video_worker.VideoRenderError, match="pre-render QA failed"):
        video_worker.render_sequence(bad, library, tmp_path / "y")


def test_silent_sequence_renders_and_fails_only_loudness(
    rendered: dict[str, Any], tmp_path: Path
) -> None:
    sequence: VideoSequence = rendered["sequence"]
    silent = VideoSequence.model_validate(
        {
            **sequence.model_dump(mode="json"),
            "outputs": ["landscape_16x9"],
            "narration": [],
            "music_bed": None,
        }
    )
    with pytest.raises(video_worker.VideoRenderError, match="not outputs"):
        video_worker.render_sequence(
            silent, rendered["library"], tmp_path / "bad", aspects=["reels_9x16"]
        )
    (manifest,) = video_worker.render_sequence(silent, rendered["library"], tmp_path / "silent")
    assert manifest.audio["loudnorm_applied"] == {"normalization_type": "skipped_silent_mix"}
    report = video_worker.check_rendered_video(silent, tmp_path / "silent", "landscape_16x9")
    results = {c.check: c.passed for c in report.checks}
    assert results.pop("integrated_loudness") is False
    assert all(results.values()), results
