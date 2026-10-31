"""The detector spec: sampling, safe areas, every threshold, each detector's questions and the severity scale.

The pack's `spec.detectors` noun holds this same document; a test keeps the two equal. A requester may
override any value with a JSON file; the findings record the spec digest that applied.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

SPEC_FORMAT = "frame-qa.spec.v1"

SEVERITIES = ("blocker", "major", "minor", "note")
# The video review pack's severity guide maps its levels onto findings to fixes like this.
PRIORITY = {"blocker": "P1", "major": "P2", "minor": "P3", "note": None}

DETECTORS = (
    "cut_off_content", "cut_off_windows", "overlaps", "small_text", "transitions",
    "freezes_and_motion", "caption_collisions", "contrast", "layered_edges",
)

DEFAULT_SPEC: dict[str, Any] = {
    "format": SPEC_FORMAT,
    "sampling": {
        "temporal_every_frames": 1,
        "spatial_every_frames": 2,
        "why_every_second_frame": (
            "Text is detected and measured on every second frame, 15 times a second at 30 fps: a text layout "
            "that lasts two frames (67 ms) is always sampled, and anything shorter is a flash that the "
            "transition detector, which reads every frame, reports. Edges, panels and border bands are "
            "measured on every frame."
        ),
        "thumb_width_px": 320,
        "panel_scale": 2,
    },
    "text": {
        "engine": "auto",
        "box_thresh": 0.5,
        "min_line_px": 6,
        "cap_em": 0.71,
        "font_size_rule": (
            "Estimated font size is the line's cap or ascender height divided by 0.71, the median cap-to-em "
            "ratio measured on IBM Plex Sans, Space Grotesk and JetBrains Mono from 12 to 72 px (range 0.67 "
            "to 0.77). A line with only x-height letters reads about 25 percent small, so such a line takes "
            "its neighbour's size when the two share a block."
        ),
        "reference_height_px": 1080,
    },
    "safe_areas": {
        "title_safe_share": 0.05,
        "action_safe_share": 0.035,
        "touch_px": 2,
        "rule": "Title-safe keeps text 5 percent in from every edge and action-safe keeps any content 3.5 percent in, of the frame's width for the sides and of its height for the top and bottom.",
    },
    "detectors": {
        "cut_off_content": {
            "questions": [
                "Does any text touch or run off a frame edge?",
                "Is any text inside the 3.5 percent action-safe margin?",
                "Is any text inside the 5 percent title-safe margin?",
                "Does interface content run off a frame edge, by edges crossing the frame's outermost pixels?",
            ],
            "thresholds": {"border_step_levels": 24, "ui_min_crossings": 10, "ui_min_band_density": 0.03, "min_duration_s": 0.2},
            "severity": {"text_at_edge": "major when it lasts 0.5 s or more, else minor", "text_in_action_margin": "minor",
                          "text_in_title_margin": "note", "ui_off_edge": "note"},
        },
        "cut_off_windows": {
            "questions": [
                "Does a window, card or panel reach the frame edge, so part of it is outside the frame?",
                "Is text inside that panel cut by the same edge?",
            ],
            "thresholds": {"min_area_share": 0.01, "min_side_px": 60, "rect_min": 0.88, "flat_std": 2.5, "step_levels": 6,
                           "edge_tolerance_px": 10, "min_duration_s": 0.3},
            "severity": {"panel_at_edge": "minor", "panel_at_edge_with_cut_text": "major"},
        },
        "overlaps": {
            "questions": [
                "Do two text lines overlap each other?",
                "Does a callout chip or label cover part of a line of page text?",
            ],
            "thresholds": {"text_overlap_min_share": 0.10, "text_overlap_major_share": 0.30, "duplicate_iou": 0.85,
                           "chip_min_overlap_px": 2, "chip_major_share": 0.25, "chip_max_area_share": 0.03,
                           "chip_color_step": 12, "min_duration_s": 0.2},
            "severity": {"text_on_text": "major from 30 percent of the smaller line, else minor",
                          "chip_covers_text": "major from 25 percent of the covered line's height, else minor"},
        },
        "small_text": {
            "questions": [
                "Is any text smaller than 24 px at 1080p?",
                "Is any text smaller than 16 px at 1080p?",
                "Would any text be smaller than 12 px on a 390 px wide phone screen?",
            ],
            "thresholds": {"min_font_px": 24, "major_font_px": 16, "phone_width_px": 390, "min_phone_px": 12,
                           "min_glyphs": 2, "min_duration_s": 0.2},
            "severity": {"under_16_px": "major", "under_24_px": "minor", "under_12_px_on_phone": "note"},
        },
        "transitions": {
            "questions": [
                "Where are the hard cuts and the dissolves?",
                "Does a dissolve blend two text-heavy frames into a double exposure?",
                "Is there a flash frame: one or two frames unlike both neighbours?",
                "Is there a jump cut inside a shot: an abrupt change with the same layout either side?",
                "Are there black or blank frames?",
            ],
            "thresholds": {"change_level": 3.0, "change_share": 0.003, "cut_level": 12.0, "cut_share": 0.4,
                           "dissolve_min_frames": 3, "dissolve_max_frames": 60, "blend_max_residual": 0.12,
                           "blend_max_error": 0.25, "blend_min_share": 0.002, "blend_min_distinct": 0.2,
                           "text_heavy_share": 0.02, "text_ghost_overlap": 0.15,
                           "flash_max_frames": 2, "flash_min_level": 12.0, "flash_return_share": 0.25,
                           "jump_same_layout_share": 0.6, "jump_min_changed_share": 0.01,
                           "black_max_luma": 16, "black_max_p99": 40, "blank_max_std": 1.5, "blank_max_step": 6},
            "severity": {"double_exposure": "major from 6 frames, else minor", "flash_frame": "major",
                          "jump_cut": "minor when the frame jumps, note when an element pops in",
                          "black_or_blank": "major from 0.5 s, minor for a shorter run, note at the very start or end",
                          "cut_or_dissolve": "note"},
        },
        "freezes_and_motion": {
            "questions": [
                "Is the picture frozen for more than 1.5 s?",
                "Does the content stay still, apart from a camera drift, for more than 1.5 s?",
                "Does text move fast enough to hurt reading while it is on screen?",
                "Is there a sudden spike in motion speed?",
            ],
            "thresholds": {"freeze_max_level": 0.12, "freeze_min_s": 1.5, "still_lag_frames": 15,
                           "still_change_level": 24, "still_max_changed_share": 0.004, "still_min_s": 1.5,
                           "still_minor_s": 6.0, "text_speed_minor_px": 3.0, "text_speed_major_px": 8.0,
                           "text_motion_min_s": 0.3, "spike_ratio": 4.0, "spike_min_px": 4.0,
                           "shift_min_response": 0.3, "shift_min_gain": 0.5},
            "severity": {"freeze": "minor from 1.5 s, major from 4 s", "near_static": "note, minor from 6 s",
                          "text_motion": "minor from 3 px a frame, major from 8 px a frame", "motion_spike": "minor"},
        },
        "caption_collisions": {
            "questions": [
                "While a caption cue shows, is there text or proof in the bottom 18 percent of the frame?",
                "Does that text sit where the player draws the caption?",
            ],
            "thresholds": {"band_share": 0.18, "caption_font_share": 0.045, "char_em": 0.52, "line_gap_em": 1.25,
                           "min_glyphs": 2, "min_duration_s": 0.2},
            "severity": {"under_caption_box": "major", "in_band_beside_caption": "minor"},
        },
        "contrast": {
            "questions": [
                "Is any text below 4.5 to 1 against its background, or below 3 to 1 when it is 24 px or larger?",
                "Is any text below 2 to 1?",
            ],
            "thresholds": {"normal_min": 4.5, "large_min": 3.0, "large_font_px": 24, "major_below": 2.0,
                           "min_glyphs": 3, "min_line_px": 8, "min_duration_s": 0.2},
            "severity": {"below_2": "major", "below_minimum": "minor"},
        },
        "layered_edges": {
            "questions": [
                "Is the frame busy: dense edges at three scales at once?",
                "Does content cross a panel's boundary, spilling out of its container?",
            ],
            "thresholds": {"canny_low": 50, "canny_high": 150, "busy_density": [0.07, 0.10, 0.14], "busy_min_s": 1.0,
                           "spill_min_px": 8, "spill_min_share": 0.10, "spill_major_share": 0.25, "min_duration_s": 0.2},
            "severity": {"busy_frame": "note", "spill": "minor, major from 25 percent outside"},
        },
    },
    "clustering": {
        "max_gap_frames": 4,
        "match_iou": 0.3,
        "rule": "Hits of one detector and kind on nearby frames whose boxes overlap by at least 0.3 IoU are one finding; a gap of up to 4 frames is bridged.",
    },
    "severity_scale": {
        "levels": list(SEVERITIES),
        "findings_to_fixes": {"blocker": "P1", "major": "P2", "minor": "P3", "note": "none"},
        "source": "the video review pack's severity guide",
    },
}


def merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_spec(path: str | Path | None = None) -> dict:
    spec = copy.deepcopy(DEFAULT_SPEC)
    if path:
        override = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(override, dict):
            raise ValueError("a spec override is a JSON object")
        spec = merge(spec, override)
    if spec.get("format") != SPEC_FORMAT:
        raise ValueError(f"spec format must be {SPEC_FORMAT}")
    for name in DETECTORS:
        if name not in spec["detectors"]:
            raise ValueError(f"spec misses detector {name}")
    return spec


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def spec_digest(spec: dict) -> str:
    return hashlib.sha256(canonical(spec).encode("utf-8")).hexdigest()


def thresholds(spec: dict, detector: str) -> dict:
    return spec["detectors"][detector]["thresholds"]
