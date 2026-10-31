"""Browser window and tab chrome layout calculator and safe-area / caption-band collision verifier."""

from __future__ import annotations

from typing import Any, Sequence

# 1080p canonical composition zones:
# Safe upper stage: x in [96, 1824], y in [72, 820]
# Separation gutter: y in [820, 836] (16 px breathing strip)
# Dedicated lower caption band: x in [0, 1920], y in [836, 1080]
STAGE_SAFE_BOX = (96, 72, 1824, 820)
CAPTION_BAND_BOX = (0, 836, 1920, 1080)


def _overlap_box(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float, float] | None:
    ix0 = max(float(a[0]), float(b[0]))
    iy0 = max(float(a[1]), float(b[1]))
    ix1 = min(float(a[2]), float(b[2]))
    iy1 = min(float(a[3]), float(b[3]))
    if ix1 <= ix0 or iy1 <= iy0:
        return None
    return (round(ix0, 2), round(iy0, 2), round(ix1, 2), round(iy1, 2))


def compute_browser_chrome_layout(
    outer_box: Sequence[float],
    tabs: Sequence[str],
    *,
    active_tab_index: int = 0,
    url: str = "https://workspace.example/overview",
    tab_bar_height_px: int = 42,
    toolbar_height_px: int = 40,
    border_px: int = 2,
) -> dict[str, Any]:
    """Compute realistic desktop browser window, traffic-light controls, tab strip, URL bar and viewport."""
    x0, y0, x1, y1 = [int(round(v)) for v in outer_box]
    width = x1 - x0
    height = y1 - y0
    if width < 480 or height < 240:
        raise ValueError(f"browser outer_box {outer_box} is smaller than 480x240 minimum")
    if not tabs:
        raise ValueError("browser chrome requires at least one tab title")
    if not (0 <= active_tab_index < len(tabs)):
        raise ValueError("active_tab_index out of range")

    traffic_lights = [
        {"role": "close", "center": [x0 + 22, y0 + tab_bar_height_px // 2], "radius_px": 6},
        {"role": "minimize", "center": [x0 + 42, y0 + tab_bar_height_px // 2], "radius_px": 6},
        {"role": "expand", "center": [x0 + 62, y0 + tab_bar_height_px // 2], "radius_px": 6},
    ]

    tabs_start_x = x0 + 88
    avail_tabs_w = max(160, (x1 - 24) - tabs_start_x)
    per_tab_w = min(240, max(120, avail_tabs_w // len(tabs)))
    tab_rects = []
    for idx, title in enumerate(tabs):
        tx0 = tabs_start_x + idx * per_tab_w
        tx1 = min(x1 - 16, tx0 + per_tab_w - 6)
        tab_rects.append({
            "index": idx,
            "title": title,
            "active": idx == active_tab_index,
            "box": [tx0, y0 + 6, tx1, y0 + tab_bar_height_px],
            "font_px": 18,
        })

    toolbar_y0 = y0 + tab_bar_height_px
    toolbar_y1 = toolbar_y0 + toolbar_height_px
    omnibox = {
        "url": url,
        "box": [x0 + 96, toolbar_y0 + 6, x1 - 32, toolbar_y1 - 6],
        "font_px": 18,
    }

    viewport_box = [x0 + border_px, toolbar_y1, x1 - border_px, y1 - border_px]
    return {
        "outer_box": [x0, y0, x1, y1],
        "tab_bar_box": [x0, y0, x1, toolbar_y0],
        "traffic_lights": traffic_lights,
        "tabs": tab_rects,
        "toolbar_box": [x0, toolbar_y0, x1, toolbar_y1],
        "omnibox": omnibox,
        "viewport_box": viewport_box,
        "viewport_width": viewport_box[2] - viewport_box[0],
        "viewport_height": viewport_box[3] - viewport_box[1],
    }


def verify_safe_area_and_caption_band(
    elements: Sequence[dict[str, Any]],
    *,
    safe_box: tuple[int, int, int, int] = STAGE_SAFE_BOX,
    caption_band: tuple[int, int, int, int] = CAPTION_BAND_BOX,
) -> dict[str, Any]:
    """Verify stage elements stay inside `x: 96..1824, y: 72..820` and never collide with `y: 836..1080`.

    Elements with `role == "caption"` must sit completely inside `caption_band` (`y: 836..1080`)
    and inside horizontal title-safe bounds (`x: 96..1824`). All other stage elements (`browser`,
    `card`, `callout`, `title`, `badge`) must stay inside `safe_box` and never enter `caption_band`.
    """
    sx0, sy0, sx1, sy1 = safe_box
    _, cy0, _, cy1 = caption_band
    violations: list[dict[str, Any]] = []

    for el in elements:
        eid = str(el["id"])
        role = str(el.get("role", "card"))
        bx0, by0, bx1, by1 = [float(v) for v in el["box"]]

        if role == "caption":
            if by0 < cy0 or by1 > cy1 or bx0 < sx0 or bx1 > sx1:
                violations.append({
                    "id": eid,
                    "role": role,
                    "kind": "caption_outside_band",
                    "severity": "major",
                    "box": [bx0, by0, bx1, by1],
                    "allowed_box": [sx0, cy0, sx1, cy1],
                })
            continue

        cap_hit = _overlap_box((bx0, by0, bx1, by1), caption_band)
        if cap_hit is not None:
            area = (cap_hit[2] - cap_hit[0]) * (cap_hit[3] - cap_hit[1])
            violations.append({
                "id": eid,
                "role": role,
                "kind": "caption_band_collision",
                "severity": "blocker",
                "box": [bx0, by0, bx1, by1],
                "overlap_box": list(cap_hit),
                "overlap_area_px": round(area, 1),
            })

        out_sides = []
        if bx0 < sx0:
            out_sides.append("left")
        if by0 < sy0:
            out_sides.append("top")
        if bx1 > sx1:
            out_sides.append("right")
        if by1 > sy1:
            out_sides.append("bottom")
        if out_sides:
            violations.append({
                "id": eid,
                "role": role,
                "kind": "outside_safe_stage",
                "severity": "major" if cap_hit is not None or bx0 < 0 or bx1 > 1920 or by0 < 0 else "minor",
                "box": [bx0, by0, bx1, by1],
                "sides": out_sides,
                "safe_box": list(safe_box),
            })

    return {
        "safe_box": list(safe_box),
        "caption_band": list(caption_band),
        "checked_elements": len(elements),
        "valid": len(violations) == 0,
        "violations": violations,
    }
