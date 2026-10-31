"""Align per-frame segmentation masks, speech-to-text word timings, and caption safe zones."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# Normalized [x, y, w, h] safe zones in [0.0, 1.0] frame coordinates, ordered by default preference.
DEFAULT_SAFE_ZONES: list[dict[str, Any]] = [
    {"zone_id": "bottom_band", "bbox": [0.08, 0.78, 0.84, 0.14], "priority": 1},
    {"zone_id": "top_band", "bbox": [0.08, 0.08, 0.84, 0.14], "priority": 2},
    {"zone_id": "lower_left", "bbox": [0.06, 0.68, 0.42, 0.18], "priority": 3},
    {"zone_id": "lower_right", "bbox": [0.52, 0.68, 0.42, 0.18], "priority": 4},
    {"zone_id": "upper_left", "bbox": [0.06, 0.10, 0.42, 0.18], "priority": 5},
    {"zone_id": "upper_right", "bbox": [0.52, 0.10, 0.42, 0.18], "priority": 6},
]

_WORD_CLEAN_RE = re.compile(r"[^a-z0-9]+")


def _box_area(box: list[float] | tuple[float, float, float, float]) -> float:
    return max(0.0, float(box[2])) * max(0.0, float(box[3]))


def box_intersection_area(
    box_a: list[float] | tuple[float, float, float, float],
    box_b: list[float] | tuple[float, float, float, float],
) -> float:
    """Compute intersection area of two [x, y, w, h] boxes."""
    ax1, ay1, aw, ah = (float(v) for v in box_a)
    bx1, by1, bw, bh = (float(v) for v in box_b)
    ax2, ay2 = ax1 + max(0.0, aw), ay1 + max(0.0, ah)
    bx2, by2 = bx1 + max(0.0, bw), by1 + max(0.0, bh)
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    return ix * iy


def box_iou(
    box_a: list[float] | tuple[float, float, float, float],
    box_b: list[float] | tuple[float, float, float, float],
) -> float:
    """Compute Intersection-over-Union (IoU) in [0.0, 1.0] for two [x, y, w, h] boxes."""
    inter = box_intersection_area(box_a, box_b)
    if inter <= 0.0:
        return 0.0
    union = _box_area(box_a) + _box_area(box_b) - inter
    return round(inter / union, 6) if union > 0.0 else 0.0


def mask_intrusion_ratio(
    zone_box: list[float] | tuple[float, float, float, float],
    mask_box: list[float] | tuple[float, float, float, float],
) -> float:
    """Fraction of zone_box area covered by mask_box."""
    z_area = _box_area(zone_box)
    if z_area <= 0.0:
        return 0.0
    return round(min(1.0, box_intersection_area(zone_box, mask_box) / z_area), 6)


def polygon_to_bbox_and_area(points: list[list[float]] | list[tuple[float, float]]) -> tuple[list[float], float]:
    """Convert polygon [[x, y], ...] into tight [x, y, w, h] bounding box and Shoelace area."""
    if len(points) < 3:
        raise ValueError("Polygon requires at least 3 vertices")
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    shoelace = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = float(points[i][0]), float(points[i][1])
        x2, y2 = float(points[(i + 1) % n][0]), float(points[(i + 1) % n][1])
        shoelace += x1 * y2 - x2 * y1
    return [round(min_x, 6), round(min_y, 6), round(max_x - min_x, 6), round(max_y - min_y, 6)], round(abs(shoelace) * 0.5, 6)


def _normalize_mask_box(
    mask: dict[str, Any],
    frame_width: float,
    frame_height: float,
) -> list[float]:
    if "bbox" in mask:
        raw = [float(v) for v in mask["bbox"]]
    elif "polygon" in mask:
        raw, _ = polygon_to_bbox_and_area(mask["polygon"])
    else:
        raise ValueError(f"Mask missing bbox or polygon: {mask}")

    # Normalize pixel coordinates if any coordinate > 1.0 and frame dimensions are > 1.0
    if any(v > 1.0 for v in raw) and frame_width > 1.0 and frame_height > 1.0:
        return [
            round(raw[0] / frame_width, 6),
            round(raw[1] / frame_height, 6),
            round(raw[2] / frame_width, 6),
            round(raw[3] / frame_height, 6),
        ]
    return [round(v, 6) for v in raw]


def group_words_into_utterances(
    words: list[dict[str, Any]],
    max_words: int = 8,
    max_pause_s: float = 0.45,
    min_word_confidence: float = 0.70,
) -> list[dict[str, Any]]:
    """Group word-level speech timings into caption-sized utterance spans."""
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (float(w["start_s"]), float(w["end_s"])))
    utterances: list[dict[str, Any]] = []
    bucket: list[dict[str, Any]] = []

    def _flush(items: list[dict[str, Any]]) -> None:
        if not items:
            return
        low_conf = [str(w["word"]) for w in items if float(w.get("confidence", 1.0)) < min_word_confidence]
        utterances.append(
            {
                "utterance_id": f"utt.{len(utterances) + 1:03d}",
                "text": " ".join(str(w["word"]).strip() for w in items if str(w["word"]).strip()),
                "start_s": round(float(items[0]["start_s"]), 3),
                "end_s": round(float(items[-1]["end_s"]), 3),
                "word_count": len(items),
                "min_confidence": round(min(float(w.get("confidence", 1.0)) for w in items), 4),
                "low_confidence_words": low_conf,
                "words": items,
            }
        )

    for w in ordered:
        start_s = float(w["start_s"])
        end_s = float(w["end_s"])
        if end_s < start_s:
            raise ValueError(f"Word end_s ({end_s}) precedes start_s ({start_s})")
        if bucket:
            pause = start_s - float(bucket[-1]["end_s"])
            if len(bucket) >= max_words or pause > max_pause_s:
                _flush(bucket)
                bucket = []
        bucket.append(w)
    _flush(bucket)
    return utterances


def align_multimodal_timeline(
    timeline: dict[str, Any],
    max_drift_ms: float = 250.0,
    max_intrusion: float = 0.05,
    min_word_confidence: float = 0.70,
) -> dict[str, Any]:
    """Align speech words, segmentation masks, visual event cues, and non-occluding safe zones."""
    frame_w = float(timeline.get("frame_width", 1.0))
    frame_h = float(timeline.get("frame_height", 1.0))
    safe_zones = list(timeline.get("safe_zones") or DEFAULT_SAFE_ZONES)
    hud_exclusions = [
        _normalize_mask_box({"bbox": b}, frame_w, frame_h)
        for b in (timeline.get("hud_exclusion_boxes") or [])
    ]

    norm_masks: list[dict[str, Any]] = []
    first_seen_by_label: dict[str, float] = {}
    for m in timeline.get("mask_frames") or []:
        t_s = float(m["t_s"])
        label = _WORD_CLEAN_RE.sub("", str(m.get("label", "foreground")).lower()) or "foreground"
        conf = float(m.get("confidence", 1.0))
        nbox = _normalize_mask_box(m, frame_w, frame_h)
        norm_masks.append({"t_s": t_s, "label": label, "confidence": conf, "bbox": nbox})
        if label not in first_seen_by_label or t_s < first_seen_by_label[label]:
            first_seen_by_label[label] = t_s

    utterances = group_words_into_utterances(
        list(timeline.get("words") or []),
        max_words=int(timeline.get("max_words_per_caption", 8)),
        max_pause_s=float(timeline.get("max_pause_s", 0.45)),
        min_word_confidence=min_word_confidence,
    )

    placements: list[dict[str, Any]] = []
    av_sync_events: list[dict[str, Any]] = []
    drift_violations = 0
    occlusion_conflicts = 0

    for utt in utterances:
        u_start = utt["start_s"]
        u_end = utt["end_s"]
        # Masks within [u_start - 0.05, u_end + 0.05]
        active_masks = [m for m in norm_masks if (u_start - 0.05) <= m["t_s"] <= (u_end + 0.05)]

        # Evaluate candidate safe zones
        zone_scores: list[dict[str, Any]] = []
        for z in safe_zones:
            zbox = _normalize_mask_box(z, frame_w, frame_h)
            hud_hit = max((mask_intrusion_ratio(zbox, hbox) for hbox in hud_exclusions), default=0.0)
            max_mask_hit = max((mask_intrusion_ratio(zbox, m["bbox"]) for m in active_masks), default=0.0)
            max_iou = max((box_iou(zbox, m["bbox"]) for m in active_masks), default=0.0)
            combined_intrusion = round(max(hud_hit, max_mask_hit), 6)
            zone_scores.append(
                {
                    "zone_id": z["zone_id"],
                    "bbox": zbox,
                    "priority": int(z.get("priority", 99)),
                    "max_intrusion_ratio": combined_intrusion,
                    "max_mask_iou": max_iou,
                    "safe": combined_intrusion <= max_intrusion,
                }
            )

        # Prefer safe zones sorted by priority, else lowest intrusion ratio
        safe_candidates = [zs for zs in zone_scores if zs["safe"]]
        if safe_candidates:
            safe_candidates.sort(key=lambda zs: (zs["priority"], zs["max_intrusion_ratio"]))
            chosen = safe_candidates[0]
            conflict = False
        else:
            zone_scores.sort(key=lambda zs: (zs["max_intrusion_ratio"], zs["priority"]))
            chosen = zone_scores[0]
            conflict = True
            occlusion_conflicts += 1

        # Check spoken token -> mask onset synchronization
        for w in utt["words"]:
            tok = _WORD_CLEAN_RE.sub("", str(w["word"]).lower())
            if tok and tok in first_seen_by_label:
                mask_t = first_seen_by_label[tok]
                offset_ms = round((float(w["start_s"]) - mask_t) * 1000.0, 2)
                drifted = abs(offset_ms) > max_drift_ms
                if drifted:
                    drift_violations += 1
                av_sync_events.append(
                    {
                        "label": tok,
                        "word_start_s": round(float(w["start_s"]), 3),
                        "mask_onset_s": round(mask_t, 3),
                        "av_offset_ms": offset_ms,
                        "drift_exceeded": drifted,
                    }
                )

        placements.append(
            {
                "utterance_id": utt["utterance_id"],
                "text": utt["text"],
                "start_s": u_start,
                "end_s": u_end,
                "selected_zone_id": chosen["zone_id"],
                "selected_bbox": chosen["bbox"],
                "max_intrusion_ratio": chosen["max_intrusion_ratio"],
                "max_mask_iou": chosen["max_mask_iou"],
                "occlusion_conflict": conflict,
                "low_confidence_words": utt["low_confidence_words"],
            }
        )

    digest_input = json.dumps(placements, sort_keys=True, separators=(",", ":"))
    plan_sha = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

    return {
        "clip_id": str(timeline.get("clip_id") or "clip-01"),
        "alignment_plan_sha256": plan_sha,
        "utterance_count": len(utterances),
        "mask_frame_count": len(norm_masks),
        "occlusion_conflicts": occlusion_conflicts,
        "av_drift_violations": drift_violations,
        "ready_for_render": occlusion_conflicts == 0 and drift_violations == 0,
        "placements": placements,
        "av_sync_events": av_sync_events,
    }
