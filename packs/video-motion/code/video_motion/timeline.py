"""Deterministic, random-access video-as-code frame evaluator and standalone SVG renderer."""

from __future__ import annotations

import hashlib
import math
from html import escape

from video_motion.captions import wrap_balanced_lines
from video_motion.errors import FrameOutOfRangeError
from video_motion.schemas import (
    ASPECT_PROFILES,
    ActorFrameTransform,
    AspectId,
    AudioFrameEnvelope,
    BeatPhase,
    Box2D,
    CameraCrop,
    CaptionCue,
    CaptionFrameLayout,
    EasingKind,
    FrameState,
    MotionTrack,
    SceneActor,
    SceneRecipe,
    canonical_sha256,
)


def evaluate_easing(kind: EasingKind, u: float) -> float:
    """Evaluate a parametric normalized easing curve on u clamped to [0.0, 1.0]."""
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    if kind == "linear":
        return u
    if kind == "ease_out_cubic":
        inv = 1.0 - u
        return 1.0 - (inv * inv * inv)
    if kind == "ease_in_out_cubic":
        if u < 0.5:
            return 4.0 * u * u * u
        tail = -2.0 * u + 2.0
        return 1.0 - (tail * tail * tail) / 2.0
    if kind == "spring_pop":
        return 1.0 - (1.0 - u) * math.exp(-5.0 * u) * math.cos(2.5 * math.pi * u)
    # step_hold holds the start value until reaching u == 1.0
    return 0.0


def seeded_unit(seed: int, key: str, frame_index: int) -> float:
    """Pure O(1) pseudo-random scalar in [0.0, 1.0) derived strictly from (seed, key, frame_index)."""
    digest = hashlib.sha256(f"{seed}:{key}:{frame_index}".encode()).digest()
    raw = int.from_bytes(digest[:8], "big")
    return raw / float(1 << 64)


def sample_track(track: MotionTrack, t_s: float) -> float:
    """Sample a piecewise eased MotionTrack at exact timestamp `t_s`."""
    kfs = track.keyframes
    if t_s <= kfs[0].t_s:
        return kfs[0].value
    if t_s >= kfs[-1].t_s:
        return kfs[-1].value
    for idx in range(len(kfs) - 1):
        left = kfs[idx]
        right = kfs[idx + 1]
        if left.t_s <= t_s <= right.t_s:
            span = right.t_s - left.t_s
            if span <= 1e-9:
                return right.value
            u = (t_s - left.t_s) / span
            eased = evaluate_easing(left.easing, u)
            return left.value + (right.value - left.value) * eased
    return kfs[-1].value


def hex_relative_luminance(hex_color: str) -> float:
    """Compute WCAG 2.x relative luminance in [0.0, 1.0] for a `#RRGGBB` hex string."""
    clean = hex_color.lstrip("#")
    r_srgb = int(clean[0:2], 16) / 255.0
    g_srgb = int(clean[2:4], 16) / 255.0
    b_srgb = int(clean[4:6], 16) / 255.0

    def _linearize(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * _linearize(r_srgb) + 0.7152 * _linearize(g_srgb) + 0.0722 * _linearize(b_srgb)


def _beat_phase_at(recipe: SceneRecipe, t_s: float) -> BeatPhase:
    for beat in recipe.beats:
        if beat.start_s <= t_s < beat.end_s:
            return beat.phase
    if t_s >= recipe.beats[-1].start_s:
        return recipe.beats[-1].phase
    return recipe.beats[0].phase


def _remap_y_for_aspect(y_9x16: float, aspect: AspectId) -> float:
    """Map an actor center-Y authored on the 9:16 safe stage onto the target aspect's safe stage."""
    if aspect == "reels_9x16":
        return y_9x16
    reels_safe = ASPECT_PROFILES["reels_9x16"].safe_canvas
    feed_safe = ASPECT_PROFILES["feed_4x5"].safe_canvas
    norm = (y_9x16 - reels_safe.y) / reels_safe.height
    return feed_safe.y + norm * feed_safe.height


def stage_mapping(
    x: float, y: float, stage: AspectId, aspect: AspectId
) -> tuple[float, float, float]:
    """Map a point authored on `stage`'s safe canvas onto `aspect`; return (x, y, size factor).

    The original 9:16-to-4:5 rule (remap Y only, keep size) is preserved exactly. Every other pair
    maps the normalized position between safe canvases and scales sizes uniformly so the stage's
    safe canvas fits the target's; per-aspect `AspectOverride`s then adjust the layout.
    """
    if stage == aspect:
        return x, y, 1.0
    if stage == "reels_9x16" and aspect == "feed_4x5":
        return x, _remap_y_for_aspect(y, aspect), 1.0
    src = ASPECT_PROFILES[stage].safe_canvas
    dst = ASPECT_PROFILES[aspect].safe_canvas
    factor = min(dst.width / src.width, dst.height / src.height)
    return (
        dst.x + (x - src.x) / src.width * dst.width,
        dst.y + (y - src.y) / src.height * dst.height,
        factor,
    )


def _stage_default_center(stage: AspectId) -> tuple[float, float]:
    if stage == "reels_9x16":
        return 470.0, 760.0
    safe = ASPECT_PROFILES[stage].safe_canvas
    return safe.x + safe.width / 2.0, safe.y + safe.height / 2.0


def _evaluate_actor(
    actor: SceneActor, t_s: float, aspect: AspectId, stage: AspectId = "reels_9x16"
) -> ActorFrameTransform:
    default_x, default_y = _stage_default_center(stage)
    defaults: dict[str, float] = {
        "x": default_x,
        "y": default_y,
        "scale": 1.0,
        "rotation_deg": 0.0,
        "opacity": 1.0,
        "draw_progress": 1.0,
    }
    for track in actor.tracks:
        defaults[track.property] = sample_track(track, t_s)

    override = actor.aspect_overrides.get(aspect)
    mapped_x, mapped_y, stage_scale = stage_mapping(defaults["x"], defaults["y"], stage, aspect)
    x = mapped_x + (override.dx if override else 0.0)
    y = mapped_y + (override.dy if override else 0.0)
    scale = max(0.05, defaults["scale"] * stage_scale * (override.scale_mul if override else 1.0))
    rotation_deg = defaults["rotation_deg"]
    opacity = min(1.0, max(0.0, defaults["opacity"]))
    # Applied only when set, so recipes without these overrides keep byte-identical frames.
    if override is not None and override.rotation_offset_deg != 0.0:
        rotation_deg += override.rotation_offset_deg
    if override is not None and override.opacity_mul != 1.0:
        opacity *= override.opacity_mul
    draw_progress = min(1.0, max(0.0, defaults["draw_progress"]))

    eff_w = round(actor.width * scale, 4)
    eff_h = round(actor.height * scale, 4)
    bbox = Box2D(
        x=round(x - eff_w / 2.0, 4),
        y=round(y - eff_h / 2.0, 4),
        width=eff_w,
        height=eff_h,
        label=f"actor:{actor.actor_id}",
    )
    subject_box: Box2D | None = None
    if actor.is_subject_focus and opacity >= 0.2:
        # Upper-central head / hero focal zone protected from caption occlusion
        focus_w = round(eff_w * 0.62, 4)
        focus_h = round(eff_h * 0.48, 4)
        subject_box = Box2D(
            x=round(x - focus_w / 2.0, 4),
            y=round(bbox.y + eff_h * 0.06, 4),
            width=max(1.0, focus_w),
            height=max(1.0, focus_h),
            label=f"subject:{actor.actor_id}",
        )

    return ActorFrameTransform(
        actor_id=actor.actor_id,
        kind=actor.kind,
        label=actor.label,
        z_index=actor.z_index,
        x=round(x, 4),
        y=round(y, 4),
        width=actor.width,
        height=actor.height,
        scale=round(scale, 4),
        rotation_deg=round(rotation_deg, 4),
        opacity=round(opacity, 4),
        draw_progress=round(draw_progress, 4),
        fill_hex=actor.fill_hex,
        accent_hex=actor.accent_hex,
        is_subject_focus=actor.is_subject_focus,
        data_points=list(actor.data_points),
        bounding_box=bbox,
        subject_keep_out=subject_box,
    )


def _default_caption_box(
    cue: CaptionCue,
    lines: list[str],
    aspect: AspectId,
) -> Box2D:
    if aspect in cue.box_override:
        return cue.box_override[aspect]

    line_height = cue.font_px * 1.32
    header_extra = cue.font_px * 0.72 if (cue.role_label or cue.speaker) else 0.0
    box_h = round(max(68.0, len(lines) * line_height + header_extra + 32.0), 4)
    longest = max((len(ln) for ln in lines), default=1)
    est_text_w = longest * cue.font_px * 0.56 + 52.0

    if aspect == "landscape_16x9":
        return _landscape_caption_box(cue, box_h, est_text_w)

    if aspect == "reels_9x16":
        max_w = 780.0
        box_w = round(min(max_w, max(280.0, est_text_w)), 4)
        if cue.anchor == "top_banner":
            return Box2D(
                x=round(68.0 + (812.0 - box_w) / 2.0, 4),
                y=192.0,
                width=box_w,
                height=box_h,
                label=cue.cue_id,
            )
        if cue.anchor == "upper_left":
            return Box2D(x=76.0, y=206.0, width=box_w, height=box_h, label=cue.cue_id)
        if cue.anchor == "center_stage":
            return Box2D(
                x=round(68.0 + (812.0 - box_w) / 2.0, 4),
                y=860.0,
                width=box_w,
                height=box_h,
                label=cue.cue_id,
            )
        if cue.anchor == "reclaimed_lower_right":
            # Raw lower-right placement collides with the Reels right-rail button column unless adapted
            raw_w = round(min(400.0, max(280.0, est_text_w)), 4)
            return Box2D(x=660.0, y=1320.0, width=raw_w, height=box_h, label=cue.cue_id)
        return Box2D(
            x=round(68.0 + (812.0 - box_w) / 2.0, 4),
            y=round(1524.0 - box_h, 4),
            width=box_w,
            height=box_h,
            label=cue.cue_id,
        )

    max_w_feed = 900.0
    box_w_feed = round(min(max_w_feed, max(280.0, est_text_w)), 4)
    if cue.anchor == "top_banner":
        return Box2D(
            x=round((1080.0 - box_w_feed) / 2.0, 4),
            y=84.0,
            width=box_w_feed,
            height=box_h,
            label=cue.cue_id,
        )
    if cue.anchor == "upper_left":
        return Box2D(x=76.0, y=96.0, width=box_w_feed, height=box_h, label=cue.cue_id)
    if cue.anchor == "center_stage":
        return Box2D(
            x=round((1080.0 - box_w_feed) / 2.0, 4),
            y=610.0,
            width=box_w_feed,
            height=box_h,
            label=cue.cue_id,
        )
    if cue.anchor == "reclaimed_lower_right":
        reclaimed_w = round(min(400.0, max(260.0, est_text_w)), 4)
        return Box2D(
            x=round(1012.0 - reclaimed_w, 4),
            y=round(1266.0 - box_h, 4),
            width=reclaimed_w,
            height=box_h,
            label=cue.cue_id,
        )
    return Box2D(
        x=round((1080.0 - box_w_feed) / 2.0, 4),
        y=round(1266.0 - box_h, 4),
        width=box_w_feed,
        height=box_h,
        label=cue.cue_id,
    )


def _landscape_caption_box(cue: CaptionCue, box_h: float, est_text_w: float) -> Box2D:
    """Caption boxes inside the 16:9 title-safe canvas (x 96..1824, y 80..984)."""
    box_w = round(min(1440.0, max(320.0, est_text_w)), 4)
    centered_x = round(96.0 + (1728.0 - box_w) / 2.0, 4)
    if cue.anchor == "top_banner":
        return Box2D(x=centered_x, y=96.0, width=box_w, height=box_h, label=cue.cue_id)
    if cue.anchor == "upper_left":
        return Box2D(x=120.0, y=104.0, width=box_w, height=box_h, label=cue.cue_id)
    if cue.anchor == "center_stage":
        return Box2D(
            x=centered_x,
            y=round(540.0 - box_h / 2.0, 4),
            width=box_w,
            height=box_h,
            label=cue.cue_id,
        )
    if cue.anchor == "reclaimed_lower_right":
        corner_w = round(min(640.0, max(320.0, est_text_w)), 4)
        return Box2D(
            x=round(1800.0 - corner_w, 4),
            y=round(968.0 - box_h, 4),
            width=corner_w,
            height=box_h,
            label=cue.cue_id,
        )
    return Box2D(
        x=centered_x, y=round(968.0 - box_h, 4), width=box_w, height=box_h, label=cue.cue_id
    )


def caption_layout(cue: CaptionCue, aspect: AspectId) -> CaptionFrameLayout:
    """Wrapped lines and the safe-zone box for one caption cue on one aspect."""
    lines = wrap_balanced_lines(cue.text, cue.max_chars_per_line)
    return CaptionFrameLayout(
        cue_id=cue.cue_id,
        role_label=cue.role_label,
        speaker=cue.speaker,
        lines=lines,
        font_px=cue.font_px,
        max_chars_per_line=cue.max_chars_per_line,
        anchor=cue.anchor,
        box=_default_caption_box(cue, lines, aspect),
        opacity=1.0,
    )


def _evaluate_captions(
    recipe: SceneRecipe, t_s: float, aspect: AspectId
) -> list[CaptionFrameLayout]:
    return [
        caption_layout(cue, aspect) for cue in recipe.captions if cue.start_s <= t_s < cue.end_s
    ]


def _evaluate_audio(recipe: SceneRecipe, t_s: float) -> AudioFrameEnvelope:
    active_cues = [
        cue for cue in recipe.audio_cues if cue.start_s <= t_s < (cue.start_s + cue.duration_s)
    ]
    if not active_cues:
        return AudioFrameEnvelope(active_stems=[], combined_peak_dbfs=-96.0, ducking_applied_db=0.0)

    voice_active = any(cue.stem_kind == "voiceover" for cue in active_cues)
    power_sum = 0.0
    max_duck = 0.0
    stems: list[str] = []
    for cue in sorted(active_cues, key=lambda c: c.cue_id):
        stems.append(f"{cue.stem_kind}:{cue.cue_id}")
        applied_duck = (
            cue.duck_db if (voice_active and cue.stem_kind in {"music_bed", "ambience"}) else 0.0
        )
        max_duck = max(max_duck, applied_duck)
        eff_db = cue.peak_dbfs - applied_duck
        power_sum += 10.0 ** (eff_db / 10.0)

    combined_db = 10.0 * math.log10(max(1e-12, power_sum))
    return AudioFrameEnvelope(
        active_stems=stems,
        combined_peak_dbfs=round(combined_db, 4),
        ducking_applied_db=round(max_duck, 4),
    )


def _estimate_frame_luminance(
    bg_hex: str,
    actors: list[ActorFrameTransform],
    viewport_w: int,
    viewport_h: int,
) -> float:
    bg_lum = hex_relative_luminance(bg_hex)
    viewport_box = Box2D(x=0.0, y=0.0, width=float(viewport_w), height=float(viewport_h))
    total_area = viewport_box.area()
    lum = bg_lum
    for actor in actors:
        if actor.opacity <= 0.0:
            continue
        vis_area = viewport_box.intersection_area(actor.bounding_box)
        coverage = min(1.0, (vis_area / total_area) * actor.opacity)
        actor_lum = 0.65 * hex_relative_luminance(actor.fill_hex) + 0.35 * hex_relative_luminance(
            actor.accent_hex
        )
        lum = lum * (1.0 - coverage) + actor_lum * coverage
    return round(min(1.0, max(0.0, lum)), 6)


def evaluate_frame(
    recipe: SceneRecipe,
    frame_index: int,
    aspect: AspectId = "reels_9x16",
) -> FrameState:
    """Pure random-access frame evaluation `seek(frame_index)` with zero wall-clock state."""
    total = recipe.total_frames
    if frame_index < 0 or frame_index >= total:
        raise FrameOutOfRangeError(frame_index, total)

    profile = ASPECT_PROFILES[aspect]
    t_s = round(frame_index / float(recipe.fps), 6)
    beat_phase = _beat_phase_at(recipe, t_s)

    sorted_actors = sorted(recipe.actors, key=lambda a: (a.z_index, a.actor_id))
    actor_states = [
        _evaluate_actor(actor, t_s, aspect, recipe.stage_aspect) for actor in sorted_actors
    ]
    caption_states = _evaluate_captions(recipe, t_s, aspect)
    audio_state = _evaluate_audio(recipe, t_s)

    # Seeded camera subtle breathing is bypassed here in favor of crisp deterministic framing.
    # pan_y records the legacy 9:16 stage offset into 4:5; other mappings use stage_mapping().
    legacy_feed = recipe.stage_aspect == "reels_9x16" and aspect == "feed_4x5"
    camera = CameraCrop(
        aspect_id=aspect,
        viewport_width=profile.width,
        viewport_height=profile.height,
        pan_x=0.0,
        pan_y=-185.0 if legacy_feed else 0.0,
        zoom=1.0,
    )
    est_lum = _estimate_frame_luminance(
        recipe.background_hex,
        actor_states,
        profile.width,
        profile.height,
    )

    visual_payload = {
        "bg": recipe.background_hex,
        "actors": [
            {
                "id": a.actor_id,
                "x": a.x,
                "y": a.y,
                "s": a.scale,
                "r": a.rotation_deg,
                "o": a.opacity,
                "p": a.draw_progress,
            }
            for a in actor_states
        ],
        "captions": [
            {"id": c.cue_id, "lines": c.lines, "box": [c.box.x, c.box.y, c.box.width, c.box.height]}
            for c in caption_states
        ],
    }
    visual_sig = canonical_sha256(visual_payload)

    state_core = {
        "recipe_id": recipe.recipe_id,
        "frame_index": frame_index,
        "timestamp_s": t_s,
        "seed": recipe.seed,
        "aspect": aspect,
        "beat_phase": beat_phase,
        "background_hex": recipe.background_hex,
        "estimated_luminance": est_lum,
        "visual_signature": visual_sig,
        "camera": camera.model_dump(),
        "actors": [a.model_dump() for a in actor_states],
        "captions": [c.model_dump() for c in caption_states],
        "audio": audio_state.model_dump(),
    }
    frame_hash = canonical_sha256(state_core)

    return FrameState(
        recipe_id=recipe.recipe_id,
        frame_index=frame_index,
        timestamp_s=t_s,
        seed=recipe.seed,
        aspect=aspect,
        beat_phase=beat_phase,
        background_hex=recipe.background_hex,
        estimated_luminance=est_lum,
        visual_signature=visual_sig,
        camera=camera,
        actors=actor_states,
        captions=caption_states,
        audio=audio_state,
        frame_hash_sha256=frame_hash,
    )


def _render_actor_svg(actor: ActorFrameTransform) -> str:
    if actor.opacity <= 0.001:
        return ""
    w = actor.width
    h = actor.height
    half_w = w / 2.0
    half_h = h / 2.0
    transform = (
        f"translate({actor.x:.2f} {actor.y:.2f}) "
        f"rotate({actor.rotation_deg:.2f}) "
        f"scale({actor.scale:.4f})"
    )
    parts: list[str] = [f'<g transform="{transform}" opacity="{actor.opacity:.3f}">']

    if actor.kind == "character":
        parts.append(
            f'<rect x="{-half_w:.1f}" y="{-half_h:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="28" fill="{actor.fill_hex}" stroke="{actor.accent_hex}" stroke-width="4"/>'
        )
        head_r = min(w, h) * 0.19
        head_cy = -half_h + h * 0.30
        parts.append(
            f'<circle cx="0" cy="{head_cy:.1f}" r="{head_r:.1f}" fill="{actor.accent_hex}" opacity="0.9"/>'
        )
        eye_dx = head_r * 0.34
        eye_y = head_cy - head_r * 0.12
        parts.append(f'<circle cx="{-eye_dx:.1f}" cy="{eye_y:.1f}" r="4.5" fill="#0f172a"/>')
        parts.append(f'<circle cx="{eye_dx:.1f}" cy="{eye_y:.1f}" r="4.5" fill="#0f172a"/>')
        mouth_w = head_r * (0.42 + 0.35 * actor.draw_progress)
        parts.append(
            f'<rect x="{-mouth_w / 2:.1f}" y="{head_cy + head_r * 0.24:.1f}" '
            f'width="{mouth_w:.1f}" height="6" rx="3" fill="#0f172a"/>'
        )
        torso_w = w * 0.64
        torso_h = h * 0.28
        parts.append(
            f'<rect x="{-torso_w / 2:.1f}" y="{head_cy + head_r + 14:.1f}" '
            f'width="{torso_w:.1f}" height="{torso_h:.1f}" rx="18" fill="{actor.accent_hex}" opacity="0.28"/>'
        )
        if actor.label:
            parts.append(
                f'<text x="0" y="{half_h - 22:.1f}" fill="#f8fafc" font-family="ui-sans-serif,system-ui,sans-serif" '
                f'font-size="24" font-weight="700" text-anchor="middle">{escape(actor.label)}</text>'
            )
    elif actor.kind == "chart":
        parts.append(
            f'<rect x="{-half_w:.1f}" y="{-half_h:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="22" fill="{actor.fill_hex}" stroke="{actor.accent_hex}" stroke-width="3"/>'
        )
        pts = actor.data_points if actor.data_points else [25.0, 52.0, 74.0, 96.0]
        peak = max(max(pts), 1.0)
        pad_x = 34.0
        usable_w = max(40.0, w - 2.0 * pad_x)
        usable_h = max(40.0, h - 108.0)
        bar_gap = 14.0
        bar_w = max(12.0, (usable_w - bar_gap * (len(pts) - 1)) / len(pts))
        poly_coords: list[str] = []
        for idx, val in enumerate(pts):
            bx = -half_w + pad_x + idx * (bar_w + bar_gap)
            bh = (val / peak) * usable_h * actor.draw_progress
            by = half_h - 42.0 - bh
            parts.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{max(2.0, bh):.1f}" '
                f'rx="8" fill="{actor.accent_hex}" opacity="0.82"/>'
            )
            poly_coords.append(f"{bx + bar_w / 2.0:.1f},{by:.1f}")
        if len(poly_coords) >= 2:
            parts.append(
                f'<polyline points="{" ".join(poly_coords)}" fill="none" stroke="#f8fafc" '
                f'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        if actor.label:
            parts.append(
                f'<text x="{-half_w + 28:.1f}" y="{-half_h + 40:.1f}" fill="#f8fafc" '
                f'font-family="ui-sans-serif,system-ui,sans-serif" font-size="26" font-weight="700">{escape(actor.label)}</text>'
            )
    elif actor.kind == "mechanism":
        parts.append(
            f'<rect x="{-half_w:.1f}" y="{-half_h:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="20" fill="{actor.fill_hex}" stroke="{actor.accent_hex}" stroke-width="3"/>'
        )
        track_x0 = -half_w + 36.0
        track_x1 = half_w - 36.0
        track_w = max(20.0, track_x1 - track_x0)
        token_x = track_x0 + track_w * actor.draw_progress
        parts.append(
            f'<line x1="{track_x0:.1f}" y1="12" x2="{track_x1:.1f}" y2="12" '
            f'stroke="#334155" stroke-width="10" stroke-linecap="round"/>'
        )
        parts.append(
            f'<line x1="{track_x0:.1f}" y1="12" x2="{token_x:.1f}" y2="12" '
            f'stroke="{actor.accent_hex}" stroke-width="10" stroke-linecap="round"/>'
        )
        parts.append(
            f'<circle cx="{token_x:.1f}" cy="12" r="16" fill="#f8fafc" stroke="{actor.accent_hex}" stroke-width="4"/>'
        )
        if actor.label:
            parts.append(
                f'<text x="{track_x0:.1f}" y="{-half_h + 42:.1f}" fill="#f8fafc" '
                f'font-family="ui-sans-serif,system-ui,sans-serif" font-size="24" font-weight="700">{escape(actor.label)}</text>'
            )
    elif actor.kind == "background":
        parts.append(
            f'<rect x="{-half_w:.1f}" y="{-half_h:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="36" fill="{actor.fill_hex}" stroke="{actor.accent_hex}" stroke-width="2" opacity="0.5"/>'
        )
    else:
        parts.append(
            f'<rect x="{-half_w:.1f}" y="{-half_h:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="20" fill="{actor.fill_hex}" stroke="{actor.accent_hex}" stroke-width="3"/>'
        )
        bar_w = max(12.0, (w - 40.0) * actor.draw_progress)
        parts.append(
            f'<rect x="{-half_w + 20:.1f}" y="{half_h - 26:.1f}" width="{bar_w:.1f}" height="8" '
            f'rx="4" fill="{actor.accent_hex}"/>'
        )
        if actor.label:
            parts.append(
                f'<text x="0" y="8" fill="#f8fafc" font-family="ui-sans-serif,system-ui,sans-serif" '
                f'font-size="26" font-weight="700" text-anchor="middle">{escape(actor.label)}</text>'
            )

    parts.append("</g>")
    return "".join(parts)


def _render_caption_svg(cap: CaptionFrameLayout) -> str:
    b = cap.box
    parts: list[str] = [
        f'<g opacity="{cap.opacity:.3f}">',
        f'<rect x="{b.x:.1f}" y="{b.y:.1f}" width="{b.width:.1f}" height="{b.height:.1f}" '
        f'rx="18" fill="#090d16" fill-opacity="0.88" stroke="#38bdf8" stroke-opacity="0.65" stroke-width="2"/>',
    ]
    cursor_y = b.y + 22.0
    if cap.role_label or cap.speaker:
        badge = " · ".join(part for part in (cap.role_label, cap.speaker) if part)
        cursor_y += cap.font_px * 0.56
        parts.append(
            f'<text x="{b.x + 22:.1f}" y="{cursor_y:.1f}" fill="#38bdf8" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="{max(22.0, cap.font_px * 0.56):.1f}" '
            f'font-weight="700">{escape(badge)}</text>'
        )
        cursor_y += 12.0

    for line in cap.lines:
        cursor_y += cap.font_px * 1.15
        parts.append(
            f'<text x="{b.x + b.width / 2.0:.1f}" y="{cursor_y:.1f}" fill="#f8fafc" '
            f'font-family="ui-sans-serif,system-ui,sans-serif" font-size="{cap.font_px:.1f}" '
            f'font-weight="700" text-anchor="middle">{escape(line)}</text>'
        )
    parts.append("</g>")
    return "".join(parts)


def _render_frame_inner(frame_state: FrameState, *, show_safe_zones: bool) -> str:
    profile = ASPECT_PROFILES[frame_state.aspect]
    w = profile.width
    h = profile.height
    parts: list[str] = [
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{frame_state.background_hex}"/>'
    ]
    for actor in frame_state.actors:
        rendered = _render_actor_svg(actor)
        if rendered:
            parts.append(rendered)
    for caption in frame_state.captions:
        parts.append(_render_caption_svg(caption))

    if show_safe_zones:
        sc = profile.safe_canvas
        parts.append(
            f'<rect x="{sc.x:.1f}" y="{sc.y:.1f}" width="{sc.width:.1f}" height="{sc.height:.1f}" '
            f'fill="none" stroke="#22c55e" stroke-width="3" stroke-dasharray="14 10" opacity="0.8"/>'
        )
        for ko in profile.ui_keep_outs:
            parts.append(
                f'<rect x="{ko.x:.1f}" y="{ko.y:.1f}" width="{ko.width:.1f}" height="{ko.height:.1f}" '
                f'fill="#ef4444" fill-opacity="0.16" stroke="#ef4444" stroke-width="2" stroke-dasharray="8 6"/>'
            )
            parts.append(
                f'<text x="{ko.x + 14:.1f}" y="{ko.y + 30:.1f}" fill="#fca5a5" '
                f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="20">{escape(ko.label)}</text>'
            )
        for actor in frame_state.actors:
            if actor.subject_keep_out is not None:
                sk = actor.subject_keep_out
                parts.append(
                    f'<rect x="{sk.x:.1f}" y="{sk.y:.1f}" width="{sk.width:.1f}" height="{sk.height:.1f}" '
                    f'fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="6 6"/>'
                )
        hud = f"f={frame_state.frame_index:04d} · {frame_state.timestamp_s:05.2f}s · {frame_state.beat_phase}"
        parts.append(
            '<rect x="24" y="20" width="430" height="40" rx="8" fill="#090d16" fill-opacity="0.82"/>'
        )
        parts.append(
            f'<text x="38" y="47" fill="#a5f3fc" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" '
            f'font-size="21" font-weight="600">{escape(hud)}</text>'
        )
    return "".join(parts)


def render_svg_frame(frame_state: FrameState, *, show_safe_zones: bool = False) -> str:
    """Render a standalone, deterministic SVG document for a single FrameState."""
    profile = ASPECT_PROFILES[frame_state.aspect]
    inner = _render_frame_inner(frame_state, show_safe_zones=show_safe_zones)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {profile.width} {profile.height}" '
        f'width="{profile.width}" height="{profile.height}" '
        f'data-recipe="{escape(frame_state.recipe_id)}" '
        f'data-frame="{frame_state.frame_index}" '
        f'data-aspect="{frame_state.aspect}" '
        f'data-sha256="{frame_state.frame_hash_sha256}">'
        f"{inner}</svg>"
    )


def render_caption_overlay_svg(cue: CaptionCue, aspect: AspectId) -> str:
    """A transparent full-frame SVG holding one caption, laid out for `aspect`'s safe zones.

    Used for sequence-level caption tracks, which are composited over clips and transitions.
    """
    profile = ASPECT_PROFILES[aspect]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {profile.width} {profile.height}" '
        f'width="{profile.width}" height="{profile.height}" data-caption="{escape(cue.cue_id)}" '
        f'data-aspect="{aspect}">{_render_caption_svg(caption_layout(cue, aspect))}</svg>'
    )


def sample_frame_indices(total_frames: int, sample_count: int = 6) -> list[int]:
    """Select `sample_count` evenly spaced frame indices across [0, total_frames - 1]."""
    count = max(1, min(sample_count, total_frames))
    if count == 1:
        return [0]
    return [round(i * (total_frames - 1) / (count - 1)) for i in range(count)]


def render_contact_sheet_svg(
    recipe: SceneRecipe,
    sample_count: int = 6,
    aspect: AspectId = "reels_9x16",
    *,
    show_safe_zones: bool = True,
) -> str:
    """Render a multi-frame SVG contact sheet displaying evenly spaced keyframes and beat labels."""
    profile = ASPECT_PROFILES[aspect]
    indices = sample_frame_indices(recipe.total_frames, sample_count)
    cols = min(3, len(indices))
    rows = math.ceil(len(indices) / cols)

    tile_w = 270
    tile_h = round(tile_w * profile.height / profile.width)
    label_h = 46
    pad = 22
    header_h = 62
    sheet_w = pad + cols * (tile_w + pad)
    sheet_h = header_h + pad + rows * (tile_h + label_h + pad)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {sheet_w} {sheet_h}" width="{sheet_w}" height="{sheet_h}">',
        f'<rect x="0" y="0" width="{sheet_w}" height="{sheet_h}" fill="#070b14"/>',
        f'<text x="{pad}" y="40" fill="#e2e8f0" font-family="ui-sans-serif,system-ui,sans-serif" '
        f'font-size="20" font-weight="700">{escape(recipe.title)} -- {escape(aspect)} ({profile.width}x{profile.height})</text>',
    ]

    for idx, frame_idx in enumerate(indices):
        col = idx % cols
        row = idx // cols
        tx = pad + col * (tile_w + pad)
        ty = header_h + row * (tile_h + label_h + pad)
        state = evaluate_frame(recipe, frame_idx, aspect=aspect)
        inner = _render_frame_inner(state, show_safe_zones=show_safe_zones)
        parts.append(
            f'<svg x="{tx}" y="{ty}" width="{tile_w}" height="{tile_h}" '
            f'viewBox="0 0 {profile.width} {profile.height}">{inner}</svg>'
        )
        parts.append(
            f'<rect x="{tx}" y="{ty}" width="{tile_w}" height="{tile_h}" '
            f'fill="none" stroke="#334155" stroke-width="1.5"/>'
        )
        caption = f"f={state.frame_index} ({state.timestamp_s:.2f}s) · {state.beat_phase}"
        parts.append(
            f'<text x="{tx + 4}" y="{ty + tile_h + 20}" fill="#cbd5e1" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="12">{escape(caption)}</text>'
        )
        parts.append(
            f'<text x="{tx + 4}" y="{ty + tile_h + 37}" fill="#64748b" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="11">sha256:{state.frame_hash_sha256[:16]}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
