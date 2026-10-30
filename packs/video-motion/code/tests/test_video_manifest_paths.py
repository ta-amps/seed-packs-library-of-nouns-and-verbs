"""Untrusted render manifests cannot read or write outside the worker's render directory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from video_motion import video_worker
from video_motion.media import media_pin
from video_motion.nouns import value_sha256
from video_motion.sequence import SceneClip, VideoSequence, load_bundled_sequence, plan_sequence

ASPECT = "landscape_16x9"
PATH_FIELDS = [
    ("outputs", "mp4"),
    ("outputs", "srt"),
    ("outputs", "vtt"),
    ("audio", "master"),
    ("audio", "narration_stem"),
    ("captions", 0, "png"),
    ("media", 0, "path"),
]


@pytest.fixture
def bundle(tmp_path: Path) -> tuple[VideoSequence, Path, dict[str, Any]]:
    """A complete, hashed synthetic inventory; no browser, media decoder or network needed."""
    sequence, assets = load_bundled_sequence("hackathon-demo")
    plan = plan_sequence(sequence)
    root = tmp_path / "render"
    root.mkdir()

    def put(relative: str) -> str:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = f"synthetic render file {relative}".encode()
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    outputs: dict[str, Any] = {}
    for kind in ("mp4", "srt", "vtt"):
        relative = f"{ASPECT}/example.{kind}"
        outputs[kind] = relative
        outputs[f"{kind}_sha256"] = put(relative)
    manifest = video_worker.RenderManifest(
        sequence_id=sequence.sequence_id,
        sequence_sha256=plan.sequence_sha256,
        plan_sha256=value_sha256(plan.model_dump(mode="json")),
        aspect=ASPECT,
        width=1920,
        height=1080,
        fps=plan.fps,
        total_frames=plan.total_frames,
        tool_version="0.1.0",
        tool_source_files={},
        tools=[],
        media=[
            video_worker.RenderedMedia(
                element_id=asset.media_id,
                pin=media_pin(asset),
                blob_sha256=put(f"media/{asset.media_id}.wav"),
                path=f"media/{asset.media_id}.wav",
                kind=asset.kind,
                provenance=asset.provenance,
                synthetic=asset.synthetic,
                license=asset.license,
                disclosure=asset.disclosure,
            )
            for asset in assets
        ],
        scene_frames={
            clip.clip_id: [
                [local, "0" * 64, put(f"{ASPECT}/frames/{clip.clip_id}/{local:05d}.png")]
                for local in range(clip.recipe.total_frames)
            ]
            for clip in sequence.clips
            if isinstance(clip, SceneClip)
        },
        captions=[
            {
                "cue_id": cue.cue_id,
                "png": f"{ASPECT}/captions/{cue.cue_id}.png",
                "png_sha256": put(f"{ASPECT}/captions/{cue.cue_id}.png"),
            }
            for cue in sequence.captions
        ],
        audio={
            "mix_sha256": put("audio/mix.wav"),
            "master": "audio/master.wav",
            "master_sha256": put("audio/master.wav"),
            "narration_stem": "audio/narration.wav",
            "narration_stem_sha256": put("audio/narration.wav"),
        },
        commands={},
        outputs=outputs,
        disclosure="Synthetic fixture, not playable media",
        prerender_qa_receipt_sha256="0" * 64,
    ).model_dump(mode="json")
    return sequence, root, manifest


def _save(root: Path, manifest: dict[str, Any]) -> None:
    (root / ASPECT / "render-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _field(manifest: dict[str, Any], field: tuple[str | int, ...]) -> tuple[Any, str | int]:
    node: Any = manifest
    for key in field[:-1]:
        node = node[key]
    return node, field[-1]


def _no_read_or_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("unsafe inventory reached asset hashing or external tool selection")

    monkeypatch.setattr(video_worker, "file_sha256", fail)
    monkeypatch.setattr(video_worker, "locate_ffmpeg", fail)


@pytest.mark.parametrize("field", PATH_FIELDS)
def test_each_manifest_path_rejects_traversal_before_asset_reads(
    bundle: tuple[VideoSequence, Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    field: tuple[str | int, ...],
) -> None:
    sequence, root, manifest = bundle
    outside = root.parent / "outside.txt"
    outside.write_text("synthetic outside data", encoding="utf-8")
    node, key = _field(manifest, field)
    node[key] = "../outside.txt"
    _save(root, manifest)
    _no_read_or_tool(monkeypatch)
    with pytest.raises(video_worker.VideoRenderError, match="relative path inside"):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=0)
    assert not (root / ASPECT / "video-measurements.json").exists()
    assert outside.read_text() == "synthetic outside data"


@pytest.mark.parametrize(
    "relative",
    ["absolute", "https://invalid.example/file", "file:outside.txt", "C:/file", "..\\file"],
)
def test_absolute_and_protocol_paths_are_rejected(
    bundle: tuple[VideoSequence, Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
) -> None:
    sequence, root, manifest = bundle
    manifest["outputs"]["srt"] = str(root / "captions.srt") if relative == "absolute" else relative
    _save(root, manifest)
    _no_read_or_tool(monkeypatch)
    with pytest.raises(video_worker.VideoRenderError, match="relative path inside"):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=0)


def _inputs(manifest: dict[str, Any]) -> list[str]:
    paths = []
    for field in PATH_FIELDS:
        node, key = _field(manifest, field)
        paths.append(node[key])
    clip_id = next(iter(manifest["scene_frames"]))
    return [*paths, "audio/mix.wav", f"{ASPECT}/frames/{clip_id}/00000.png"]


@pytest.mark.parametrize("input_index", range(len(PATH_FIELDS) + 2))
def test_every_input_kind_rejects_outside_symlinks_even_with_matching_digest(
    bundle: tuple[VideoSequence, Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    input_index: int,
) -> None:
    sequence, root, manifest = bundle
    path = root / _inputs(manifest)[input_index]
    outside = root.parent / "outside.bin"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    _save(root, manifest)
    _no_read_or_tool(monkeypatch)
    with pytest.raises(video_worker.VideoRenderError, match="escapes the render directory"):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=0)


def test_manifest_itself_cannot_be_an_outside_symlink(
    bundle: tuple[VideoSequence, Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    sequence, root, manifest = bundle
    outside = root.parent / "outside.json"
    outside.write_text(json.dumps(manifest), encoding="utf-8")
    (root / ASPECT / "render-manifest.json").symlink_to(outside)
    _no_read_or_tool(monkeypatch)
    with pytest.raises(video_worker.VideoRenderError, match="escapes the render directory"):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=0)


def test_symlinked_frame_directory_is_confined_before_reading_any_asset(
    bundle: tuple[VideoSequence, Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    sequence, root, manifest = bundle
    frames = root / ASPECT / "frames"
    outside = root.parent / "outside-frames"
    frames.rename(outside)
    frames.symlink_to(outside, target_is_directory=True)
    _save(root, manifest)
    _no_read_or_tool(monkeypatch)
    with pytest.raises(video_worker.VideoRenderError, match="escapes the render directory"):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=0)


@pytest.mark.parametrize(
    "destination", ["qa-decoded", "video-qa.json", "video-measurements.json", "spot"]
)
def test_qa_destinations_cannot_escape_before_any_asset_read(
    bundle: tuple[VideoSequence, Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    destination: str,
) -> None:
    sequence, root, manifest = bundle
    _save(root, manifest)
    outside = root.parent / "outside"
    outside.mkdir()
    if destination == "spot":
        frame = video_worker._spot_frames(plan_sequence(sequence), sequence, 1)[0]
        path = root / ASPECT / "qa-decoded" / f"{frame:05d}.png"
        path.parent.mkdir()
        path.symlink_to(outside / "spot.png")
    else:
        (root / ASPECT / destination).symlink_to(outside)
    _no_read_or_tool(monkeypatch)
    with pytest.raises(video_worker.VideoRenderError, match="escapes the render directory"):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=1)
    assert not list(outside.iterdir())


@pytest.mark.parametrize("input_index", range(len(PATH_FIELDS) + 2))
def test_every_input_kind_must_match_its_declared_digest_before_tools(
    bundle: tuple[VideoSequence, Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    input_index: int,
) -> None:
    sequence, root, manifest = bundle
    path = root / _inputs(manifest)[input_index]
    path.write_bytes(path.read_bytes() + b"changed")
    _save(root, manifest)

    def fail(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("changed input reached external tool selection")

    monkeypatch.setattr(video_worker, "locate_ffmpeg", fail)
    with pytest.raises(video_worker.VideoRenderError, match="changed after rendering"):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=0)


@pytest.mark.parametrize("digest", [None, "", "f" * 63, "not-a-digest"])
def test_missing_or_invalid_sidecar_digest_stops_before_reading_assets(
    bundle: tuple[VideoSequence, Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, digest: Any
) -> None:
    sequence, root, manifest = bundle
    manifest["outputs"]["srt_sha256"] = digest
    _save(root, manifest)
    _no_read_or_tool(monkeypatch)
    with pytest.raises(video_worker.VideoRenderError, match="valid SHA-256"):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=0)


def test_confined_relative_paths_and_internal_symlinks_reach_tool_selection(
    bundle: tuple[VideoSequence, Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    sequence, root, manifest = bundle
    original = root / manifest["outputs"]["srt"]
    target = root / "relocated.srt"
    original.rename(target)
    original.symlink_to(target)
    _save(root, manifest)

    class PreflightPassed(Exception):
        pass

    def stop(*_args: Any, **_kwargs: Any) -> Any:
        raise PreflightPassed

    monkeypatch.setattr(video_worker, "locate_ffmpeg", stop)
    with pytest.raises(PreflightPassed):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=0)


@pytest.mark.parametrize("field", ["aspect", "plan_sha256"])
def test_manifest_must_match_the_requested_aspect_and_pinned_plan(
    bundle: tuple[VideoSequence, Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    sequence, root, manifest = bundle
    manifest[field] = "reels_9x16" if field == "aspect" else "0" * 64
    _save(root, manifest)
    _no_read_or_tool(monkeypatch)
    with pytest.raises(video_worker.VideoRenderError, match="different sequence version"):
        video_worker.check_rendered_video(sequence, root, ASPECT, spot_count=0)
