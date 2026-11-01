"""Pure standard-library geometry, hook scoring, caption reflow, and claim-preservation checks."""

from __future__ import annotations

import math
from typing import Any

ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "9:16": (9, 16),
    "1:1": (1, 1),
    "4:5": (4, 5),
}

# Normalized vertical safe bands [y_min_frac, y_max_frac] avoiding top status and bottom overlay chrome.
SAFE_BANDS: dict[str, tuple[float, float]] = {
    "9:16": (0.14, 0.78),
    "1:1": (0.10, 0.86),
    "4:5": (0.12, 0.82),
}


def _crop_dimensions(src_w: int, src_h: int, aspect: str) -> tuple[int, int]:
    if aspect not in ASPECT_RATIOS:
        raise ValueError(f"unsupported aspect {aspect!r}; expected one of {sorted(ASPECT_RATIOS)}")
    aw, ah = ASPECT_RATIOS[aspect]
    target_w = int(round(src_h * (aw / ah)))
    if target_w <= src_w:
        target_w = max(2, target_w - (target_w % 2))
        return target_w, src_h
    target_h = int(round(src_w * (ah / aw)))
    target_h = max(2, target_h - (target_h % 2))
    return src_w, target_h


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def plan_crop_trajectory(
    keyframes: list[dict[str, Any]],
    *,
    src_w: int = 1920,
    src_h: int = 1080,
    aspect: str = "9:16",
    deadband_px: float = 36.0,
    max_pan_px_per_sec: float = 420.0,
) -> dict[str, Any]:
    """Compute a stabilized, velocity-clamped crop trajectory from 16:9 subject keyframes."""
    if src_w <= 0 or src_h <= 0:
        raise ValueError("source dimensions must be positive")
    crop_w, crop_h = _crop_dimensions(src_w, src_h, aspect)
    ordered = sorted(keyframes, key=lambda k: float(k["time_s"]))
    trajectory: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    prev_cx: float | None = None
    prev_cy: float | None = None
    prev_t: float | None = None

    half_w = crop_w / 2.0
    half_h = crop_h / 2.0

    for kf in ordered:
        t = float(kf["time_s"])
        bx, by, bw, bh = [float(x) for x in kf["subject_bbox"]]
        desired_cx = _clamp(bx + bw / 2.0, half_w, src_w - half_w)
        desired_cy = _clamp(by + bh / 2.0, half_h, src_h - half_h)

        if prev_cx is None or prev_cy is None or prev_t is None:
            cx, cy = desired_cx, desired_cy
        else:
            dt = max(1e-3, t - prev_t)
            dx = desired_cx - prev_cx
            dy = desired_cy - prev_cy
            if abs(dx) <= deadband_px:
                dx = 0.0
            if abs(dy) <= deadband_px:
                dy = 0.0
            max_step = max_pan_px_per_sec * dt
            cx = _clamp(prev_cx + _clamp(dx, -max_step, max_step), half_w, src_w - half_w)
            cy = _clamp(prev_cy + _clamp(dy, -max_step, max_step), half_h, src_h - half_h)

        crop_x = int(round(cx - half_w))
        crop_y = int(round(cy - half_h))
        crop_right = crop_x + crop_w
        crop_bottom = crop_y + crop_h

        mode = "pan_crop"
        critical_boxes = [list(map(float, r)) for r in kf.get("critical_regions", [])]
        if bw > crop_w or bh > crop_h:
            mode = "pillarbox_inset"
            violations.append(
                {
                    "time_s": round(t, 3),
                    "reason": "subject_wider_than_crop_window",
                    "required_width_px": int(math.ceil(bw)),
                    "crop_width_px": crop_w,
                    "fallback_mode": mode,
                }
            )
        for rx, ry, rw, rh in critical_boxes:
            if rx < crop_x or (rx + rw) > crop_right or ry < crop_y or (ry + rh) > crop_bottom:
                mode = "pillarbox_inset"
                violations.append(
                    {
                        "time_s": round(t, 3),
                        "reason": "critical_region_clipped_by_crop",
                        "region": [round(rx, 1), round(ry, 1), round(rw, 1), round(rh, 1)],
                        "fallback_mode": mode,
                    }
                )

        trajectory.append(
            {
                "time_s": round(t, 3),
                "crop_x": crop_x,
                "crop_y": crop_y,
                "crop_w": crop_w,
                "crop_h": crop_h,
                "framing_mode": mode,
            }
        )
        prev_cx, prev_cy, prev_t = cx, cy, t

    return {
        "aspect": aspect,
        "source_size": [src_w, src_h],
        "crop_size": [crop_w, crop_h],
        "keyframes": trajectory,
        "clip_violations": violations,
        "all_subjects_safe": len(violations) == 0,
    }


def score_hook_beats(
    beats: list[dict[str, Any]],
    *,
    max_hook_seconds: float = 5.0,
) -> list[dict[str, Any]]:
    """Rank candidate opening beats deterministically and flag weak splash/throat-clearing openings."""
    scored: list[dict[str, Any]] = []
    for beat in beats:
        start_s = float(beat["start_s"])
        end_s = float(beat["end_s"])
        duration = max(0.01, end_s - start_s)
        visual = _clamp(float(beat.get("visual_change_score", 0.0)), 0.0, 1.0)
        clarity = _clamp(float(beat.get("audio_clarity_score", 0.0)), 0.0, 1.0)
        shows_outcome = bool(beat.get("concrete_outcome_shown", False))
        filler = bool(beat.get("filler_opening", False))

        raw = (0.40 * visual) + (0.30 * clarity) + (0.30 * (1.0 if shows_outcome else 0.0))
        if filler:
            raw -= 0.45
        if duration > max_hook_seconds:
            raw -= min(0.25, 0.05 * (duration - max_hook_seconds))
        score = round(_clamp(raw, 0.0, 1.0), 4)
        eligible = (not filler) and (duration <= max_hook_seconds) and score >= 0.55
        scored.append(
            {
                "beat_id": str(beat["beat_id"]),
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "duration_s": round(duration, 3),
                "hook_score": score,
                "eligible_opening_hook": eligible,
                "disqualifier": (
                    "filler_opening"
                    if filler
                    else ("exceeds_max_hook_duration" if duration > max_hook_seconds else (None if eligible else "low_salience"))
                ),
            }
        )
    scored.sort(key=lambda item: (-item["hook_score"], item["start_s"], item["beat_id"]))
    return scored


def _wrap_two_lines(text: str, max_chars_per_line: int) -> tuple[list[str], bool]:
    words = text.strip().split()
    if not words:
        return [], False
    lines: list[str] = []
    current = ""
    overflow = False
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars_per_line:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            if len(word) > max_chars_per_line:
                overflow = True
    if current:
        lines.append(current)
    if len(lines) > 2:
        overflow = True
    return lines, overflow


def reflow_captions(
    captions: list[dict[str, Any]],
    *,
    aspect: str = "9:16",
    max_chars_per_line: int = 32,
    max_cps: float = 18.0,
) -> dict[str, Any]:
    """Reflow captions into platform-safe bands and flag line-count or reading-speed breaches."""
    if aspect not in SAFE_BANDS:
        raise ValueError(f"unsupported aspect {aspect!r}")
    y_min_frac, y_max_frac = SAFE_BANDS[aspect]
    cues: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for idx, cap in enumerate(captions, start=1):
        cue_id = str(cap.get("cue_id") or f"cue-{idx}")
        start_s = float(cap["start_s"])
        end_s = float(cap["end_s"])
        dur = max(0.05, end_s - start_s)
        text = str(cap.get("text") or "").strip()
        lines, line_overflow = _wrap_two_lines(text, max_chars_per_line)
        cps = round(len(text) / dur, 2)
        speed_violation = cps > max_cps

        # Place caption at lower safe anchor unless lower band is marked occupied by critical UI.
        lower_occupied = bool(cap.get("lower_band_occupied", False))
        anchor_y_frac = round(y_min_frac + 0.04, 3) if lower_occupied else round(y_max_frac - 0.06, 3)
        in_safe_zone = y_min_frac <= anchor_y_frac <= y_max_frac

        if line_overflow:
            issues.append({"cue_id": cue_id, "issue": "exceeds_two_line_cap", "line_count": len(lines)})
        if speed_violation:
            issues.append({"cue_id": cue_id, "issue": "reading_speed_exceeded", "chars_per_sec": cps, "max_cps": max_cps})

        cues.append(
            {
                "cue_id": cue_id,
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "lines": lines,
                "chars_per_sec": cps,
                "anchor_y_frac": anchor_y_frac,
                "in_safe_zone": in_safe_zone,
                "valid": (not line_overflow) and (not speed_violation) and in_safe_zone,
            }
        )

    return {
        "aspect": aspect,
        "safe_band_y_frac": [y_min_frac, y_max_frac],
        "cues": cues,
        "issues": issues,
        "all_cues_valid": len(issues) == 0,
    }


def _timestamp_in_segments(ts: float, segments: list[tuple[float, float]]) -> bool:
    return any((start - 1e-6) <= ts <= (end + 1e-6) for start, end in segments)


def check_claim_preservation(
    source_claims: list[dict[str, Any]],
    retained_segments: list[dict[str, Any]],
    cutdown_captions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Ensure every claim spoken or shown in the cutdown preserves its qualifiers and evidence beat."""
    seg_ranges = [(float(s["start_s"]), float(s["end_s"])) for s in retained_segments]
    combined_caption_text = " ".join(str(c.get("text") or "") for c in cutdown_captions).lower()
    results: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for claim in source_claims:
        cid = str(claim["claim_id"])
        trigger_phrase = str(claim["headline_phrase"]).strip().lower()
        referenced_in_cutdown = bool(trigger_phrase) and (trigger_phrase in combined_caption_text)
        qualifiers = [str(q).strip() for q in claim.get("required_qualifiers", [])]
        evidence_ts = claim.get("evidence_timestamp_s")

        if not referenced_in_cutdown:
            results.append({"claim_id": cid, "referenced_in_cutdown": False, "preserved": True, "dropped_qualifiers": []})
            continue

        missing_quals = [q for q in qualifiers if q.lower() not in combined_caption_text]
        evidence_kept = True if evidence_ts is None else _timestamp_in_segments(float(evidence_ts), seg_ranges)
        ok = (len(missing_quals) == 0) and evidence_kept

        if not ok:
            violations.append(
                {
                    "claim_id": cid,
                    "dropped_qualifiers": missing_quals,
                    "evidence_timestamp_retained": evidence_kept,
                }
            )
        results.append(
            {
                "claim_id": cid,
                "referenced_in_cutdown": True,
                "preserved": ok,
                "dropped_qualifiers": missing_quals,
                "evidence_timestamp_retained": evidence_kept,
            }
        )

    return {
        "claim_preservation_passed": len(violations) == 0,
        "claims_checked": len(results),
        "violations": violations,
        "results": results,
    }


def build_cutdown_plan(spec: dict[str, Any], *, aspect: str = "9:16") -> dict[str, Any]:
    """Compile crop trajectory, hook rankings, caption reflow, and claim gate into one cutdown plan."""
    crop = plan_crop_trajectory(
        spec.get("keyframes", []),
        src_w=int(spec.get("source_width", 1920)),
        src_h=int(spec.get("source_height", 1080)),
        aspect=aspect,
    )
    hooks = score_hook_beats(spec.get("candidate_beats", []), max_hook_seconds=float(spec.get("max_hook_seconds", 5.0)))
    captions = reflow_captions(spec.get("captions", []), aspect=aspect)
    claims = check_claim_preservation(
        spec.get("source_claims", []),
        spec.get("retained_segments", []),
        spec.get("captions", []),
    )
    ready = (
        any(h["eligible_opening_hook"] for h in hooks)
        and captions["all_cues_valid"]
        and claims["claim_preservation_passed"]
    )
    return {
        "aspect": aspect,
        "ready_for_render": ready,
        "crop_plan": crop,
        "hook_candidates": hooks,
        "caption_plan": captions,
        "claim_gate": claims,
    }
