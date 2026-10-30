"""Motion learning from timestamped observation traces and beat-proportional scene retargeting."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

from video_motion.errors import MotionTraceError, UnlicensedAssetError
from video_motion.schemas import (
    ALLOWED_LICENSES,
    ASPECT_PROFILES,
    AspectId,
    AspectOverride,
    AssetAttribution,
    AudioCue,
    BeatMarker,
    BeatPhase,
    BeatProportion,
    CaptionCue,
    CastMember,
    EasingKind,
    LearnedTrajectory,
    MotionObservationTrace,
    MotionProfile,
    MotionTrack,
    ObservationSample,
    SceneActor,
    SceneRecipe,
    TrackKeyframe,
    TrajectoryWaypoint,
    canonical_sha256,
)
from video_motion.timeline import evaluate_easing

EASING_CANDIDATES: tuple[EasingKind, ...] = (
    "linear",
    "ease_out_cubic",
    "ease_in_out_cubic",
    "spring_pop",
    "step_hold",
)

# Canonical 16.0s social story proportions:
# Hook 0.0-0.6s -> Orientation 0.6-2.0s -> Setup 2.0-6.0s -> Escalation 6.0-11.0s -> Punchline 11.0-14.8s -> Hold 14.8-16.0s
CANONICAL_BOUNDARY_RATIOS: tuple[float, ...] = (
    0.0,
    0.0375,
    0.125,
    0.375,
    0.6875,
    0.925,
    1.0,
)
BEAT_PHASES: tuple[BeatPhase, ...] = (
    "hook",
    "orientation",
    "setup",
    "escalation",
    "punchline",
    "hold",
)


def fit_easing_primitive(
    u_samples: Sequence[float],
    progress_samples: Sequence[float],
) -> tuple[EasingKind, float]:
    """Fit the minimum-RMSE parametric easing curve over normalized (u, progress) observations."""
    if not u_samples or len(u_samples) != len(progress_samples):
        return "ease_out_cubic", 0.0

    best_kind: EasingKind = "linear"
    best_rmse = float("inf")
    n = len(u_samples)
    for candidate in EASING_CANDIDATES:
        sq_err = 0.0
        for u_val, y_val in zip(u_samples, progress_samples, strict=True):
            pred = evaluate_easing(candidate, u_val)
            diff = pred - y_val
            sq_err += diff * diff
        rmse = math.sqrt(sq_err / float(n))
        if rmse < best_rmse - 1e-9:
            best_rmse = rmse
            best_kind = candidate
    return best_kind, round(best_rmse, 6)


def _snap_beat_boundaries(
    samples: list[ObservationSample],
    duration_s: float,
) -> list[float]:
    cut_ratios: list[float] = []
    prev_speaker = samples[0].active_speaker
    for sample in samples:
        ratio = min(1.0, max(0.0, sample.t_s / duration_s))
        speaker_changed = bool(sample.active_speaker and sample.active_speaker != prev_speaker)
        if (sample.cut_detected or speaker_changed) and 0.015 < ratio < 0.985:
            cut_ratios.append(ratio)
        if sample.active_speaker:
            prev_speaker = sample.active_speaker

    snapped = [0.0]
    for target in CANONICAL_BOUNDARY_RATIOS[1:-1]:
        candidates = [r for r in cut_ratios if abs(r - target) <= 0.08 and r > snapped[-1] + 0.02]
        if candidates:
            chosen = min(candidates, key=lambda r: abs(r - target))
        else:
            chosen = max(snapped[-1] + 0.02, target)
        snapped.append(round(min(0.97, chosen), 6))
    snapped.append(1.0)
    return snapped


def _extract_segment_curve(
    segment: list[ObservationSample],
    start_t: float,
    end_t: float,
) -> tuple[EasingKind, float]:
    if len(segment) < 2 or end_t <= start_t + 1e-6:
        return "step_hold", 0.0

    u_vals = [min(1.0, max(0.0, (s.t_s - start_t) / (end_t - start_t))) for s in segment]
    if all(s.normalized_progress is not None for s in segment):
        p_vals = [float(s.normalized_progress or 0.0) for s in segment]
        return fit_easing_primitive(u_vals, p_vals)

    first = segment[0]
    last = segment[-1]
    dx = last.primary_norm_x - first.primary_norm_x
    dy = last.primary_norm_y - first.primary_norm_y
    ds = last.primary_scale - first.primary_scale
    total_disp = math.sqrt(dx * dx + dy * dy + ds * ds)
    if total_disp < 1e-4:
        return "step_hold", 0.0

    proj_vals: list[float] = []
    for sample in segment:
        sx = sample.primary_norm_x - first.primary_norm_x
        sy = sample.primary_norm_y - first.primary_norm_y
        ss = sample.primary_scale - first.primary_scale
        proj = (sx * dx + sy * dy + ss * ds) / (total_disp * total_disp)
        proj_vals.append(min(1.25, max(-0.25, proj)))
    return fit_easing_primitive(u_vals, proj_vals)


def learn_motion_profile(trace: MotionObservationTrace) -> MotionProfile:
    """Learn a reusable, media-free MotionProfile from timestamped motion/cut/pose observations."""
    if len(trace.samples) < 6:
        raise MotionTraceError(
            "At least 6 timestamped samples are required to learn a 6-beat MotionProfile."
        )

    ordered = sorted(trace.samples, key=lambda s: s.t_s)
    if ordered[-1].t_s > trace.duration_s + 1e-3:
        raise MotionTraceError(
            f"Sample timestamp {ordered[-1].t_s}s exceeds trace duration_s {trace.duration_s}s."
        )

    boundaries = _snap_beat_boundaries(ordered, trace.duration_s)
    beat_proportions: list[BeatProportion] = []
    easing_weights: dict[EasingKind, float] = {}
    waypoints: list[TrajectoryWaypoint] = []

    for idx, phase in enumerate(BEAT_PHASES):
        r0 = boundaries[idx]
        r1 = boundaries[idx + 1]
        t0 = r0 * trace.duration_s
        t1 = r1 * trace.duration_s
        in_beat = [s for s in ordered if (t0 - 1e-6) <= s.t_s <= (t1 + 1e-6)]
        if not in_beat:
            nearest = min(ordered, key=lambda s: abs(s.t_s - (t0 + t1) / 2.0))
            in_beat = [nearest]

        mean_energy = round(sum(s.frame_diff_energy for s in in_beat) / len(in_beat), 6)
        dom_easing, rmse = _extract_segment_curve(in_beat, t0, t1)
        if phase != "hold":
            easing_weights[dom_easing] = easing_weights.get(dom_easing, 0.0) + (r1 - r0)
        beat_proportions.append(
            BeatProportion(
                phase=phase,
                start_ratio=r0,
                end_ratio=r1,
                mean_energy=mean_energy,
                dominant_easing=dom_easing,
                fit_rmse=rmse,
            )
        )
        anchor_sample = in_beat[0]
        waypoints.append(
            TrajectoryWaypoint(
                ratio=r0,
                norm_x=round(anchor_sample.primary_norm_x, 4),
                norm_y=round(anchor_sample.primary_norm_y, 4),
                scale=round(anchor_sample.primary_scale, 4),
                easing=dom_easing,
            )
        )

    final_sample = ordered[-1]
    waypoints.append(
        TrajectoryWaypoint(
            ratio=1.0,
            norm_x=round(final_sample.primary_norm_x, 4),
            norm_y=round(final_sample.primary_norm_y, 4),
            scale=round(final_sample.primary_scale, 4),
            easing="step_hold",
        )
    )

    cut_times = [0.0]
    for sample in ordered:
        if sample.cut_detected and (sample.t_s - cut_times[-1]) > 0.08:
            cut_times.append(sample.t_s)
    if trace.duration_s - cut_times[-1] > 0.08:
        cut_times.append(trace.duration_s)
    intervals = [
        cut_times[i + 1] - cut_times[i]
        for i in range(len(cut_times) - 1)
        if (cut_times[i + 1] - cut_times[i]) > 0.0
    ]
    median_cadence = round(statistics.median(intervals) if intervals else trace.duration_s, 4)
    mean_intensity = round(sum(s.frame_diff_energy for s in ordered) / len(ordered), 6)

    dominant_overall: EasingKind = "ease_out_cubic"
    if easing_weights:
        dominant_overall = max(
            EASING_CANDIDATES,
            key=lambda k: easing_weights.get(k, -1.0),
        )

    trajectories = [LearnedTrajectory(role_slot="lead", waypoints=waypoints)]
    profile_id = f"prof-{trace.trace_id}"
    core_payload = {
        "profile_id": profile_id,
        "title": f"Learned Formula: {trace.title}",
        "source_trace_id": trace.trace_id,
        "reference_duration_s": trace.duration_s,
        "median_cut_cadence_s": median_cadence,
        "mean_motion_intensity": mean_intensity,
        "dominant_easing": dominant_overall,
        "beat_proportions": [bp.model_dump() for bp in beat_proportions],
        "trajectories": [tr.model_dump() for tr in trajectories],
    }
    digest = canonical_sha256(core_payload)
    return MotionProfile(
        profile_id=profile_id,
        title=f"Learned Formula: {trace.title}",
        source_trace_id=trace.trace_id,
        reference_duration_s=trace.duration_s,
        median_cut_cadence_s=median_cadence,
        mean_motion_intensity=mean_intensity,
        dominant_easing=dominant_overall,
        beat_proportions=beat_proportions,
        trajectories=trajectories,
        profile_sha256=digest,
    )


def retarget_motion(
    profile: MotionProfile,
    cast: Sequence[CastMember],
    duration_s: float,
    aspect: AspectId = "reels_9x16",
    *,
    fps: int = 30,
    title: str = "Retargeted Motion Scene",
    recipe_id: str | None = None,
    seed: int = 42,
) -> SceneRecipe:
    """Apply a learned MotionProfile to a new cast and target duration with frame-exact beat ratios."""
    if not cast:
        raise MotionTraceError("retarget_motion requires at least one CastMember.")
    if duration_s <= 1.0:
        raise MotionTraceError("retarget_motion requires duration_s > 1.0 seconds.")

    for member in cast:
        if (
            member.attribution.license not in ALLOWED_LICENSES
            or not member.attribution.creator.strip()
        ):
            raise UnlicensedAssetError(
                member.asset_id,
                "CastMember attribution must carry an allowlisted open license and non-empty creator.",
            )

    total_frames = max(12, round(duration_s * fps))
    aligned_duration = round(total_frames / float(fps), 6)
    safe = ASPECT_PROFILES["reels_9x16"].safe_canvas

    beats: list[BeatMarker] = []
    prev_frame = 0
    for idx, bp in enumerate(profile.beat_proportions):
        end_frame = (
            total_frames
            if idx == len(profile.beat_proportions) - 1
            else max(prev_frame + 1, round(bp.end_ratio * total_frames))
        )
        end_frame = min(total_frames, end_frame)
        start_s = round(prev_frame / float(fps), 6)
        end_s = round(end_frame / float(fps), 6)
        beats.append(
            BeatMarker(
                phase=bp.phase,
                start_s=start_s,
                end_s=max(round(start_s + 1.0 / fps, 6), end_s),
                target_energy=bp.mean_energy,
            )
        )
        prev_frame = end_frame

    lead_traj = profile.trajectories[0]
    actors: list[SceneActor] = []
    attributions_by_id: dict[str, AssetAttribution] = {}

    for slot_idx, member in enumerate(cast):
        attributions_by_id[member.attribution.asset_id] = member.attribution
        lane_offset_x = 0.0 if len(cast) == 1 else (-155.0 if slot_idx % 2 == 0 else 155.0)
        x_kfs: list[TrackKeyframe] = []
        y_kfs: list[TrackKeyframe] = []
        scale_kfs: list[TrackKeyframe] = []
        progress_kfs: list[TrackKeyframe] = []

        for wp_idx, wp in enumerate(lead_traj.waypoints):
            kf_frame = round(wp.ratio * total_frames)
            t_s = round(min(total_frames, kf_frame) / float(fps), 6)
            mirrored_nx = wp.norm_x if slot_idx % 2 == 0 else (1.0 - wp.norm_x)
            stage_x = safe.x + 150.0 + mirrored_nx * (safe.width - 300.0) + lane_offset_x * 0.35
            stage_x = min(safe.right - 135.0, max(safe.x + 135.0, stage_x))
            # Keep actors in upper-mid stage [380..760] so lower-third captions never occlude faces
            stage_y = 390.0 + wp.norm_y * 340.0 + (slot_idx * 24.0)
            x_kfs.append(TrackKeyframe(t_s=t_s, value=round(stage_x, 3), easing=wp.easing))
            y_kfs.append(TrackKeyframe(t_s=t_s, value=round(stage_y, 3), easing=wp.easing))
            scale_kfs.append(TrackKeyframe(t_s=t_s, value=round(wp.scale, 3), easing=wp.easing))
            prog_val = round(wp_idx / max(1, len(lead_traj.waypoints) - 1), 4)
            progress_kfs.append(TrackKeyframe(t_s=t_s, value=prog_val, easing=wp.easing))

        overrides: dict[AspectId, AspectOverride] = {
            "feed_4x5": AspectOverride(
                dx=36.0 if aspect == "feed_4x5" else 20.0,
                dy=-18.0,
                scale_mul=0.95,
            )
        }
        actors.append(
            SceneActor(
                actor_id=member.actor_id,
                kind=member.kind,
                label=member.label,
                asset_id=member.asset_id,
                z_index=10 + slot_idx,
                width=240.0 if member.kind == "character" else 420.0,
                height=260.0 if member.kind == "character" else 280.0,
                fill_hex=member.fill_hex,
                accent_hex=member.accent_hex,
                is_subject_focus=member.is_subject_focus,
                data_points=list(member.data_points),
                tracks=[
                    MotionTrack(property="x", keyframes=x_kfs),
                    MotionTrack(property="y", keyframes=y_kfs),
                    MotionTrack(property="scale", keyframes=scale_kfs),
                    MotionTrack(
                        property="opacity",
                        keyframes=[
                            TrackKeyframe(t_s=0.0, value=0.92, easing="ease_out_cubic"),
                            TrackKeyframe(
                                t_s=round(min(0.4, aligned_duration * 0.1), 4),
                                value=1.0,
                                easing="step_hold",
                            ),
                        ],
                    ),
                    MotionTrack(property="draw_progress", keyframes=progress_kfs),
                ],
                aspect_overrides=overrides,
            )
        )

    captions: list[CaptionCue] = []
    margin = round(3.0 / fps, 6)
    for beat_idx, beat in enumerate(beats):
        if beat.phase == "hold":
            continue
        speaker_member = cast[beat_idx % len(cast)]
        base_line = (
            speaker_member.line_text.strip()
            or f"{beat.phase.capitalize()} beat locked to frame grid."
        )
        cue_text = base_line if beat_idx == 0 else f"{beat.phase.capitalize()}: {base_line}"
        c_start = round(beat.start_s + (0.0 if beat_idx == 0 else margin), 6)
        c_end = round(beat.end_s - margin, 6)
        if c_end - c_start < round(5.0 / fps, 6):
            continue
        captions.append(
            CaptionCue(
                cue_id=f"cue-{beat.phase}",
                role_label=speaker_member.role_label or beat.phase.upper(),
                speaker=speaker_member.label,
                text=cue_text,
                start_s=c_start,
                end_s=c_end,
                anchor="lower_third",
                font_px=42.0,
                max_chars_per_line=26,
            )
        )

    bed_asset_id = "proc-audio-bed-pulse"
    attributions_by_id[bed_asset_id] = AssetAttribution(
        asset_id=bed_asset_id,
        license="LicenseRef-Video-Motion-Procedural",
        creator="video-motion procedural synth",
        source_uri="urn:video-motion:procedural:audio-bed",
        sha256=canonical_sha256({"asset": bed_asset_id, "kind": "music_bed"}),
        digest_basis="procedural_definition",
    )
    audio_cues = [
        AudioCue(
            cue_id="bed-main",
            stem_kind="music_bed",
            asset_id=bed_asset_id,
            start_s=0.0,
            duration_s=aligned_duration,
            peak_dbfs=-14.0,
            duck_db=8.0,
        )
    ]

    cover_idx = min(total_frames - 1, max(0, round(0.75 * total_frames)))
    resolved_id = recipe_id or f"retargeted-{profile.source_trace_id}-{round(duration_s)}s"
    return SceneRecipe(
        recipe_id=resolved_id,
        title=title,
        synopsis=f"Retargeted from {profile.profile_id} ({profile.dominant_easing}) to {aligned_duration:.2f}s.",
        fps=fps,
        duration_s=aligned_duration,
        seed=seed,
        background_hex="#0b1020",
        cover_frame_index=cover_idx,
        beats=beats,
        actors=actors,
        captions=captions,
        audio_cues=audio_cues,
        attributions=sorted(attributions_by_id.values(), key=lambda a: a.asset_id),
    )
