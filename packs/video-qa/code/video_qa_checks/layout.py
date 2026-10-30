"""Layout checks for text whose size and place are known from the stage, the layout or a measurement.

legibility() is a proxy, not a reading test. It takes each text item's font size in output pixels (or a
source size and the scale that maps it into the frame), then asks two questions: is it at least a
fraction of the frame height for its role, and how many CSS pixels tall would it be on the smallest
display the cut is planned for? The second floor defaults to 12 px, the size below which a former
Lighthouse audit called web text illegible on phones. It knows nothing about weight, stroke, motion,
blur or how busy the picture is behind the text; a person still looks at the frames.

contrast_ratio() is WCAG's relative-luminance ratio. reading_time_s() is 0.5 s plus 3 words per second,
the rule one production used for text a viewer must read. check_boxes() keeps text inside a safe
rectangle and clear of keep-out boxes, such as a platform's buttons.
"""

from __future__ import annotations

import math
from typing import Any

ROLE_FLOORS = {"title": 0.045, "caption": 0.026, "body": 0.022, "label": 0.017, "fine_print": 0.012}
DEFAULT_MIN_CSS_PX = 12.0
CAP_RATIO = 0.70


def font_px(item: dict[str, Any]) -> float:
    """An item's font size in output pixels, from px, or from source_px times scale; cap heights convert."""
    if "px" in item:
        size = float(item["px"])
    elif "source_px" in item:
        size = float(item["source_px"]) * float(item.get("scale", 1.0))
    else:
        raise ValueError(f"{item.get('id')}: give px, or source_px with scale")
    if item.get("measure", "font_px") == "cap_px":
        size /= CAP_RATIO
    return size


def legibility(items: list[dict[str, Any]], frame: dict[str, int], displays: list[dict[str, Any]],
               min_css_px: float = DEFAULT_MIN_CSS_PX, floors: dict[str, float] | None = None) -> dict[str, Any]:
    """Per item: size in output pixels, share of frame height and CSS pixels on each planned display."""
    table = {**ROLE_FLOORS, **(floors or {})}
    smallest = min(displays, key=lambda d: d["width_px"])
    rows, problems = [], []
    for item in items:
        size = font_px(item)
        share = size / frame["height"]
        css = {d["name"]: round(size * d["width_px"] / frame["width"], 2) for d in displays}
        floor = table.get(item.get("role", "body"), table["body"])
        need_px = math.ceil(min_css_px * frame["width"] / smallest["width_px"] * 10) / 10
        verdicts = []
        if share < floor:
            verdicts.append("below_role_floor")
        if css[smallest["name"]] < min_css_px:
            verdicts.append("too_small_on_smallest_display")
        rows.append({"id": item["id"], "role": item.get("role", "body"), "font_px": round(size, 2),
                     "frame_share": round(share, 4), "role_floor": floor, "css_px": css,
                     "needs_px_for_smallest_display": need_px, "problems": verdicts})
        problems += [f"{item['id']}: {v}" for v in verdicts]
    return {"frame": frame, "smallest_display": smallest["name"], "min_css_px": min_css_px, "items": rows,
            "problems": problems}


def _luminance(color: str) -> float:
    value = color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"colors are #rrggbb, not {color!r}")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(foreground: str, background: str) -> float:
    a, b = _luminance(foreground), _luminance(background)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio of two sRGB colors, rounded to two places for reports."""
    return round(_ratio(foreground, background), 2)


def contrast_ok(foreground: str, background: str, px: float, bold: bool = False) -> bool:
    """WCAG AA: 4.5 for normal text, 3.0 for large text (24 px, or 18.66 px when bold).

    The threshold is compared with the unrounded ratio, as WCAG requires: 4.499 to 1 fails 4.5 to 1.
    """
    large = px >= 24 or (bold and px >= 18.66)
    return _ratio(foreground, background) >= (3.0 if large else 4.5)


def words(text: str) -> int:
    return sum(1 for token in text.split() if any(ch.isalnum() for ch in token))


def reading_time_s(text: str) -> float:
    """Seconds a viewer needs for text they must read: 0.5 s plus 3 words per second."""
    return round(0.5 + words(text) / 3, 3)


def check_reading(items: list[dict[str, Any]]) -> list[str]:
    """Items with start_s and end_s that leave the screen before their reading time."""
    problems = []
    for item in items:
        if "start_s" in item and "end_s" in item and item.get("must_read", True):
            shown = item["end_s"] - item["start_s"]
            need = reading_time_s(item.get("text", ""))
            if shown + 1e-9 < need:
                problems.append(f"{item['id']}: on screen {round(shown, 3)} s, needs {need} s to read")
    return problems


def check_boxes(boxes: list[dict[str, Any]], frame: dict[str, int], safe: dict[str, float] | None = None,
                keep_outs: list[dict[str, Any]] | None = None) -> list[str]:
    """Text boxes [x, y, w, h] outside the safe rectangle or overlapping a keep-out box.

    The default safe rectangle is the inner 90 percent of the frame.
    """
    if safe is None:
        safe = {"x": frame["width"] * 0.05, "y": frame["height"] * 0.05,
                "width": frame["width"] * 0.9, "height": frame["height"] * 0.9}
    problems = []
    for box in boxes:
        x, y, w, h = box["box"]
        if x < safe["x"] - 1e-6 or y < safe["y"] - 1e-6 or x + w > safe["x"] + safe["width"] + 1e-6 \
                or y + h > safe["y"] + safe["height"] + 1e-6:
            problems.append(f"{box['id']}: outside the safe area")
        for zone in keep_outs or []:
            dx = min(x + w, zone["x"] + zone["width"]) - max(x, zone["x"])
            dy = min(y + h, zone["y"] + zone["height"]) - max(y, zone["y"])
            if dx > 0 and dy > 0:
                problems.append(f"{box['id']}: overlaps {zone.get('label', 'a keep-out box')}")
    return problems
