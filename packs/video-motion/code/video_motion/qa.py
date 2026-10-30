"""Deterministic every-frame typography, safe-zone, photosensitivity, audio, and rights QA gate."""

from __future__ import annotations

from collections.abc import Sequence

from video_motion.captions import wrap_balanced_lines
from video_motion.schemas import (
    ALLOWED_LICENSES,
    ASPECT_PROFILES,
    SHA256_RE,
    AspectId,
    FrameState,
    QACheckName,
    QACheckSummary,
    QAFinding,
    QAReport,
    SceneRecipe,
    canonical_sha256,
)
from video_motion.timeline import evaluate_frame, hex_relative_luminance

ALL_QA_CHECKS: tuple[QACheckName, ...] = (
    "platform_ui_keep_out",
    "min_font_and_line_balance",
    "subject_keep_out_occlusion",
    "caption_flicker_jitter",
    "black_or_frozen_frames",
    "luminance_flash_rate",
    "audio_peak_and_caption_overlap",
    "asset_attribution_completeness",
)


def build_attribution_credit_line(recipe: SceneRecipe) -> str:
    """Format a deterministic open-license attribution credit line for posting metadata."""
    if not recipe.attributions:
        return "Unattributed"
    ordered = sorted(recipe.attributions, key=lambda a: a.asset_id)
    parts = [f"{attr.asset_id} ({attr.license}, {attr.creator})" for attr in ordered]
    return "Credits: " + "; ".join(parts)


def _check_min_font_and_line_balance(
    recipe: SceneRecipe,
    aspect: AspectId,
    findings: list[QAFinding],
) -> None:
    min_px = ASPECT_PROFILES[aspect].min_font_px
    for cue in recipe.captions:
        if cue.font_px < min_px:
            findings.append(
                QAFinding(
                    check="min_font_and_line_balance",
                    severity="error",
                    aspect=aspect,
                    frame_index=round(cue.start_s * recipe.fps),
                    detail=f"Caption {cue.cue_id!r} font_px={cue.font_px} is below minimum {min_px}px at 1080w.",
                )
            )
        lines = wrap_balanced_lines(cue.text, cue.max_chars_per_line)
        if len(lines) > 3:
            findings.append(
                QAFinding(
                    check="min_font_and_line_balance",
                    severity="error",
                    aspect=aspect,
                    frame_index=round(cue.start_s * recipe.fps),
                    detail=f"Caption {cue.cue_id!r} wraps into {len(lines)} lines (maximum 3).",
                )
            )
        lengths = [len(ln) for ln in lines if ln]
        if lengths and max(lengths) > cue.max_chars_per_line + 4:
            findings.append(
                QAFinding(
                    check="min_font_and_line_balance",
                    severity="error",
                    aspect=aspect,
                    frame_index=round(cue.start_s * recipe.fps),
                    detail=f"Caption {cue.cue_id!r} line length {max(lengths)} exceeds max_chars_per_line ({cue.max_chars_per_line}).",
                )
            )
        if len(lengths) >= 2 and len(cue.text.split()) >= 4:
            ratio = min(lengths) / float(max(lengths))
            if ratio < 0.25:
                findings.append(
                    QAFinding(
                        check="min_font_and_line_balance",
                        severity="error",
                        aspect=aspect,
                        frame_index=round(cue.start_s * recipe.fps),
                        detail=f"Caption {cue.cue_id!r} has unbalanced orphan line break (min/max ratio {ratio:.2f} < 0.25).",
                    )
                )
        lum_fg = hex_relative_luminance(cue.text_hex)
        lum_bg = hex_relative_luminance(cue.bg_hex)
        contrast = (max(lum_fg, lum_bg) + 0.05) / (min(lum_fg, lum_bg) + 0.05)
        if contrast < 4.5:
            findings.append(
                QAFinding(
                    check="min_font_and_line_balance",
                    severity="error",
                    aspect=aspect,
                    frame_index=round(cue.start_s * recipe.fps),
                    detail=f"Caption {cue.cue_id!r} WCAG contrast ratio {contrast:.2f}:1 is below 4.50:1 minimum.",
                )
            )


def _check_frame_keep_outs_and_occlusion(
    frames: list[FrameState],
    aspect: AspectId,
    findings: list[QAFinding],
) -> None:
    profile = ASPECT_PROFILES[aspect]
    reported_ui: set[tuple[str, str]] = set()
    reported_viewport: set[str] = set()
    reported_actor_viewport: set[str] = set()
    reported_occlusion: set[tuple[str, str]] = set()
    reported_cap_overlap: set[tuple[str, str]] = set()

    for state in frames:
        for actor in state.actors:
            if (
                actor.opacity >= 0.05
                and actor.kind != "background"
                and not actor.bounding_box.inside_viewport(profile.width, profile.height)
                and actor.actor_id not in reported_actor_viewport
            ):
                reported_actor_viewport.add(actor.actor_id)
                findings.append(
                    QAFinding(
                        check="platform_ui_keep_out",
                        severity="error",
                        aspect=aspect,
                        frame_index=state.frame_index,
                        detail=f"Actor {actor.actor_id!r} overflows {aspect} viewport ({profile.width}x{profile.height}).",
                    )
                )
        for idx, cap in enumerate(state.captions):
            if (
                not cap.box.inside_viewport(profile.width, profile.height)
                and cap.cue_id not in reported_viewport
            ):
                reported_viewport.add(cap.cue_id)
                findings.append(
                    QAFinding(
                        check="platform_ui_keep_out",
                        severity="error",
                        aspect=aspect,
                        frame_index=state.frame_index,
                        detail=f"Caption {cap.cue_id!r} overflows {aspect} viewport ({profile.width}x{profile.height}).",
                    )
                )
            for ko in profile.ui_keep_outs:
                pair = (cap.cue_id, ko.label)
                if cap.box.intersects(ko) and pair not in reported_ui:
                    reported_ui.add(pair)
                    findings.append(
                        QAFinding(
                            check="platform_ui_keep_out",
                            severity="error",
                            aspect=aspect,
                            frame_index=state.frame_index,
                            detail=f"Caption {cap.cue_id!r} collides with platform UI keep-out {ko.label!r} on {aspect}.",
                        )
                    )
            for actor in state.actors:
                if actor.subject_keep_out is not None and cap.box.intersects(
                    actor.subject_keep_out
                ):
                    occ_pair = (cap.cue_id, actor.actor_id)
                    if occ_pair not in reported_occlusion:
                        reported_occlusion.add(occ_pair)
                        findings.append(
                            QAFinding(
                                check="subject_keep_out_occlusion",
                                severity="error",
                                aspect=aspect,
                                frame_index=state.frame_index,
                                detail=f"Caption {cap.cue_id!r} occludes subject focus keep-out of actor {actor.actor_id!r}.",
                            )
                        )
            for other in state.captions[idx + 1 :]:
                ov_pair = (min(cap.cue_id, other.cue_id), max(cap.cue_id, other.cue_id))
                if cap.box.intersects(other.box) and ov_pair not in reported_cap_overlap:
                    reported_cap_overlap.add(ov_pair)
                    findings.append(
                        QAFinding(
                            check="audio_peak_and_caption_overlap",
                            severity="error",
                            aspect=aspect,
                            frame_index=state.frame_index,
                            detail=f"Captions {cap.cue_id!r} and {other.cue_id!r} overlap spatially on frame {state.frame_index}.",
                        )
                    )


def _check_caption_flicker_and_jitter(
    recipe: SceneRecipe,
    frames: list[FrameState],
    aspect: AspectId,
    findings: list[QAFinding],
) -> None:
    min_frames = max(4, round(0.14 * recipe.fps))
    cue_frame_counts: dict[str, int] = {}
    for state in frames:
        for cap in state.captions:
            cue_frame_counts[cap.cue_id] = cue_frame_counts.get(cap.cue_id, 0) + 1

    for cue in recipe.captions:
        count = cue_frame_counts.get(cue.cue_id, 0)
        if 0 < count < min_frames:
            findings.append(
                QAFinding(
                    check="caption_flicker_jitter",
                    severity="error",
                    aspect=aspect,
                    frame_index=round(cue.start_s * recipe.fps),
                    detail=f"Caption {cue.cue_id!r} appears for only {count} frame(s) (< {min_frames}), causing read flicker.",
                )
            )

    # Detect 1-2 frame empty blink gaps between consecutive captions
    gap_run = 0
    had_caption_before = False
    for state in frames:
        if state.captions:
            if had_caption_before and 1 <= gap_run <= 2:
                findings.append(
                    QAFinding(
                        check="caption_flicker_jitter",
                        severity="error",
                        aspect=aspect,
                        frame_index=state.frame_index,
                        detail=f"Rapid {gap_run}-frame caption disappearance gap before frame {state.frame_index}.",
                    )
                )
            had_caption_before = True
            gap_run = 0
        elif had_caption_before:
            gap_run += 1

    # Detect inter-frame position wobble of an active cue
    positions_by_cue: dict[str, list[tuple[int, float, float]]] = {}
    for state in frames:
        for cap in state.captions:
            positions_by_cue.setdefault(cap.cue_id, []).append(
                (state.frame_index, cap.box.x, cap.box.y)
            )

    for cue_id, trace in positions_by_cue.items():
        for idx in range(1, len(trace)):
            f_prev, x_prev, y_prev = trace[idx - 1]
            f_cur, x_cur, y_cur = trace[idx]
            if f_cur == f_prev + 1 and (abs(x_cur - x_prev) > 1.5 or abs(y_cur - y_prev) > 1.5):
                findings.append(
                    QAFinding(
                        check="caption_flicker_jitter",
                        severity="error",
                        aspect=aspect,
                        frame_index=f_cur,
                        detail=f"Caption {cue_id!r} jitters position between frames {f_prev} and {f_cur}.",
                    )
                )
                break


def _check_black_frozen_and_flash(
    recipe: SceneRecipe,
    frames: list[FrameState],
    aspect: AspectId,
    findings: list[QAFinding],
) -> None:
    black_run = 0
    black_reported = False
    frozen_run = 0
    frozen_reported = False
    max_frozen = max(5, round(1.5 * recipe.fps))
    prev_sig = ""

    for state in frames:
        has_visible_actor = any(a.opacity >= 0.05 for a in state.actors)
        if state.estimated_luminance < 0.015 and not has_visible_actor and not state.captions:
            black_run += 1
            if black_run >= 3 and not black_reported:
                black_reported = True
                findings.append(
                    QAFinding(
                        check="black_or_frozen_frames",
                        severity="error",
                        aspect=aspect,
                        frame_index=state.frame_index,
                        detail=f"Unintended black/empty frame run ({black_run}+ frames) detected at frame {state.frame_index}.",
                    )
                )
        else:
            black_run = 0

        if state.beat_phase != "hold" and state.visual_signature == prev_sig:
            frozen_run += 1
            if frozen_run > max_frozen and not frozen_reported:
                frozen_reported = True
                findings.append(
                    QAFinding(
                        check="black_or_frozen_frames",
                        severity="error",
                        aspect=aspect,
                        frame_index=state.frame_index,
                        detail=f"Unintended frozen visual state ({frozen_run} identical non-hold frames) at frame {state.frame_index}.",
                    )
                )
        else:
            frozen_run = 0
        prev_sig = state.visual_signature

    # Harding / WCAG 2.3.1 luminance flash rate guard: <= 3 flashes (> 6 opposing jumps >= 0.20) per 1s window
    jumps = [0] * len(frames)
    for idx in range(1, len(frames)):
        if abs(frames[idx].estimated_luminance - frames[idx - 1].estimated_luminance) >= 0.20:
            jumps[idx] = 1

    window = max(1, recipe.fps)
    rolling = 0
    for idx, jump in enumerate(jumps):
        rolling += jump
        if idx >= window:
            rolling -= jumps[idx - window]
        if rolling > 6:
            findings.append(
                QAFinding(
                    check="luminance_flash_rate",
                    severity="error",
                    aspect=aspect,
                    frame_index=frames[idx].frame_index,
                    detail=f"Luminance flash rate exceeds 3 flashes/sec ({rolling} transitions >= 0.20 in 1s window).",
                )
            )
            break


def _check_audio_and_caption_schedule(
    recipe: SceneRecipe,
    frames: list[FrameState],
    aspect: AspectId,
    findings: list[QAFinding],
) -> None:
    for cue in recipe.audio_cues:
        if cue.peak_dbfs > -1.0:
            findings.append(
                QAFinding(
                    check="audio_peak_and_caption_overlap",
                    severity="error",
                    aspect=aspect,
                    frame_index=round(cue.start_s * recipe.fps),
                    detail=f"AudioCue {cue.cue_id!r} peak_dbfs={cue.peak_dbfs} exceeds -1.0 dBFS clipping ceiling.",
                )
            )
    for state in frames:
        if state.audio.combined_peak_dbfs > -1.0:
            findings.append(
                QAFinding(
                    check="audio_peak_and_caption_overlap",
                    severity="error",
                    aspect=aspect,
                    frame_index=state.frame_index,
                    detail=f"Combined stem mix reaches {state.audio.combined_peak_dbfs:.2f} dBFS (> -1.0 dBFS) on frame {state.frame_index}.",
                )
            )
            break

    ordered = sorted(recipe.captions, key=lambda c: (c.start_s, c.end_s, c.cue_id))
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            if right.start_s >= left.end_s - 1e-6:
                break
            if left.anchor == right.anchor:
                findings.append(
                    QAFinding(
                        check="audio_peak_and_caption_overlap",
                        severity="error",
                        aspect=aspect,
                        frame_index=round(right.start_s * recipe.fps),
                        detail=f"Captions {left.cue_id!r} and {right.cue_id!r} overlap in time on anchor {left.anchor!r}.",
                    )
                )


def _check_attributions(
    recipe: SceneRecipe,
    aspect: AspectId,
    findings: list[QAFinding],
) -> None:
    by_id = {attr.asset_id: attr for attr in recipe.attributions}
    referenced = sorted(
        {actor.asset_id for actor in recipe.actors}
        | {audio.asset_id for audio in recipe.audio_cues}
    )
    if not referenced:
        findings.append(
            QAFinding(
                check="asset_attribution_completeness",
                severity="error",
                aspect=aspect,
                frame_index=None,
                detail="Recipe references zero assets.",
            )
        )
        return

    for asset_id in referenced:
        attr = by_id.get(asset_id)
        if attr is None:
            findings.append(
                QAFinding(
                    check="asset_attribution_completeness",
                    severity="error",
                    aspect=aspect,
                    frame_index=None,
                    detail=f"Referenced asset {asset_id!r} is missing from recipe.attributions.",
                )
            )
        elif (
            attr.license not in ALLOWED_LICENSES
            or not attr.creator.strip()
            or not SHA256_RE.fullmatch(attr.sha256.lower())
        ):
            findings.append(
                QAFinding(
                    check="asset_attribution_completeness",
                    severity="error",
                    aspect=aspect,
                    frame_index=None,
                    detail=f"Asset {asset_id!r} lacks allowlisted open license, non-empty creator, or valid sha256.",
                )
            )


def audit_recipe(
    recipe: SceneRecipe,
    aspects: Sequence[AspectId] = ("reels_9x16", "feed_4x5"),
) -> QAReport:
    """Audit every frame of a SceneRecipe across requested aspects and return a SHA-256 QAReport."""
    aspect_list: list[AspectId] = list(dict.fromkeys(aspects)) if aspects else ["reels_9x16"]
    findings: list[QAFinding] = []
    total_audited = 0

    for idx, aspect in enumerate(aspect_list):
        frames = [
            evaluate_frame(recipe, frame_idx, aspect=aspect)
            for frame_idx in range(recipe.total_frames)
        ]
        total_audited += len(frames)
        _check_min_font_and_line_balance(recipe, aspect, findings)
        _check_frame_keep_outs_and_occlusion(frames, aspect, findings)
        _check_caption_flicker_and_jitter(recipe, frames, aspect, findings)
        _check_black_frozen_and_flash(recipe, frames, aspect, findings)
        _check_audio_and_caption_schedule(recipe, frames, aspect, findings)
        if idx == 0:
            _check_attributions(recipe, aspect, findings)

    summaries: list[QACheckSummary] = []
    total_errors = 0
    total_warnings = 0
    for check_name in ALL_QA_CHECKS:
        errs = sum(1 for f in findings if f.check == check_name and f.severity == "error")
        warns = sum(1 for f in findings if f.check == check_name and f.severity == "warning")
        total_errors += errs
        total_warnings += warns
        summaries.append(
            QACheckSummary(
                check=check_name,
                passed=(errs == 0),
                error_count=errs,
                warning_count=warns,
            )
        )

    score = round(max(0.0, 100.0 - 15.0 * total_errors - 3.0 * total_warnings), 2)
    passed = total_errors == 0
    credit_line = build_attribution_credit_line(recipe)

    receipt_payload = {
        "recipe_id": recipe.recipe_id,
        "aspects_checked": aspect_list,
        "frames_audited": total_audited,
        "passed": passed,
        "score": score,
        "checks": [s.model_dump() for s in summaries],
        "findings": [f.model_dump() for f in findings],
        "attribution_credit_line": credit_line,
    }
    receipt_sha = canonical_sha256(receipt_payload)

    return QAReport(
        recipe_id=recipe.recipe_id,
        aspects_checked=aspect_list,
        frames_audited=total_audited,
        passed=passed,
        score=score,
        checks=summaries,
        findings=findings,
        attribution_credit_line=credit_line,
        qa_receipt_sha256=receipt_sha,
    )
