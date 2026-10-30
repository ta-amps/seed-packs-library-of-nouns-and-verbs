"""Worker-only video tools: probe external tools, rasterize frames, encode, and check the result.

This module runs inside a claimed render or check verb. It starts subprocesses (ffmpeg, and
Chromium through Playwright) and imports the optional `video` extra lazily, so importing `video_motion`
never needs them. It does not schedule work, read credentials, call models or publish anything:
it turns one pinned sequence plus locally resolved media into files and manifests in `out_dir`.

Outputs are deterministic for the same tool builds and fonts: manifests carry no timestamps or
local paths, and repeat renders produce byte-identical MP4s.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from video_motion import __version__
from video_motion.errors import VideoMotionError
from video_motion.ffmpeg_graph import (
    BASE,
    ComposeInputs,
    compose_command,
    detect_command,
    framemd5_command,
    loudness_apply_command,
    loudness_measure_command,
    metadata_command,
    mix_command,
    probe_command,
    silence_command,
    spot_frame_command,
)
from video_motion.media import MIME_SUFFIX, LocalMediaLibrary, MediaAsset, file_sha256
from video_motion.nouns import NounPin, tool_source_manifest, value_sha256
from video_motion.schemas import ASPECT_PROFILES, AspectId, FrameState
from video_motion.sequence import (
    SceneClip,
    SequencePlan,
    VideoSequence,
    audit_sequence,
    disclosure_text,
    plan_sequence,
    sequence_srt,
    sequence_webvtt,
    static_windows,
)
from video_motion.timeline import evaluate_frame, render_caption_overlay_svg, render_svg_frame
from video_motion.toolcards import (
    ExternalToolCard,
    chromium_license,
    ffmpeg_capabilities,
    ffmpeg_license,
    parse_ffmpeg_components,
    parse_ffmpeg_version,
)
from video_motion.video_checks import (
    BLACK_MIN_S,
    FREEZE_MIN_S,
    SpotCheck,
    VideoMeasurements,
    VideoQAReport,
    count_framemd5,
    evaluate_video,
    parse_black_segments,
    parse_ebur128,
    parse_ffmetadata,
    parse_freeze_segments,
    parse_loudnorm_json,
    parse_silence_segments,
    parse_ssim,
    parse_stream_info,
)

VIDEO_TOOL_ENTRYPOINT = "video_motion.video_worker:render_sequence"
CHROMIUM_ARGS = ["--force-color-profile=srgb", "--disable-gpu"]
_HTML = "<!doctype html><html><body style='margin:0;background:transparent'>{svg}</body></html>"


class VideoToolError(VideoMotionError):
    """Raised when a required external tool or capability is unavailable."""

    def __init__(self, detail: str) -> None:
        super().__init__(503, "video_tool_unavailable", "Video Tool Unavailable", detail)


class VideoRenderError(VideoMotionError):
    """Raised when pre-render QA, a tool run or an output check fails during rendering."""

    def __init__(self, detail: str) -> None:
        super().__init__(422, "video_render_failed", "Video Render Failed", detail)


# ---------------------------------------------------------------------------------------------
# External tools
# ---------------------------------------------------------------------------------------------


def locate_ffmpeg(explicit: str | os.PathLike[str] | None = None) -> Path:
    """ffmpeg to use: an explicit path, $VIDEO_MOTION_FFMPEG, the imageio-ffmpeg build, or PATH."""
    candidates: list[str] = [str(explicit)] if explicit else []
    if env := os.environ.get("VIDEO_MOTION_FFMPEG"):
        candidates.append(env)
    try:
        import imageio_ffmpeg

        candidates.append(str(imageio_ffmpeg.get_ffmpeg_exe()))
    except (ImportError, RuntimeError):
        pass
    if found := shutil.which("ffmpeg"):
        candidates.append(found)
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file() and os.access(path, os.X_OK):
            return path.resolve()
    raise VideoToolError("No ffmpeg found; install the `video` extra or set VIDEO_MOTION_FFMPEG.")


def _run(
    binary: Path, args: Sequence[str], cwd: Path | None = None, timeout: float = 1800.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _distribution_of(path: Path, banner: str) -> str:
    if "imageio_ffmpeg" in path.parts:
        try:
            version = importlib.metadata.version("imageio-ffmpeg")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        return f"imageio-ffmpeg {version} wheel binary ({banner})"
    return f"ffmpeg binary on the worker ({banner})"


def probe_ffmpeg(ffmpeg: Path) -> ExternalToolCard:
    """Card for the ffmpeg binary: version, SPDX license, SHA-256 and required capabilities."""
    version_text = _run(ffmpeg, ["-version"]).stdout
    version, flags = parse_ffmpeg_version(version_text)
    license_spdx, license_basis = ffmpeg_license(_run(ffmpeg, ["-hide_banner", "-L"]).stdout, flags)
    components = {
        kind: parse_ffmpeg_components(_run(ffmpeg, ["-hide_banner", f"-{kind}"]).stdout, kind)
        for kind in ("encoders", "muxers", "filters")
    }
    have, missing = ffmpeg_capabilities(
        components["encoders"], components["muxers"], components["filters"]
    )
    banner = version_text.splitlines()[0].split("Copyright")[0].strip() if version_text else ""
    return ExternalToolCard(
        tool_id="ffmpeg",
        name="FFmpeg",
        version=version,
        license_spdx=license_spdx,
        license_basis=license_basis,
        sha256=file_sha256(ffmpeg),
        byte_size=ffmpeg.stat().st_size,
        distribution=_distribution_of(ffmpeg, banner),
        capabilities=have,
        missing_capabilities=missing,
        build_configuration=flags,
    )


def probe_playwright() -> ExternalToolCard:
    """Card for the Playwright driver that controls Chromium."""
    try:
        import playwright
    except ImportError as exc:
        raise VideoToolError("Playwright is not installed; install the `video` extra.") from exc
    package = Path(playwright.__file__).resolve().parent
    driver = package / "driver" / "node"
    if not driver.is_file():
        raise VideoToolError("The Playwright driver binary is missing.")
    version = importlib.metadata.version("playwright")
    meta = importlib.metadata.metadata("playwright")
    declared = meta.get("License-Expression") or meta.get("License") or ""
    license_spdx = "Apache-2.0" if "Apache" in declared else "LicenseRef-Playwright-unknown"
    return ExternalToolCard(
        tool_id="playwright",
        name="Playwright for Python",
        version=version,
        license_spdx=license_spdx,
        license_basis="installed package metadata",
        sha256=file_sha256(driver),
        byte_size=driver.stat().st_size,
        distribution=f"playwright {version} wheel (driver/node is the hashed binary)",
        capabilities=["chromium.launch", "page.set_content", "page.screenshot:png"],
    )


def _headless_shell_for(full_chromium: Path) -> Path | None:
    revision_dir = full_chromium.parents[1]
    revision = revision_dir.name.rpartition("-")[2]
    shell_root = revision_dir.parent / f"chromium_headless_shell-{revision}"
    matches = sorted(shell_root.glob("chrome-headless-shell-*/chrome-headless-shell"))
    return matches[0] if matches else None


def _chromium_card(binary: Path, version: str) -> ExternalToolCard:
    license_files = sorted(p for p in binary.parent.glob("LICENSE*") if p.is_file())
    text = license_files[0].read_text(encoding="utf-8", errors="replace") if license_files else ""
    license_spdx, license_basis = chromium_license(text)
    try:
        playwright_version = importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        playwright_version = "unknown"
    return ExternalToolCard(
        tool_id="chromium",
        name=binary.name,
        version=version,
        license_spdx=license_spdx,
        license_basis=license_basis,
        sha256=file_sha256(binary),
        byte_size=binary.stat().st_size,
        distribution=f"Playwright {playwright_version} browser build {binary.parents[1].name}",
        capabilities=["headless SVG rendering", "PNG screenshots with alpha"],
        build_configuration=CHROMIUM_ARGS,
    )


class Rasterizer:
    """Headless Chromium (via Playwright) that turns SVG documents into PNG bytes."""

    def __init__(self, chromium: str | os.PathLike[str] | None = None) -> None:
        self._explicit = chromium or os.environ.get("VIDEO_MOTION_CHROMIUM")
        self._pages: dict[tuple[int, int], Any] = {}

    def __enter__(self) -> Rasterizer:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise VideoToolError("Playwright is not installed; install the `video` extra.") from exc
        self._manager = sync_playwright().start()
        if self._explicit:
            binary = Path(self._explicit).resolve()
        else:
            full = Path(self._manager.chromium.executable_path)
            binary = _headless_shell_for(full) or full
        if not binary.is_file():
            self._manager.stop()
            raise VideoToolError("No Chromium build found; run `playwright install chromium`.")
        self.binary = binary
        self._browser = self._manager.chromium.launch(
            executable_path=str(binary), args=CHROMIUM_ARGS
        )
        self.card = _chromium_card(binary, self._browser.version)
        return self

    def __exit__(self, *_exc: object) -> None:
        self._browser.close()
        self._manager.stop()

    def png(self, svg: str, width: int, height: int, *, transparent: bool = False) -> bytes:
        page = self._pages.get((width, height))
        if page is None:
            # Frames are data: render them with scripting disabled.
            page = self._browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
                java_script_enabled=False,
            )
            self._pages[(width, height)] = page
        page.set_content(_HTML.format(svg=svg))
        data: bytes = page.screenshot(
            type="png",
            omit_background=transparent,
            clip={"x": 0, "y": 0, "width": width, "height": height},
        )
        return data


def _raster_chunk(job: tuple[str | None, list[tuple[str, str, int, int, bool]]]) -> list[str]:
    """Rasterize one chunk of (svg, output path, width, height, transparent) in a fresh process."""
    chromium, items = job
    digests = []
    with Rasterizer(chromium) as raster:
        for svg, out, width, height, transparent in items:
            data = raster.png(svg, width, height, transparent=transparent)
            Path(out).write_bytes(data)
            digests.append(hashlib.sha256(data).hexdigest())
    return digests


def rasterize_all(
    items: list[tuple[str, Path, int, int, bool]],
    *,
    chromium: str | None,
    processes: int,
) -> list[str]:
    """Rasterize SVGs to PNG files, optionally across processes; returns PNG SHA-256s in order."""
    jobs = [(svg, str(out), w, h, t) for svg, out, w, h, t in items]
    if processes <= 1 or len(jobs) < 2 * processes:
        return _raster_chunk((chromium, jobs))
    size = -(-len(jobs) // processes)
    chunks = [(chromium, jobs[i : i + size]) for i in range(0, len(jobs), size)]
    # Spawn, not fork: the parent may hold Playwright threads, and forking those can deadlock.
    with ProcessPoolExecutor(max_workers=processes, mp_context=get_context("spawn")) as pool:
        return [digest for chunk in pool.map(_raster_chunk, chunks) for digest in chunk]


# ---------------------------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------------------------


class RenderedMedia(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    element_id: str
    pin: NounPin
    blob_sha256: str
    path: str
    kind: str
    provenance: str
    synthetic: bool
    license: str
    disclosure: str


class RenderManifest(BaseModel):
    """Everything a checker needs to verify one rendered aspect, without local paths or clocks."""

    model_config = ConfigDict(extra="forbid", strict=True)

    format: Literal["video_motion.video-render.v1"] = "video_motion.video-render.v1"
    sequence_id: str
    sequence_sha256: str
    plan_sha256: str
    aspect: AspectId
    width: int
    height: int
    fps: int
    total_frames: int
    tool_version: str
    tool_source_files: dict[str, str]
    tools: list[ExternalToolCard]
    media: list[RenderedMedia]
    scene_frames: dict[str, list[list[Any]]]
    captions: list[dict[str, Any]]
    audio: dict[str, Any]
    commands: dict[str, list[str]]
    outputs: dict[str, Any]
    disclosure: str
    synthetic_visuals: bool = True
    synthetic_media: list[str] = Field(default_factory=list)
    prerender_qa_receipt_sha256: str


def _check(proc: subprocess.CompletedProcess[str], step: str) -> subprocess.CompletedProcess[str]:
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise VideoRenderError(f"{step} failed (exit {proc.returncode}): {tail}")
    return proc


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tool_cards(ffmpeg: Path, raster: Rasterizer) -> list[ExternalToolCard]:
    cards = [probe_ffmpeg(ffmpeg), raster.card, probe_playwright()]
    missing = cards[0].missing_capabilities
    if missing:
        raise VideoToolError(f"ffmpeg lacks required components: {', '.join(missing)}")
    return cards


def render_sequence(
    sequence: VideoSequence,
    library: LocalMediaLibrary,
    out_dir: Path,
    *,
    aspects: Sequence[AspectId] | None = None,
    ffmpeg: str | None = None,
    chromium: str | None = None,
    processes: int = 1,
    crf: int = 18,
) -> list[RenderManifest]:
    """Render a pinned sequence to H.264/AAC MP4 per aspect, with sidecars and manifests.

    Fails before rendering if pre-render QA fails, a media pin or digest does not match, or a
    required tool capability is missing. Writes `<aspect>/render-manifest.json` per aspect.
    """
    # Re-validate: a model_copy(update=...) can skip validators, and ids become file names.
    sequence = VideoSequence.model_validate(sequence.model_dump(mode="json"))
    targets = list(aspects or sequence.outputs)
    extra = [aspect for aspect in targets if aspect not in sequence.outputs]
    if extra:
        raise VideoRenderError(f"{extra} are not outputs of sequence {sequence.sequence_id!r}")
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = plan_sequence(sequence)
    prerender = {aspect: audit_sequence(sequence, aspect) for aspect in targets}
    failed = [aspect for aspect, report in prerender.items() if not report.passed]
    if failed:
        details = [f.detail for a in failed for f in prerender[a].findings if f.severity == "error"]
        raise VideoRenderError(f"pre-render QA failed for {failed}: {details[:5]}")

    media_dir = out_dir / "media"
    media_dir.mkdir(exist_ok=True)
    resolved: dict[str, tuple[MediaAsset, str]] = {}
    rendered_media = []
    for element in sequence.media_elements():
        asset, source = library.resolve(element)
        relative = f"media/{asset.blob_sha256}{MIME_SUFFIX[asset.mime_type]}"
        target = out_dir / relative
        if not target.is_file() or file_sha256(target) != asset.blob_sha256:
            shutil.copyfile(source, target)
        resolved[element.element_id] = (asset, relative)
        rendered_media.append(
            RenderedMedia(
                element_id=element.element_id,
                pin=element.media,
                blob_sha256=asset.blob_sha256,
                path=relative,
                kind=asset.kind,
                provenance=asset.provenance,
                synthetic=asset.synthetic,
                license=asset.license,
                disclosure=asset.disclosure,
            )
        )
    media_files = {element_id: path for element_id, (_, path) in resolved.items()}
    disclosure = disclosure_text(sequence, [asset for asset, _ in resolved.values()])
    ffmpeg_path = locate_ffmpeg(ffmpeg)

    audio_dir = out_dir / "audio"
    audio_dir.mkdir(exist_ok=True)
    mix_args = mix_command(sequence, plan, media_files, "audio/mix.wav", "audio/narration.wav")
    _check(_run(ffmpeg_path, mix_args, cwd=out_dir), "audio mix")
    measure_args = loudness_measure_command(
        "audio/mix.wav", sequence.loudness_target_lufs, sequence.true_peak_limit_dbtp - 0.5
    )
    measured = parse_loudnorm_json(
        _check(_run(ffmpeg_path, measure_args, cwd=out_dir), "loudness measurement").stderr
    )
    if "inf" in measured.get("input_i", "").lower():
        # A silent mix has no loudness to normalize; keep it silent and let QA report it.
        apply_args = [*BASE, "-loglevel", "error", "-i", "audio/mix.wav"]
        apply_args += ["-c:a", "pcm_s16le", "-ar", "48000", "audio/master.wav"]
        _check(_run(ffmpeg_path, apply_args, cwd=out_dir), "silent master")
        applied = {"normalization_type": "skipped_silent_mix"}
    else:
        apply_args = loudness_apply_command(
            "audio/mix.wav",
            "audio/master.wav",
            measured,
            sequence.loudness_target_lufs,
            sequence.true_peak_limit_dbtp - 0.5,
        )
        applied = parse_loudnorm_json(
            _check(_run(ffmpeg_path, apply_args, cwd=out_dir), "loudness normalization").stderr
        )
    audio = {
        "mix_sha256": file_sha256(audio_dir / "mix.wav"),
        "narration_stem": "audio/narration.wav",
        "narration_stem_sha256": file_sha256(audio_dir / "narration.wav"),
        "master": "audio/master.wav",
        "master_sha256": file_sha256(audio_dir / "master.wav"),
        "loudnorm_measured": measured,
        "loudnorm_applied": applied,
    }

    manifests = []
    clips = {clip.clip_id: clip for clip in sequence.clips}
    with Rasterizer(chromium) as raster:
        cards = tool_cards(ffmpeg_path, raster)
        for aspect in targets:
            profile = ASPECT_PROFILES[aspect]
            aspect_dir = out_dir / aspect
            jobs: list[tuple[str, Path, int, int, bool]] = []
            scene_frames: dict[str, list[list[Any]]] = {}
            hashes: dict[str, list[str]] = {}
            for clip_plan in plan.clips:
                clip = clips[clip_plan.clip_id]
                if not isinstance(clip, SceneClip):
                    continue
                frame_dir = aspect_dir / "frames" / clip.clip_id
                frame_dir.mkdir(parents=True, exist_ok=True)
                hashes[clip.clip_id] = []
                for local in range(clip.recipe.total_frames):
                    state = evaluate_frame(clip.recipe, local, aspect=aspect)
                    hashes[clip.clip_id].append(state.frame_hash_sha256)
                    jobs.append(
                        (
                            render_svg_frame(state),
                            frame_dir / f"{local:05d}.png",
                            profile.width,
                            profile.height,
                            False,
                        )
                    )
            caption_dir = aspect_dir / "captions"
            caption_dir.mkdir(parents=True, exist_ok=True)
            cues = {cue.cue_id: cue for cue in sequence.captions}
            for window in plan.captions:
                jobs.append(
                    (
                        render_caption_overlay_svg(cues[window.ref_id], aspect),
                        caption_dir / f"{window.ref_id}.png",
                        profile.width,
                        profile.height,
                        True,
                    )
                )
            if processes <= 1:
                png_digests = []
                for svg, path, width, height, transparent in jobs:
                    data = raster.png(svg, width, height, transparent=transparent)
                    path.write_bytes(data)
                    png_digests.append(hashlib.sha256(data).hexdigest())
            else:
                png_digests = rasterize_all(jobs, chromium=str(raster.binary), processes=processes)
            cursor = 0
            for clip_id, frame_hashes in hashes.items():
                scene_frames[clip_id] = [
                    [local, frame_hash, png_digests[cursor + local]]
                    for local, frame_hash in enumerate(frame_hashes)
                ]
                cursor += len(frame_hashes)
            caption_rows: list[dict[str, Any]] = []
            for offset, window in enumerate(plan.captions):
                caption_rows.append(
                    {
                        "cue_id": window.ref_id,
                        "png": f"{aspect}/captions/{window.ref_id}.png",
                        "png_sha256": png_digests[cursor + offset],
                        "start_frame": window.start_frame,
                        "end_frame": window.end_frame,
                    }
                )
            inputs = ComposeInputs(
                scene_frames={clip_id: f"{aspect}/frames/{clip_id}/%05d.png" for clip_id in hashes},
                media_files=media_files,
                caption_images={row["cue_id"]: row["png"] for row in caption_rows},
                master_audio="audio/master.wav",
            )
            mp4 = f"{sequence.sequence_id}-{aspect}.mp4"
            compose_args = compose_command(
                sequence,
                plan,
                aspect,
                inputs,
                mp4,
                title=sequence.title,
                comment=disclosure,
                crf=crf,
            )
            _check(_run(ffmpeg_path, compose_args, cwd=out_dir), f"{aspect} compose and encode")
            srt_path = aspect_dir / "captions.srt"
            vtt_path = aspect_dir / "captions.vtt"
            srt_path.write_text(sequence_srt(sequence), encoding="utf-8")
            vtt_path.write_text(sequence_webvtt(sequence, aspect), encoding="utf-8")
            manifest = RenderManifest(
                sequence_id=sequence.sequence_id,
                sequence_sha256=plan.sequence_sha256,
                plan_sha256=value_sha256(plan.model_dump(mode="json")),
                aspect=aspect,
                width=profile.width,
                height=profile.height,
                fps=plan.fps,
                total_frames=plan.total_frames,
                tool_version=__version__,
                tool_source_files=tool_source_manifest("video_motion.video_worker"),
                tools=cards,
                media=rendered_media,
                scene_frames=scene_frames,
                captions=caption_rows,
                audio=audio,
                commands={
                    "mix": mix_args,
                    "loudness_measure": measure_args,
                    "loudness_apply": apply_args,
                    "compose": compose_args,
                },
                outputs={
                    "mp4": mp4,
                    "mp4_sha256": file_sha256(out_dir / mp4),
                    "mp4_bytes": (out_dir / mp4).stat().st_size,
                    "srt": f"{aspect}/captions.srt",
                    "srt_sha256": file_sha256(srt_path),
                    "vtt": f"{aspect}/captions.vtt",
                    "vtt_sha256": file_sha256(vtt_path),
                },
                disclosure=disclosure,
                synthetic_media=sorted(m.element_id for m in rendered_media if m.synthetic),
                prerender_qa_receipt_sha256=prerender[aspect].receipt_sha256,
            )
            _write_json(aspect_dir / "render-manifest.json", manifest.model_dump(mode="json"))
            manifests.append(manifest)
    return manifests


# ---------------------------------------------------------------------------------------------
# Post-encode QA
# ---------------------------------------------------------------------------------------------


def _spot_frames(plan: SequencePlan, sequence: VideoSequence, count: int) -> list[int]:
    """Evenly spread output frames that show exactly one scene clip and no media overlay."""
    scene_ids = {c.clip_id for c in sequence.clips if isinstance(c, SceneClip)}
    eligible = [
        frame
        for frame in range(plan.total_frames)
        if len(plan.sources(frame)) == 1
        and plan.sources(frame)[0][0] in scene_ids
        and not plan.active_overlays(frame)
    ]
    if not eligible:
        return []
    picks = count if len(eligible) >= count else len(eligible)
    if picks == 1:
        return [eligible[len(eligible) // 2]]
    return sorted({eligible[round(i * (len(eligible) - 1) / (picks - 1))] for i in range(picks)})


def _visibly_different(a: FrameState, b: FrameState) -> bool:
    """True when some actor moved, resized, faded or progressed enough to see in a still frame."""
    others = {actor.actor_id: actor for actor in b.actors}
    for actor in a.actors:
        other = others.get(actor.actor_id)
        if other is None:
            return True
        if (
            abs(actor.x - other.x) >= 6.0
            or abs(actor.y - other.y) >= 6.0
            or abs(actor.scale - other.scale) >= 0.03
            or abs(actor.rotation_deg - other.rotation_deg) >= 3.0
            or abs(actor.opacity - other.opacity) >= 0.15
            or abs(actor.draw_progress - other.draw_progress) >= 0.15
        ):
            return True
    return [c.cue_id for c in a.captions] != [c.cue_id for c in b.captions]


def _neighbor(clip: SceneClip, local: int, aspect: AspectId) -> int | None:
    """Nearest frame of the same clip that is visibly different, as a negative control."""
    state = evaluate_frame(clip.recipe, local, aspect=aspect)
    total = clip.recipe.total_frames
    for distance in range(1, total):
        for candidate in (local - distance, local + distance):
            if 0 <= candidate < total and _visibly_different(
                state, evaluate_frame(clip.recipe, candidate, aspect=aspect)
            ):
                return candidate
    return None


def _render_path(root: Path, relative: object, label: str, *, required: bool = True) -> Path:
    """Resolve a portable render-relative path, never a protocol or an outside symlink."""
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or ":" in relative
        or "\0" in relative
        or Path(relative).is_absolute()
        or ".." in Path(relative).parts
        or relative == "."
    ):
        raise VideoRenderError(f"{label} must be a relative path inside the render directory")
    try:
        path = (root / relative).resolve(strict=required)
        if not path.is_relative_to(root) or path == root:
            raise VideoRenderError(f"{label} escapes the render directory")
        if required and not path.is_file():
            raise VideoRenderError(f"{label} must be a rendered file")
    except (OSError, RuntimeError, ValueError) as exc:
        raise VideoRenderError(f"{label} is not an accessible render path") from exc
    return path


def _checked_render_files(
    root: Path,
    manifest: RenderManifest,
    sequence: VideoSequence,
    aspect: AspectId,
    output_paths: Sequence[str],
) -> dict[str, Path]:
    """Confine every input/output first, then verify all declared render-file digests.

    Source-file hashes, tool cards and recorded command arguments are provenance, not paths to
    open or commands to execute. Only this explicit render-file inventory is consumed by QA.
    """
    refs: list[tuple[object, object, str]] = [
        (manifest.outputs.get(kind), manifest.outputs.get(f"{kind}_sha256"), kind.upper())
        for kind in ("mp4", "srt", "vtt")
    ]
    refs += [
        ("audio/mix.wav", manifest.audio.get("mix_sha256"), "audio mix"),
        (manifest.audio.get("master"), manifest.audio.get("master_sha256"), "audio master"),
        (
            manifest.audio.get("narration_stem"),
            manifest.audio.get("narration_stem_sha256"),
            "narration stem",
        ),
    ]
    refs += [(media.path, media.blob_sha256, "media") for media in manifest.media]
    cues = {cue.cue_id for cue in sequence.captions}
    seen_cues: set[str] = set()
    for row in manifest.captions:
        cue_id = row.get("cue_id")
        if not isinstance(cue_id, str) or cue_id not in cues or cue_id in seen_cues:
            raise VideoRenderError("render manifest caption inventory does not match the sequence")
        seen_cues.add(cue_id)
        refs.append((row.get("png"), row.get("png_sha256"), "caption PNG"))
    if seen_cues != cues:
        raise VideoRenderError("render manifest caption inventory does not match the sequence")
    scenes = {clip.clip_id: clip for clip in sequence.clips if isinstance(clip, SceneClip)}
    if manifest.scene_frames.keys() != scenes.keys():
        raise VideoRenderError("render manifest scene inventory does not match the sequence")
    for clip_id, clip in scenes.items():
        rows = manifest.scene_frames[clip_id]
        if len(rows) != clip.recipe.total_frames:
            raise VideoRenderError("render manifest scene frame count does not match the sequence")
        for local, frame_row in enumerate(rows):
            if len(frame_row) != 3 or type(frame_row[0]) is not int or frame_row[0] != local:
                raise VideoRenderError("render manifest scene frame inventory is invalid")
            refs.append((f"{aspect}/frames/{clip_id}/{local:05d}.png", frame_row[2], "scene PNG"))

    paths: dict[str, Path] = {}
    for relative, digest, label in refs:
        path = _render_path(root, relative, label)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise VideoRenderError(f"{label} has no valid SHA-256 in the render manifest")
        assert isinstance(relative, str)
        paths[relative] = path
    for relative in output_paths:
        paths[relative] = _render_path(root, relative, "QA output", required=False)
    # Do not open any render input until the entire inventory and all QA destinations are safe.
    for relative, digest, label in refs:
        assert isinstance(relative, str)
        if file_sha256(paths[relative]) != digest:
            raise VideoRenderError(f"the {label} changed after rendering")
    return paths


def check_rendered_video(
    sequence: VideoSequence,
    out_dir: Path,
    aspect: AspectId,
    *,
    ffmpeg: str | None = None,
    spot_count: int = 12,
) -> VideoQAReport:
    """Post-encode QA for one rendered aspect; writes `<aspect>/video-qa.json` and returns it."""
    sequence = VideoSequence.model_validate(sequence.model_dump(mode="json"))
    if aspect not in sequence.outputs:
        raise VideoRenderError(f"{aspect!r} is not an output of sequence {sequence.sequence_id!r}")
    out_dir = out_dir.resolve(strict=True)
    manifest_path = _render_path(out_dir, f"{aspect}/render-manifest.json", "render manifest")
    manifest = RenderManifest.model_validate(json.loads(manifest_path.read_text("utf-8")))
    plan = plan_sequence(sequence)
    if (
        manifest.sequence_sha256 != plan.sequence_sha256
        or manifest.plan_sha256 != value_sha256(plan.model_dump(mode="json"))
        or manifest.aspect != aspect
    ):
        raise VideoRenderError("the render manifest is for a different sequence version")
    clips = {clip.clip_id: clip for clip in sequence.clips}
    frames = _spot_frames(plan, sequence, spot_count)
    neighbors: dict[int, int | None] = {}
    output_paths = [
        f"{aspect}/qa-decoded",
        f"{aspect}/video-qa.json",
        f"{aspect}/video-measurements.json",
    ]
    for frame in frames:
        clip_id, local = plan.sources(frame)[0]
        clip = clips[clip_id]
        assert isinstance(clip, SceneClip)
        neighbors[frame] = _neighbor(clip, local, aspect)
        output_paths.append(f"{aspect}/qa-decoded/{frame:05d}.png")
        if neighbors[frame] is not None:
            output_paths.append(f"{aspect}/qa-decoded/{frame:05d}-neighbor.png")
    paths = _checked_render_files(out_dir, manifest, sequence, aspect, output_paths)
    ffmpeg_path = locate_ffmpeg(ffmpeg)
    mp4 = paths[manifest.outputs["mp4"]]
    mp4_sha256 = file_sha256(mp4)
    rel_mp4 = str(mp4)
    info = parse_stream_info(_run(ffmpeg_path, probe_command(rel_mp4), cwd=out_dir).stderr)
    tags = parse_ffmetadata(
        _check(_run(ffmpeg_path, metadata_command(rel_mp4), cwd=out_dir), "metadata").stdout
    )
    info = info.model_copy(update={"title": tags.get("title"), "comment": tags.get("comment")})
    decoded = count_framemd5(
        _check(_run(ffmpeg_path, framemd5_command(rel_mp4), cwd=out_dir), "framemd5").stdout
    )
    detect = _check(
        _run(
            ffmpeg_path,
            detect_command(rel_mp4, black_min_s=BLACK_MIN_S, freeze_min_s=FREEZE_MIN_S),
            cwd=out_dir,
        ),
        "black/freeze/loudness detection",
    ).stderr
    end_of_media = info.duration_s or plan.duration_s
    narration_path = str(paths[manifest.audio["narration_stem"]])
    narration_s = plan.duration_s
    silences = parse_silence_segments(
        _check(
            _run(ffmpeg_path, silence_command(narration_path), cwd=out_dir), "silencedetect"
        ).stderr,
        narration_s,
    )

    caption_png = {row["cue_id"]: str(paths[row["png"]]) for row in manifest.captions}
    spot_dir = paths[f"{aspect}/qa-decoded"]
    spot_dir.mkdir(parents=True, exist_ok=True)
    spots = []
    for frame in frames:
        clip_id, local = plan.sources(frame)[0]
        clip = clips[clip_id]
        assert isinstance(clip, SceneClip)
        row = manifest.scene_frames[clip_id][local]
        reference = paths[f"{aspect}/frames/{clip_id}/{local:05d}.png"]
        overlays = [caption_png[cue_id] for cue_id in plan.active_captions(frame)]
        decoded_png = paths[f"{aspect}/qa-decoded/{frame:05d}.png"]
        ssim = parse_ssim(
            _run(
                ffmpeg_path,
                spot_frame_command(
                    rel_mp4, frame, plan.fps, str(reference), overlays, str(decoded_png)
                ),
                cwd=out_dir,
            ).stderr
        )
        neighbor = neighbors[frame]
        neighbor_ssim = None
        if neighbor is not None:
            neighbor_ssim = parse_ssim(
                _run(
                    ffmpeg_path,
                    spot_frame_command(
                        rel_mp4,
                        frame,
                        plan.fps,
                        str(paths[f"{aspect}/frames/{clip_id}/{neighbor:05d}.png"]),
                        overlays,
                        str(paths[f"{aspect}/qa-decoded/{frame:05d}-neighbor.png"]),
                    ),
                    cwd=out_dir,
                ).stderr
            )
        spots.append(
            SpotCheck(
                output_frame=frame,
                clip_id=clip_id,
                local_frame=local,
                captions=plan.active_captions(frame),
                manifest_frame_hash=row[1],
                evaluated_frame_hash=evaluate_frame(
                    clip.recipe, local, aspect=aspect
                ).frame_hash_sha256,
                manifest_png_sha256=row[2],
                actual_png_sha256=file_sha256(reference),
                ssim=ssim,
                neighbor_frame=None
                if neighbor is None
                else plan.clip(clip_id).start_frame + neighbor,
                neighbor_ssim=neighbor_ssim,
            )
        )
    measurements = VideoMeasurements(
        info=info,
        decoded_frames=decoded,
        black=parse_black_segments(detect),
        frozen=parse_freeze_segments(detect, end_of_media),
        loudness=parse_ebur128(detect),
        narration_duration_s=narration_s,
        narration_silences=silences,
        spots=spots,
        srt=paths[manifest.outputs["srt"]].read_text(encoding="utf-8"),
        expected_disclosure=manifest.disclosure,
    )
    report = evaluate_video(
        sequence,
        plan,
        aspect,
        measurements,
        mp4_sha256=mp4_sha256,
        render_manifest_sha256=file_sha256(manifest_path),
        holds=static_windows(sequence, plan, aspect),
    )
    _write_json(paths[f"{aspect}/video-qa.json"], report.model_dump(mode="json"))
    _write_json(paths[f"{aspect}/video-measurements.json"], measurements.model_dump(mode="json"))
    return report


__all__ = [
    "VIDEO_TOOL_ENTRYPOINT",
    "Rasterizer",
    "RenderManifest",
    "VideoRenderError",
    "VideoToolError",
    "check_rendered_video",
    "locate_ffmpeg",
    "probe_ffmpeg",
    "probe_playwright",
    "render_sequence",
]
