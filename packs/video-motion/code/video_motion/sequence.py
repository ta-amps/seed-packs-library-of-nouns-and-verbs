"""Video sequence nouns: ordered scene and media clips, transitions, audio tracks and captions.

Pure and deterministic. `plan_sequence()` turns a sequence into exact frame windows (cuts and
crossfades, overlays, caption and audio windows); `audit_sequence()` checks the caption track
against platform safe zones, scene subjects and media keep-out boxes before anything is rendered.
Rasterizing, encoding and pixel measurements live in the worker-only `video_motion.video_worker`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from itertools import pairwise
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from video_motion.captions import srt_from_cues, webvtt_from_cues
from video_motion.errors import BundledDataMissingError, VideoMotionError
from video_motion.media import MediaAsset, MediaElement
from video_motion.nouns import value_sha256
from video_motion.qa import audit_recipe
from video_motion.schemas import (
    ASPECT_PROFILES,
    HEX_COLOR_RE,
    AspectId,
    Box2D,
    CaptionCue,
    QASeverity,
    SceneRecipe,
    canonical_sha256,
)
from video_motion.social import examples_dir
from video_motion.timeline import caption_layout, evaluate_frame, hex_relative_luminance

TransitionKind = Literal["cut", "crossfade"]
SequenceCheck = Literal[
    "scene_clip_qa",
    "caption_safe_zone",
    "caption_readability",
    "caption_overlap",
    "caption_subject_occlusion",
    "caption_media_keep_out",
]
SEQUENCE_CHECKS: tuple[SequenceCheck, ...] = (
    "scene_clip_qa",
    "caption_safe_zone",
    "caption_readability",
    "caption_overlap",
    "caption_subject_occlusion",
    "caption_media_keep_out",
)
SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
MAX_CAPTION_CPS = 20.0
MIN_CAPTION_S = 0.7


class SequenceError(VideoMotionError):
    """Raised when a sequence cannot be planned into exact frame windows."""

    def __init__(self, detail: str) -> None:
        super().__init__(422, "invalid_sequence", "Invalid Video Sequence", detail)


class Transition(BaseModel):
    """How a clip enters: a cut, or a crossfade overlapping the previous clip."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    kind: TransitionKind = "cut"
    duration_s: float = Field(default=0.0, ge=0.0, le=5.0)

    @model_validator(mode="after")
    def _check(self) -> Transition:
        if (self.kind == "cut") != (self.duration_s == 0.0):
            raise ValueError("a cut has duration 0; a crossfade needs a positive duration")
        return self


class SceneClip(BaseModel):
    """A scene recipe rendered frame by frame, optionally with pinned media overlays."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    kind: Literal["scene"] = "scene"
    clip_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    recipe: SceneRecipe
    transition_in: Transition = Field(default_factory=Transition)
    overlays: list[MediaElement] = Field(default_factory=list, max_length=8)


class MediaClip(BaseModel):
    """A pinned recording or image shown full frame (or at its placement) for its span."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    kind: Literal["media"] = "media"
    clip_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    element: MediaElement
    background_hex: str = "#000000"
    transition_in: Transition = Field(default_factory=Transition)

    @field_validator("background_hex")
    @classmethod
    def _check_hex(cls, value: str) -> str:
        if not HEX_COLOR_RE.fullmatch(value):
            raise ValueError(f"Expected 6-digit #RRGGBB color, got {value!r}.")
        return value.lower()


Clip = Annotated[SceneClip | MediaClip, Field(discriminator="kind")]


class VideoSequence(BaseModel):
    """An ordered, versionable video: clips, transitions, narration, music bed and captions."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    sequence_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    title: str = Field(min_length=1)
    synopsis: str = ""
    fps: int = Field(default=30, ge=12, le=60)
    outputs: list[AspectId] = Field(min_length=1, max_length=3)
    clips: list[Clip] = Field(min_length=1, max_length=64)
    narration: list[MediaElement] = Field(default_factory=list, max_length=64)
    music_bed: MediaElement | None = None
    music_duck_db: float = Field(default=9.0, ge=0.0, le=36.0)
    captions: list[CaptionCue] = Field(default_factory=list, max_length=256)
    loudness_target_lufs: float = Field(default=-14.0, ge=-30.0, le=-8.0)
    true_peak_limit_dbtp: float = Field(default=-1.0, ge=-9.0, le=0.0)
    disclosures: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def _check_structure(self) -> VideoSequence:
        if len(set(self.outputs)) != len(self.outputs):
            raise ValueError("outputs must not repeat an aspect")
        clip_ids = [clip.clip_id for clip in self.clips]
        if len(set(clip_ids)) != len(clip_ids):
            raise ValueError("clip_id values must be unique")
        if self.clips[0].transition_in.kind != "cut":
            raise ValueError("the first clip cannot crossfade from nothing")
        element_ids = [element.element_id for element in self.media_elements()]
        if len(set(element_ids)) != len(element_ids):
            raise ValueError("media element_id values must be unique")
        for clip in self.clips:
            if isinstance(clip, SceneClip):
                if clip.recipe.fps != self.fps:
                    raise ValueError(f"clip {clip.clip_id}: recipe fps must equal sequence fps")
                for overlay in clip.overlays:
                    if overlay.kind == "audio":
                        raise ValueError(f"{overlay.element_id}: overlays must be visual")
                    missing = set(self.outputs) - set(overlay.placements)
                    if missing:
                        raise ValueError(
                            f"{overlay.element_id}: no placement for {sorted(missing)}"
                        )
            elif clip.element.kind == "audio":
                raise ValueError(f"clip {clip.clip_id}: a media clip must be visual")
        for element in [*self.narration, *([self.music_bed] if self.music_bed else [])]:
            if element.kind != "audio":
                raise ValueError(f"{element.element_id}: narration and music must be audio")
        cue_ids = [cue.cue_id for cue in self.captions]
        if len(set(cue_ids)) != len(cue_ids):
            raise ValueError("caption cue_id values must be unique")
        unsafe = [cue_id for cue_id in cue_ids if not SAFE_ID_RE.fullmatch(cue_id)]
        if unsafe:
            # Workers name caption files after cue ids, so they must be plain file-name tokens.
            raise ValueError(f"caption cue_id values must match {SAFE_ID_RE.pattern}: {unsafe}")
        return self

    def media_elements(self) -> list[MediaElement]:
        """Every pinned media element, in sequence order."""
        out: list[MediaElement] = []
        for clip in self.clips:
            out += clip.overlays if isinstance(clip, SceneClip) else [clip.element]
        out += self.narration
        if self.music_bed is not None:
            out.append(self.music_bed)
        return out


class ClipPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    clip_id: str
    kind: Literal["scene", "media"]
    start_frame: int = Field(ge=0)
    frame_count: int = Field(ge=1)
    transition_in: TransitionKind
    transition_frames: int = Field(ge=0)

    @property
    def end_frame(self) -> int:
        return self.start_frame + self.frame_count


class FrameWindow(BaseModel):
    """A half-open window [start_frame, end_frame) in sequence frames."""

    model_config = ConfigDict(extra="forbid", strict=True)

    ref_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=1)


class OverlayWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    clip_id: str
    element_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=1)


class SequencePlan(BaseModel):
    """Exact frame windows for every clip, overlay, caption and audio track of a sequence."""

    model_config = ConfigDict(extra="forbid", strict=True)

    format: Literal["video_motion.sequence-plan.v1"] = "video_motion.sequence-plan.v1"
    sequence_id: str
    sequence_sha256: str
    fps: int
    total_frames: int
    duration_s: float
    clips: list[ClipPlan]
    overlays: list[OverlayWindow]
    captions: list[FrameWindow]
    narration: list[FrameWindow]
    music: FrameWindow | None

    def clip(self, clip_id: str) -> ClipPlan:
        return next(c for c in self.clips if c.clip_id == clip_id)

    def sources(self, frame: int) -> list[tuple[str, int]]:
        """(clip_id, local frame) contributing to an output frame: one, or two in a crossfade."""
        return [
            (c.clip_id, frame - c.start_frame)
            for c in self.clips
            if c.start_frame <= frame < c.end_frame
        ]

    def in_transition(self, frame: int) -> bool:
        return len(self.sources(frame)) > 1

    def active_captions(self, frame: int) -> list[str]:
        return [w.ref_id for w in self.captions if w.start_frame <= frame < w.end_frame]

    def active_overlays(self, frame: int) -> list[OverlayWindow]:
        return [w for w in self.overlays if w.start_frame <= frame < w.end_frame]


def clip_frame_count(clip: SceneClip | MediaClip, fps: int) -> int:
    if isinstance(clip, SceneClip):
        return clip.recipe.total_frames
    return max(1, round(clip.element.span_s * fps))


def plan_sequence(sequence: VideoSequence) -> SequencePlan:
    """Lay the sequence out on exact frame indices; raise SequenceError if it cannot fit."""
    fps = sequence.fps
    clips: list[ClipPlan] = []
    overlays: list[OverlayWindow] = []
    for index, clip in enumerate(sequence.clips):
        frames = clip_frame_count(clip, fps)
        overlap = round(clip.transition_in.duration_s * fps) if index else 0
        if clip.transition_in.kind == "crossfade":
            previous = clips[-1]
            if overlap < 1 or 2 * overlap > min(previous.frame_count, frames):
                raise SequenceError(
                    f"clip {clip.clip_id}: a {overlap}-frame crossfade needs both clips to be "
                    "at least twice as long"
                )
        start = clips[-1].end_frame - overlap if clips else 0
        plan = ClipPlan(
            clip_id=clip.clip_id,
            kind=clip.kind,
            start_frame=start,
            frame_count=frames,
            transition_in=clip.transition_in.kind,
            transition_frames=overlap,
        )
        clips.append(plan)
        if isinstance(clip, SceneClip):
            for overlay in clip.overlays:
                ov_start = start + round(overlay.start_s * fps)
                ov_end = ov_start + max(1, round(overlay.span_s * fps))
                if ov_end > plan.end_frame:
                    raise SequenceError(
                        f"overlay {overlay.element_id} runs past clip {clip.clip_id}"
                    )
                overlays.append(
                    OverlayWindow(
                        clip_id=clip.clip_id,
                        element_id=overlay.element_id,
                        start_frame=ov_start,
                        end_frame=ov_end,
                    )
                )
    total = clips[-1].end_frame
    captions = []
    for cue in sorted(sequence.captions, key=lambda c: (c.start_s, c.cue_id)):
        window = FrameWindow(
            ref_id=cue.cue_id,
            start_frame=round(cue.start_s * fps),
            end_frame=round(cue.end_s * fps),
        )
        if window.end_frame > total or window.end_frame <= window.start_frame:
            raise SequenceError(f"caption {cue.cue_id} must lie inside the {total}-frame sequence")
        captions.append(window)
    narration = []
    for element in sequence.narration:
        start = round(element.start_s * fps)
        window = FrameWindow(
            ref_id=element.element_id,
            start_frame=start,
            end_frame=start + max(1, round(element.span_s * fps)),
        )
        if window.end_frame > total:
            raise SequenceError(f"narration {element.element_id} runs past the sequence end")
        narration.append(window)
    music = None
    if sequence.music_bed is not None:
        start = round(sequence.music_bed.start_s * fps)
        if start >= total:
            raise SequenceError("the music bed starts after the sequence ends")
        music = FrameWindow(
            ref_id=sequence.music_bed.element_id,
            start_frame=start,
            end_frame=min(total, start + max(1, round(sequence.music_bed.span_s * fps))),
        )
    return SequencePlan(
        sequence_id=sequence.sequence_id,
        sequence_sha256=value_sha256(sequence.model_dump(mode="json")),
        fps=fps,
        total_frames=total,
        duration_s=round(total / fps, 6),
        clips=clips,
        overlays=overlays,
        captions=captions,
        narration=narration,
        music=music,
    )


class SequenceFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    check: SequenceCheck
    severity: QASeverity
    aspect: AspectId
    frame_index: int | None = None
    clip_id: str | None = None
    detail: str


class SequenceQAReport(BaseModel):
    """Pre-render check of a sequence on one aspect, with a canonical receipt digest."""

    model_config = ConfigDict(extra="forbid", strict=True)

    sequence_id: str
    aspect: AspectId
    passed: bool
    checks: dict[str, bool]
    findings: list[SequenceFinding]
    receipt_sha256: str


def _caption_findings(
    sequence: VideoSequence, plan: SequencePlan, aspect: AspectId
) -> list[SequenceFinding]:
    profile = ASPECT_PROFILES[aspect]
    fps = sequence.fps
    findings: list[SequenceFinding] = []
    cues = {cue.cue_id: cue for cue in sequence.captions}
    layouts = {cue_id: caption_layout(cue, aspect) for cue_id, cue in cues.items()}

    def add(check: SequenceCheck, severity: QASeverity, detail: str, **where: Any) -> None:
        findings.append(
            SequenceFinding(check=check, severity=severity, aspect=aspect, detail=detail, **where)
        )

    for window in plan.captions:
        cue, layout = cues[window.ref_id], layouts[window.ref_id]
        box = layout.box
        if not box.inside_viewport(profile.width, profile.height):
            add(
                "caption_safe_zone",
                "error",
                f"{cue.cue_id} leaves the viewport",
                frame_index=window.start_frame,
            )
        for keep_out in profile.ui_keep_outs:
            if box.intersects(keep_out):
                add(
                    "caption_safe_zone",
                    "error",
                    f"{cue.cue_id} hits {keep_out.label}",
                    frame_index=window.start_frame,
                )
        shown_s = (window.end_frame - window.start_frame) / fps
        chars = len(" ".join(layout.lines))
        if cue.font_px < profile.min_font_px or len(layout.lines) > 3:
            add(
                "caption_readability",
                "error",
                f"{cue.cue_id}: font or line count out of range",
                frame_index=window.start_frame,
            )
        if shown_s < MIN_CAPTION_S:
            add(
                "caption_readability",
                "error",
                f"{cue.cue_id} shows for {shown_s:.2f}s (< {MIN_CAPTION_S}s)",
                frame_index=window.start_frame,
            )
        if chars / shown_s > MAX_CAPTION_CPS:
            add(
                "caption_readability",
                "error",
                f"{cue.cue_id} needs {chars / shown_s:.1f} chars/s (> {MAX_CAPTION_CPS})",
                frame_index=window.start_frame,
            )
        lum_fg, lum_bg = hex_relative_luminance(cue.text_hex), hex_relative_luminance(cue.bg_hex)
        if (max(lum_fg, lum_bg) + 0.05) / (min(lum_fg, lum_bg) + 0.05) < 4.5:
            add(
                "caption_readability",
                "error",
                f"{cue.cue_id}: contrast below 4.5:1",
                frame_index=window.start_frame,
            )
    ordered = sorted(plan.captions, key=lambda w: (w.start_frame, w.end_frame))
    for previous, following in pairwise(ordered):
        gap = following.start_frame - previous.end_frame
        if 1 <= gap <= 2:
            add(
                "caption_readability",
                "error",
                f"{gap}-frame blink gap before {following.ref_id}",
                frame_index=following.start_frame,
            )
    for i, left in enumerate(plan.captions):
        for right in plan.captions[i + 1 :]:
            if right.start_frame >= left.end_frame:
                continue
            same_anchor = cues[left.ref_id].anchor == cues[right.ref_id].anchor
            if same_anchor or layouts[left.ref_id].box.intersects(layouts[right.ref_id].box):
                add(
                    "caption_overlap",
                    "error",
                    f"{left.ref_id} and {right.ref_id} overlap",
                    frame_index=right.start_frame,
                )

    clips = {clip.clip_id: clip for clip in sequence.clips}
    elements = {element.element_id: element for element in sequence.media_elements()}
    reported: set[tuple[str, str]] = set()
    for window in plan.captions:
        box = layouts[window.ref_id].box
        for frame in range(window.start_frame, window.end_frame):
            for clip_id, local in plan.sources(frame):
                clip = clips[clip_id]
                if isinstance(clip, SceneClip):
                    state = evaluate_frame(clip.recipe, local, aspect=aspect)
                    for actor in state.actors:
                        key = (window.ref_id, f"{clip_id}:{actor.actor_id}")
                        if (
                            actor.subject_keep_out is not None
                            and box.intersects(actor.subject_keep_out)
                            and key not in reported
                        ):
                            reported.add(key)
                            add(
                                "caption_subject_occlusion",
                                "error",
                                f"{window.ref_id} covers subject {actor.actor_id}",
                                frame_index=frame,
                                clip_id=clip_id,
                            )
                else:
                    _check_keep_out(
                        clip.element, window.ref_id, box, aspect, frame, clip_id, reported, add
                    )
            for overlay in plan.active_overlays(frame):
                _check_keep_out(
                    elements[overlay.element_id],
                    window.ref_id,
                    box,
                    aspect,
                    frame,
                    overlay.clip_id,
                    reported,
                    add,
                )
    return findings


def _check_keep_out(
    element: MediaElement,
    cue_id: str,
    box: Box2D,
    aspect: AspectId,
    frame: int,
    clip_id: str,
    reported: set[tuple[str, str]],
    add: Callable[..., None],
) -> None:
    placement = element.placements.get(aspect)
    if placement is None:
        return
    for keep_out in placement.keep_out:
        key = (cue_id, f"{element.element_id}:{keep_out.label}")
        if box.intersects(keep_out) and key not in reported:
            reported.add(key)
            add(
                "caption_media_keep_out",
                "error",
                f"{cue_id} covers keep-out {keep_out.label or 'box'} of {element.element_id}",
                frame_index=frame,
                clip_id=clip_id,
            )


def audit_sequence(sequence: VideoSequence, aspect: AspectId) -> SequenceQAReport:
    """Every-frame QA of each scene clip plus caption-track checks, for one output aspect."""
    plan = plan_sequence(sequence)
    findings: list[SequenceFinding] = []
    for clip in sequence.clips:
        if isinstance(clip, SceneClip):
            report = audit_recipe(clip.recipe, aspects=(aspect,))
            findings += [
                SequenceFinding(
                    check="scene_clip_qa",
                    severity=f.severity,
                    aspect=aspect,
                    frame_index=f.frame_index,
                    clip_id=clip.clip_id,
                    detail=f"{f.check}: {f.detail}",
                )
                for f in report.findings
            ]
    findings += _caption_findings(sequence, plan, aspect)
    checks: dict[str, bool] = {
        name: not any(f.check == name and f.severity == "error" for f in findings)
        for name in SEQUENCE_CHECKS
    }
    passed = all(checks.values())
    receipt = canonical_sha256(
        {
            "sequence_sha256": plan.sequence_sha256,
            "aspect": aspect,
            "checks": checks,
            "findings": [f.model_dump() for f in findings],
        }
    )
    return SequenceQAReport(
        sequence_id=sequence.sequence_id,
        aspect=aspect,
        passed=passed,
        checks=checks,
        findings=findings,
        receipt_sha256=receipt,
    )


def frame_visual_keys(sequence: VideoSequence, plan: SequencePlan, aspect: AspectId) -> list[str]:
    """A digest per output frame of everything that should be visible; equal keys mean a hold."""
    clips = {clip.clip_id: clip for clip in sequence.clips}
    elements = {element.element_id: element for element in sequence.media_elements()}
    keys = []
    for frame in range(plan.total_frames):
        sources = plan.sources(frame)
        parts: list[Any] = []
        if len(sources) > 1:
            parts.append(["transition", frame])
        for clip_id, local in sources:
            clip = clips[clip_id]
            if isinstance(clip, SceneClip):
                parts.append(evaluate_frame(clip.recipe, local, aspect=aspect).visual_signature)
            elif clip.element.kind == "image":
                parts.append(["image", clip.element.element_id])
            else:
                parts.append(["recording", clip.element.element_id, local])
        for overlay in plan.active_overlays(frame):
            element = elements[overlay.element_id]
            moving = element.kind == "recording"
            parts.append(["overlay", element.element_id, frame if moving else 0])
        parts.append(["captions", plan.active_captions(frame)])
        keys.append(canonical_sha256(parts))
    return keys


def static_windows(
    sequence: VideoSequence, plan: SequencePlan, aspect: AspectId, *, min_frames: int = 2
) -> list[FrameWindow]:
    """Runs of output frames whose planned content does not change (intended holds)."""
    keys = frame_visual_keys(sequence, plan, aspect)
    windows: list[FrameWindow] = []
    start = 0
    for frame in range(1, len(keys) + 1):
        if frame == len(keys) or keys[frame] != keys[start]:
            if frame - start >= min_frames:
                windows.append(FrameWindow(ref_id="hold", start_frame=start, end_frame=frame))
            start = frame
    return windows


def load_bundled_sequence(name: str) -> tuple[VideoSequence, list[MediaAsset]]:
    """A bundled example sequence and its media nouns from `examples/sequences/`."""
    folder = examples_dir() / "sequences"
    sequence_path, media_path = folder / f"{name}.json", folder / f"{name}.media.json"
    if not sequence_path.is_file() or not media_path.is_file():
        raise BundledDataMissingError(f"Bundled sequence {name!r} is missing from {folder.name}/.")
    sequence = VideoSequence.model_validate(json.loads(sequence_path.read_text(encoding="utf-8")))
    assets = [
        MediaAsset.model_validate(item)
        for item in json.loads(media_path.read_text(encoding="utf-8"))["assets"]
    ]
    return sequence, assets


def with_media_store(sequence: VideoSequence, store: str) -> VideoSequence:
    """The same sequence with every media pin pointing at `store` (keys and digests unchanged)."""

    def retarget(node: Any) -> Any:
        if isinstance(node, dict):
            if set(node) == {"store", "key", "version", "value_sha256"}:
                return {**node, "store": store}
            return {key: retarget(value) for key, value in node.items()}
        if isinstance(node, list):
            return [retarget(item) for item in node]
        return node

    return VideoSequence.model_validate(retarget(sequence.model_dump(mode="json")))


def sequence_srt(sequence: VideoSequence) -> str:
    return srt_from_cues(sequence.captions)


def sequence_webvtt(sequence: VideoSequence, aspect: AspectId) -> str:
    return webvtt_from_cues(
        sequence.captions, aspect, note=f"sequence={sequence.sequence_id} aspect={aspect}"
    )


def disclosure_text(sequence: VideoSequence, assets: Sequence[MediaAsset]) -> str:
    """Plain-language label of what is made-up or generated, for file metadata and manifests."""
    parts = ["AI-generated visuals: procedural motion graphics rendered from code."]
    generated = sorted({asset.disclosure for asset in assets if asset.made_up})
    if generated:
        parts.append("Generated media: " + " ".join(generated))
    parts += sequence.disclosures
    return " ".join(parts)
