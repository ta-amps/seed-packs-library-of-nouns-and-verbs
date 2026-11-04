"""Multi-frame scene, transition, camera-stability, cognitive-load and caption evaluators."""

from __future__ import annotations

import math
import re
import statistics
from typing import Any

WORD_RE = re.compile(r"[A-Za-z0-9']+")
HEX64_RE = re.compile(r"^[0-9a-f]{64}\Z")

STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "does", "for",
    "from", "had", "has", "have", "he", "her", "here", "him", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "just", "me", "more", "most", "my",
    "no", "not", "now", "of", "on", "one", "only", "or", "other", "our", "out",
    "over", "s", "same", "she", "so", "some", "such", "t", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "up", "us", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "would", "you", "your",
})

STATIC_SLIDE_KINDS = frozenset({
    "static_slide",
    "typographic_card",
    "section_card",
    "terminal",
    "browser_capture",
})

CLAUSE_CONJUNCTIONS = frozenset({
    "and", "but", "or", "while", "where", "when", "because", "so", "before", "after",
    "until", "with", "without", "across", "into", "through", "under", "from",
})


def _words(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text or "")]


def _content_words(text: str) -> set[str]:
    return {w for w in _words(text) if len(w) >= 3 and w not in STOPWORDS}


def wrap_caption_clauses(text: str, *, max_chars: int = 42, max_lines: int = 2) -> list[str]:
    """Break a caption string into at most ``max_lines`` clause-balanced lines."""
    clean = " ".join((text or "").replace("\n", " ").split())
    if not clean:
        return []
    if len(clean) <= max_chars or max_lines <= 1:
        return [clean]

    tokens = clean.split(" ")
    if len(tokens) == 1:
        return [clean]

    best_idx = 1
    best_cost = math.inf
    for idx in range(1, len(tokens)):
        left = " ".join(tokens[:idx])
        right = " ".join(tokens[idx:])
        overflow = max(0, len(left) - max_chars) + max(0, len(right) - max_chars)
        imbalance = abs(len(left) - len(right))
        orphan_penalty = 40.0 if (len(tokens) >= 5 and (idx == 1 or len(tokens) - idx == 1)) else 0.0
        prev_tok = tokens[idx - 1]
        next_tok = tokens[idx].lower().strip("\"'([{")
        clause_bonus = 0.0
        if prev_tok.endswith((",", ";", ":", "\u2014", "-", ".")):
            clause_bonus -= 14.0
        elif next_tok in CLAUSE_CONJUNCTIONS:
            clause_bonus -= 8.0
        cost = overflow * 200.0 + imbalance + orphan_penalty + clause_bonus
        if cost < best_cost:
            best_cost = cost
            best_idx = idx

    return [" ".join(tokens[:best_idx]), " ".join(tokens[best_idx:])]


def evaluate_shot_dwell_and_transitions(
    shots: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
    *,
    min_shot_s: float = 1.80,
    warn_shot_s: float = 2.00,
    max_text_crossfade_frames: int = 4,
    fps: int = 30,
) -> dict[str, Any]:
    """Inspect multi-frame shot durations and cut/crossfade transitions across scenes."""
    if fps <= 0:
        raise ValueError("fps must be positive")
    findings: list[dict[str, Any]] = []
    durations: list[float] = []
    flash_shots = 0

    shots_by_id: dict[str, dict[str, Any]] = {}
    for shot in shots:
        shot_id = str(shot["id"])
        shots_by_id[shot_id] = shot
        start_s = float(shot["start_s"])
        end_s = float(shot["end_s"])
        dur_s = round(end_s - start_s, 4)
        durations.append(dur_s)
        if dur_s <= 0.0:
            flash_shots += 1
            findings.append({
                "code": "invalid_shot_window",
                "severity": "blocker",
                "item_id": shot_id,
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "detail": f"Shot {shot_id} has non-positive duration ({dur_s:.3f}s).",
            })
        elif dur_s < min_shot_s:
            flash_shots += 1
            findings.append({
                "code": "flash_shot_too_short",
                "severity": "major",
                "item_id": shot_id,
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "detail": (
                    f"Shot {shot_id} lasts {dur_s:.2f}s (< {min_shot_s:.2f}s minimum); "
                    "viewers cannot orient before the next cut."
                ),
            })
        elif dur_s < warn_shot_s and bool(shot.get("has_stage_text", False)):
            findings.append({
                "code": "tight_text_shot",
                "severity": "minor",
                "item_id": shot_id,
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "detail": f"Text-bearing shot {shot_id} lasts {dur_s:.2f}s (< {warn_shot_s:.2f}s target).",
            })

    ghost_transitions = 0
    for tr in transitions:
        from_id = str(tr["from_shot"])
        to_id = str(tr["to_shot"])
        kind = str(tr.get("kind", "cut"))
        frames = int(tr.get("frames", 0))
        from_text = bool(shots_by_id.get(from_id, {}).get("has_stage_text", False))
        to_text = bool(shots_by_id.get(to_id, {}).get("has_stage_text", False))
        if kind in ("crossfade", "dissolve", "fade_overlap") and frames > max_text_crossfade_frames and from_text and to_text:
            ghost_transitions += 1
            at_s = float(shots_by_id.get(to_id, {}).get("start_s", 0.0))
            findings.append({
                "code": "ghosting_text_crossfade",
                "severity": "major",
                "item_id": f"{from_id}->{to_id}",
                "start_s": round(at_s - frames / fps, 3),
                "end_s": round(at_s + frames / fps, 3),
                "detail": (
                    f"{kind} of {frames} frames between text-bearing shots {from_id} and {to_id} "
                    f"exceeds {max_text_crossfade_frames} frames and superimposes two layers of text."
                ),
            })

    min_dur = round(min(durations), 4) if durations else 0.0
    med_dur = round(statistics.median(durations), 4) if durations else 0.0
    verdict = "pass"
    if any(f["severity"] in ("blocker", "major") for f in findings):
        verdict = "fail"
    elif findings:
        verdict = "warn"

    return {
        "shot_count": len(shots),
        "min_shot_s": min_dur,
        "median_shot_s": med_dur,
        "flash_shots": flash_shots,
        "ghost_transitions": ghost_transitions,
        "findings": findings,
        "verdict": verdict,
    }


def evaluate_camera_and_slide_stability(
    scene_tracks: list[dict[str, Any]],
    *,
    min_unmotivated_zoom: float = 0.003,
    max_pan_drift_px: float = 2.0,
) -> dict[str, Any]:
    """Flag unmotivated Ken Burns zoom/pan drift on static slides, cards and terminals."""
    findings: list[dict[str, Any]] = []
    drifting_static_scenes = 0

    for scene in scene_tracks:
        scene_id = str(scene["id"])
        scene_kind = str(scene.get("scene_kind", "static_slide"))
        has_focal_target = bool(scene.get("has_focal_target", False))
        samples = scene.get("samples", [])
        if not samples:
            continue
        scales = [float(pt["scale"]) for pt in samples]
        txs = [float(pt.get("tx_px", 0.0)) for pt in samples]
        tys = [float(pt.get("ty_px", 0.0)) for pt in samples]
        scale_drift = round(max(scales) - min(scales), 5)
        pan_drift_px = round(math.hypot(max(txs) - min(txs), max(tys) - min(tys)), 3)
        start_s = float(samples[0].get("t_s", 0.0))
        end_s = float(samples[-1].get("t_s", start_s))

        if scene_kind in STATIC_SLIDE_KINDS and not has_focal_target:
            if scale_drift >= min_unmotivated_zoom or pan_drift_px > max_pan_drift_px:
                drifting_static_scenes += 1
                findings.append({
                    "code": "unmotivated_ken_burns_drift",
                    "severity": "major",
                    "item_id": scene_id,
                    "start_s": round(start_s, 3),
                    "end_s": round(end_s, 3),
                    "detail": (
                        f"Static {scene_kind} '{scene_id}' drifts in scale by {scale_drift:.4f} "
                        f"and translation by {pan_drift_px:.2f}px without a focal target; "
                        "lock static typography and browser slides at 1:1 (scale=1.000)."
                    ),
                })

    verdict = "fail" if drifting_static_scenes > 0 else "pass"
    return {
        "scene_count": len(scene_tracks),
        "drifting_static_scenes": drifting_static_scenes,
        "findings": findings,
        "verdict": verdict,
    }


def evaluate_reading_speed_and_cognitive_load(
    text_items: list[dict[str, Any]],
    speech_cues: list[dict[str, Any]],
    *,
    words_per_s_max: float = 3.0,
    base_orient_s: float = 0.50,
    prose_escape_min_words: int = 6,
    conflict_min_words: int = 12,
    min_lexical_overlap: float = 0.35,
) -> dict[str, Any]:
    """Check on-screen reading speed, disallowed must_read=False escapes, and speech-vs-stage split attention."""
    findings: list[dict[str, Any]] = []
    unreadable_items = 0
    cognitive_conflicts = 0
    max_stage_wps = 0.0

    for item in text_items:
        item_id = str(item["id"])
        text = str(item.get("text", "")).strip()
        start_s = float(item["start_s"])
        end_s = float(item["end_s"])
        must_read = bool(item.get("must_read", True))
        words = _words(text)
        word_count = len(words)
        dur_s = round(end_s - start_s, 4)

        if dur_s <= 0.0:
            unreadable_items += 1
            findings.append({
                "code": "inverted_text_window",
                "severity": "blocker",
                "item_id": item_id,
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "detail": f"Stage text '{item_id}' has non-positive window ({start_s:.2f}s..{end_s:.2f}s).",
            })
            continue

        wps = round(word_count / dur_s, 3) if word_count else 0.0
        if wps > max_stage_wps:
            max_stage_wps = wps

        if not must_read and word_count >= prose_escape_min_words:
            unreadable_items += 1
            findings.append({
                "code": "unreadable_prose_escape",
                "severity": "major",
                "item_id": item_id,
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "detail": (
                    f"Stage text '{item_id}' ({word_count} words in {dur_s:.2f}s) sets must_read=False "
                    f"on prose >= {prose_escape_min_words} words; shorten to a label or extend dwell."
                ),
            })

        needed_s = round(base_orient_s + word_count / words_per_s_max, 3)
        if must_read and word_count > 0 and dur_s + 1e-6 < needed_s:
            unreadable_items += 1
            findings.append({
                "code": "stage_text_too_fast",
                "severity": "major",
                "item_id": item_id,
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "detail": (
                    f"Stage text '{item_id}' shows {word_count} words for {dur_s:.2f}s "
                    f"({wps:.2f} wps; needs >= {needed_s:.2f}s)."
                ),
            })

        if word_count >= conflict_min_words:
            overlapping_speech: list[str] = []
            overlap_s = 0.0
            for cue in speech_cues:
                cs = float(cue["start_s"])
                ce = float(cue["end_s"])
                ov = min(end_s, ce) - max(start_s, cs)
                if ov > 0.0:
                    overlap_s += ov
                    overlapping_speech.append(str(cue.get("text", "")))
            if overlap_s >= 0.50 and overlapping_speech:
                stage_cw = _content_words(text)
                speech_cw = _content_words(" ".join(overlapping_speech))
                if stage_cw:
                    lexical_overlap = len(stage_cw & speech_cw) / len(stage_cw)
                    if lexical_overlap < min_lexical_overlap:
                        cognitive_conflicts += 1
                        findings.append({
                            "code": "modality_prose_conflict",
                            "severity": "major",
                            "item_id": item_id,
                            "start_s": round(start_s, 3),
                            "end_s": round(end_s, 3),
                            "detail": (
                                f"Stage prose '{item_id}' ({word_count} words) overlaps speech for "
                                f"{overlap_s:.2f}s with {lexical_overlap:.2f} content-word overlap "
                                f"(< {min_lexical_overlap:.2f}), causing split-attention reading confusion."
                            ),
                        })

    verdict = "fail" if (unreadable_items > 0 or cognitive_conflicts > 0) else "pass"
    return {
        "text_item_count": len(text_items),
        "unreadable_items": unreadable_items,
        "cognitive_conflicts": cognitive_conflicts,
        "max_stage_wps": round(max_stage_wps, 3),
        "findings": findings,
        "verdict": verdict,
    }


def evaluate_live_web_journey_provenance(
    journeys: list[dict[str, Any]],
    *,
    min_desktop_width_px: int = 1280,
) -> dict[str, Any]:
    """Verify authentic desktop website journeys: landing page entry, click navigation, chrome and no live submit."""
    findings: list[dict[str, Any]] = []
    unconvincing_journeys = 0

    for j in journeys:
        jid = str(j["id"])
        vp_w = int(j.get("viewport_width_px", 0))
        has_chrome = bool(j.get("has_browser_chrome", False))
        shows_entry = bool(j.get("shows_entry_landing", False))
        shows_click = bool(j.get("shows_click_transition", False))
        urls = [str(u) for u in j.get("navigated_urls", [])]
        submitted = bool(j.get("form_submitted", False))
        bad = False

        if submitted:
            bad = True
            findings.append({
                "code": "live_form_submitted",
                "severity": "blocker",
                "item_id": jid,
                "detail": f"Web journey '{jid}' submitted a live form; made-up demos must clear without submitting.",
            })
        if vp_w < min_desktop_width_px:
            bad = True
            findings.append({
                "code": "narrow_cropped_web_capture",
                "severity": "major",
                "item_id": jid,
                "detail": (
                    f"Web journey '{jid}' captured at {vp_w}px width (< {min_desktop_width_px}px desktop minimum), "
                    "resembling a cropped mockup card rather than a real website."
                ),
            })
        if not has_chrome:
            bad = True
            findings.append({
                "code": "missing_browser_chrome",
                "severity": "major",
                "item_id": jid,
                "detail": f"Web journey '{jid}' omits visible desktop browser tab and URL bar chrome.",
            })
        if not shows_entry or not shows_click or len(urls) < 2:
            bad = True
            findings.append({
                "code": "missing_homepage_click_provenance",
                "severity": "major",
                "item_id": jid,
                "detail": (
                    f"Web journey '{jid}' jumps mid-page without showing entry landing and interactive "
                    f"click transition (urls={urls})."
                ),
            })
        if bad:
            unconvincing_journeys += 1

    verdict = "fail" if unconvincing_journeys > 0 else "pass"
    return {
        "journey_count": len(journeys),
        "unconvincing_journeys": unconvincing_journeys,
        "findings": findings,
        "verdict": verdict,
    }


def evaluate_frosted_caption_geometry(
    caption_band: dict[str, Any],
    cues: list[dict[str, Any]],
    *,
    frame_width: int = 1920,
    band_top_y: int = 924,
    band_bottom_y: int = 1080,
    center_tol_px: float = 2.0,
    min_margin_px: float = 24.0,
    max_chars_per_line: int = 42,
) -> dict[str, Any]:
    """Verify burned-in frosted-glass rounded-pill captions centered in the lower horizontal band."""
    findings: list[dict[str, Any]] = []
    burned_in = bool(caption_band.get("burned_into_video", False))
    native_fullscreen = bool(caption_band.get("uses_native_track_in_fullscreen", False))
    frosted_pill = bool(caption_band.get("has_frosted_glass_pill", False))
    radius_px = float(caption_band.get("rounded_radius_px", 0.0))
    cx = float(caption_band.get("pill_center_x", 0.0))
    cy = float(caption_band.get("pill_center_y", 0.0))
    pill_top_y = float(caption_band.get("pill_top_y", cy))
    pill_bottom_y = float(caption_band.get("pill_bottom_y", cy))
    pill_left_x = float(caption_band.get("pill_left_x", min_margin_px))
    pill_right_x = float(caption_band.get("pill_right_x", frame_width - min_margin_px))

    expected_cx = frame_width / 2.0
    expected_cy = (band_top_y + band_bottom_y) / 2.0
    dx = round(abs(cx - expected_cx), 3)
    dy = round(abs(cy - expected_cy), 3)

    if not burned_in:
        findings.append({
            "code": "captions_not_burned_in",
            "severity": "major",
            "item_id": "caption_band",
            "detail": "Primary video relies on external caption rendering instead of deterministic burned-in captions.",
        })
    if native_fullscreen:
        findings.append({
            "code": "fullscreen_native_cue_leak",
            "severity": "major",
            "item_id": "caption_band",
            "detail": "Fullscreen mode activates native browser ::cue rendering, breaking lower-band centering and styling.",
        })
    if not frosted_pill or radius_px < 12.0:
        findings.append({
            "code": "unrounded_or_unfrosted_caption_box",
            "severity": "major",
            "item_id": "caption_band",
            "detail": f"Caption pill lacks frosted-glass rounded styling (frosted={frosted_pill}, radius={radius_px:.1f}px).",
        })
    if dx > center_tol_px or dy > center_tol_px:
        findings.append({
            "code": "caption_band_off_center",
            "severity": "major",
            "item_id": "caption_band",
            "detail": (
                f"Caption pill center ({cx:.1f}, {cy:.1f}) deviates from lower-band midpoint "
                f"({expected_cx:.1f}, {expected_cy:.1f}) by ({dx:.1f}px, {dy:.1f}px) > {center_tol_px:.1f}px."
            ),
        })
    if pill_top_y < band_top_y + 6.0 or pill_bottom_y > band_bottom_y - 6.0:
        findings.append({
            "code": "caption_straddles_stage_boundary",
            "severity": "blocker",
            "item_id": "caption_band",
            "detail": (
                f"Caption pill vertical span [{pill_top_y:.1f}, {pill_bottom_y:.1f}] crosses or crowds "
                f"lower horizontal band [{band_top_y}, {band_bottom_y}]."
            ),
        })
    if pill_left_x < min_margin_px or (frame_width - pill_right_x) < min_margin_px:
        findings.append({
            "code": "caption_margin_crowded",
            "severity": "major",
            "item_id": "caption_band",
            "detail": f"Caption pill horizontal span [{pill_left_x:.1f}, {pill_right_x:.1f}] violates {min_margin_px:.1f}px margin.",
        })

    orphan_cues = 0
    for cue in cues:
        cid = str(cue["id"])
        lines = [ln.strip() for ln in str(cue.get("text", "")).splitlines() if ln.strip()]
        if len(lines) > 2:
            orphan_cues += 1
            findings.append({
                "code": "caption_exceeds_two_lines",
                "severity": "major",
                "item_id": cid,
                "detail": f"Caption '{cid}' wraps to {len(lines)} lines (maximum 2).",
            })
        for ln in lines:
            if len(ln) > max_chars_per_line:
                orphan_cues += 1
                findings.append({
                    "code": "caption_line_too_wide",
                    "severity": "minor",
                    "item_id": cid,
                    "detail": f"Caption '{cid}' line '{ln}' is {len(ln)} chars (> {max_chars_per_line}).",
                })
        if len(lines) == 2:
            w0 = _words(lines[0])
            w1 = _words(lines[1])
            if (len(w0) + len(w1)) >= 5 and (len(w0) == 1 or len(w1) == 1):
                orphan_cues += 1
                findings.append({
                    "code": "caption_orphan_line_break",
                    "severity": "minor",
                    "item_id": cid,
                    "detail": f"Caption '{cid}' leaves a 1-word orphan across two lines: {lines!r}.",
                })

    verdict = "pass"
    if any(f["severity"] in ("blocker", "major") for f in findings):
        verdict = "fail"
    elif findings:
        verdict = "warn"

    return {
        "center_offset_x_px": dx,
        "center_offset_y_px": dy,
        "orphan_cues": orphan_cues,
        "findings": findings,
        "verdict": verdict,
    }


def compile_scene_cognitive_report(
    *,
    media_sha256: str,
    dwell_and_transitions: dict[str, Any],
    slide_stability: dict[str, Any],
    cognitive_load: dict[str, Any],
    web_provenance: dict[str, Any],
    caption_geometry: dict[str, Any],
) -> dict[str, Any]:
    """Bind all five multi-frame and cognitive checks into one digest-pinned QA report."""
    if not HEX64_RE.search(media_sha256):
        raise ValueError("media_sha256 must be a 64-char lowercase hex SHA-256 digest")

    verdicts = [
        dwell_and_transitions["verdict"],
        slide_stability["verdict"],
        cognitive_load["verdict"],
        web_provenance["verdict"],
        caption_geometry["verdict"],
    ]
    if "fail" in verdicts:
        overall = "fail"
    elif "warn" in verdicts:
        overall = "warn"
    else:
        overall = "pass"

    return {
        "media_sha256": media_sha256,
        "min_shot_s": float(dwell_and_transitions["min_shot_s"]),
        "flash_shots": int(dwell_and_transitions["flash_shots"]),
        "ghost_transitions": int(dwell_and_transitions["ghost_transitions"]),
        "drifting_static_scenes": int(slide_stability["drifting_static_scenes"]),
        "unreadable_items": int(cognitive_load["unreadable_items"]),
        "cognitive_conflicts": int(cognitive_load["cognitive_conflicts"]),
        "unconvincing_journeys": int(web_provenance["unconvincing_journeys"]),
        "caption_center_offset_x_px": float(caption_geometry["center_offset_x_px"]),
        "caption_center_offset_y_px": float(caption_geometry["center_offset_y_px"]),
        "overall_verdict": overall,
    }
