"""Pure standard-library declarative SVG compiler with WCAG contrast and label-collision checks."""

from __future__ import annotations

import html
import re
from typing import Any
import xml.etree.ElementTree as ET

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_PALETTE: dict[str, str] = {
    "background": "#FFFFFF",
    "text": "#111827",
    "muted_text": "#374151",
    "primary_mark": "#1D4ED8",
    "accent_mark": "#047857",
    "error_mark": "#B91C1C",
    "grid": "#D1D5DB",
    "node_fill": "#F3F4F6",
    "node_stroke": "#374151",
}


def _relative_luminance(hex_color: str) -> float:
    if not HEX_COLOR_RE.fullmatch(hex_color):
        raise ValueError(f"expected 6-digit #RRGGBB hex color, got {hex_color!r}")
    channels = [int(hex_color[i : i + 2], 16) / 255.0 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(fg: str, bg: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two #RRGGBB colors."""
    la = _relative_luminance(fg)
    lb = _relative_luminance(bg)
    hi, lo = (la, lb) if la >= lb else (lb, la)
    return round((hi + 0.05) / (lo + 0.05), 2)


def _estimate_text_bbox(text: str, x: float, y: float, font_size: float, anchor: str = "start") -> dict[str, Any]:
    width = round(max(1.0, len(text) * font_size * 0.58), 2)
    height = round(font_size * 1.15, 2)
    if anchor == "middle":
        left = x - (width / 2.0)
    elif anchor == "end":
        left = x - width
    else:
        left = x
    top = y - (font_size * 0.85)
    return {
        "text": text,
        "x": round(left, 2),
        "y": round(top, 2),
        "width": width,
        "height": height,
    }


def detect_label_collisions(boxes: list[dict[str, Any]], padding_px: float = 1.0) -> list[dict[str, Any]]:
    """Return every overlapping pair among estimated label bounding boxes."""
    collisions: list[dict[str, Any]] = []
    for i in range(len(boxes)):
        a = boxes[i]
        ax1, ay1 = float(a["x"]) - padding_px, float(a["y"]) - padding_px
        ax2, ay2 = float(a["x"]) + float(a["width"]) + padding_px, float(a["y"]) + float(a["height"]) + padding_px
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            bx1, by1 = float(b["x"]), float(b["y"])
            bx2, by2 = bx1 + float(b["width"]), by1 + float(b["height"])
            overlaps = (ax1 < bx2) and (ax2 > bx1) and (ay1 < by2) and (ay2 > by1)
            if overlaps:
                collisions.append({"first": a["text"], "second": b["text"], "first_index": i, "second_index": j})
    return collisions


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _merged_palette(spec: dict[str, Any]) -> dict[str, str]:
    pal = dict(DEFAULT_PALETTE)
    custom = spec.get("palette") or {}
    if not isinstance(custom, dict):
        raise ValueError("palette must be an object")
    for k, v in custom.items():
        if k not in pal:
            raise ValueError(f"unknown palette slot {k!r}")
        if not HEX_COLOR_RE.fullmatch(str(v)):
            raise ValueError(f"palette[{k!r}] must be #RRGGBB")
        pal[k] = str(v)
    return pal


def _svg_header(width: int, height: int, title_id: str, desc_id: str, title: str, desc: str, bg: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-labelledby="{_esc(title_id)} {_esc(desc_id)}">',
        f'  <title id="{_esc(title_id)}">{_esc(title)}</title>',
        f'  <desc id="{_esc(desc_id)}">{_esc(desc)}</desc>',
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="{bg}" />',
    ]


def _render_forest_plot(spec: dict[str, Any], pal: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
    rows = spec.get("rows") or []
    if not rows:
        raise ValueError("forest_plot requires non-empty rows")
    title = str(spec.get("title") or "Confidence Interval Forest Plot")
    desc = str(spec.get("description") or f"Forest plot with {len(rows)} rows and confidence intervals.")
    null_ref = float(spec.get("null_reference", 0.0))

    width = int(spec.get("width", 780))
    row_h = 38
    top_pad = 72
    bottom_pad = 48
    height = top_pad + (len(rows) * row_h) + bottom_pad

    left_col_x = 24
    plot_x0 = 240
    plot_x1 = width - 190
    stat_col_x = width - 24

    lo_val = min([null_ref] + [float(r["ci_low"]) for r in rows])
    hi_val = max([null_ref] + [float(r["ci_high"]) for r in rows])
    span = (hi_val - lo_val) if hi_val > lo_val else 1.0
    dom_lo = lo_val - 0.08 * span
    dom_hi = hi_val + 0.08 * span

    def sx(v: float) -> float:
        return round(plot_x0 + ((v - dom_lo) / (dom_hi - dom_lo)) * (plot_x1 - plot_x0), 2)

    lines = _svg_header(width, height, "svg-title", "svg-desc", title, desc, pal["background"])
    bboxes: list[dict[str, Any]] = []

    def add_text(txt: str, x: float, y: float, size: int, fill: str, anchor: str = "start", weight: str = "normal") -> None:
        bboxes.append(_estimate_text_bbox(txt, x, y, size, anchor))
        lines.append(
            f'  <text x="{x:.1f}" y="{y:.1f}" font-family="sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{_esc(txt)}</text>'
        )

    add_text(title, left_col_x, 34, 16, pal["text"], "start", "bold")
    ref_x = sx(null_ref)
    lines.append(
        f'  <line x1="{ref_x:.2f}" y1="{top_pad - 14}" x2="{ref_x:.2f}" y2="{height - bottom_pad + 8}" '
        f'stroke="{pal["muted_text"]}" stroke-width="1.5" stroke-dasharray="4 3" />'
    )

    for idx, row in enumerate(rows):
        cy = top_pad + (idx * row_h) + 14
        label = str(row["label"])
        est = float(row["estimate"])
        lo = float(row["ci_low"])
        hi = float(row["ci_high"])
        if not (lo <= est <= hi):
            raise ValueError(f"row {label!r}: require ci_low <= estimate <= ci_high")
        x_lo, x_est, x_hi = sx(lo), sx(est), sx(hi)
        lines.append(f'  <line x1="{plot_x0}" y1="{cy:.1f}" x2="{plot_x1}" y2="{cy:.1f}" stroke="{pal["grid"]}" stroke-width="1" />')
        lines.append(f'  <line x1="{x_lo:.2f}" y1="{cy:.1f}" x2="{x_hi:.2f}" y2="{cy:.1f}" stroke="{pal["primary_mark"]}" stroke-width="2.5" />')
        lines.append(f'  <line x1="{x_lo:.2f}" y1="{cy - 5:.1f}" x2="{x_lo:.2f}" y2="{cy + 5:.1f}" stroke="{pal["primary_mark"]}" stroke-width="2" />')
        lines.append(f'  <line x1="{x_hi:.2f}" y1="{cy - 5:.1f}" x2="{x_hi:.2f}" y2="{cy + 5:.1f}" stroke="{pal["primary_mark"]}" stroke-width="2" />')
        lines.append(f'  <circle cx="{x_est:.2f}" cy="{cy:.1f}" r="4.5" fill="{pal["primary_mark"]}" />')
        add_text(label, left_col_x, cy + 4, 13, pal["text"], "start")
        stat_str = f"{est:.2f} [{lo:.2f}, {hi:.2f}]"
        add_text(stat_str, stat_col_x, cy + 4, 12, pal["muted_text"], "end")

    add_text(f"ref = {null_ref:.2f}", ref_x, height - 14, 11, pal["muted_text"], "middle")
    lines.append("</svg>")
    return "\n".join(lines), bboxes


def _render_progression_bars(spec: dict[str, Any], pal: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
    bars = spec.get("bars") or []
    if not bars:
        raise ValueError("progression_bars requires non-empty bars")
    title = str(spec.get("title") or "Progression Bars")
    desc = str(spec.get("description") or f"Horizontal progression bar chart with {len(bars)} items.")
    unit = str(spec.get("unit") or "")

    width = int(spec.get("width", 760))
    row_h = 40
    top_pad = 70
    bottom_pad = 40
    height = top_pad + (len(bars) * row_h) + bottom_pad

    left_col_x = 24
    bar_x0 = 230
    bar_x1 = width - 130
    val_col_x = width - 24

    values = [float(b["value"]) for b in bars]
    if any(v < 0 for v in values):
        raise ValueError("progression_bars requires non-negative values anchored at zero")
    threshold = spec.get("target_threshold")
    max_v = max(values + ([float(threshold)] if threshold is not None else [1.0]))
    dom_max = max_v * 1.10 if max_v > 0 else 1.0

    def sx(v: float) -> float:
        return round(bar_x0 + (v / dom_max) * (bar_x1 - bar_x0), 2)

    lines = _svg_header(width, height, "svg-title", "svg-desc", title, desc, pal["background"])
    bboxes: list[dict[str, Any]] = []

    def add_text(txt: str, x: float, y: float, size: int, fill: str, anchor: str = "start", weight: str = "normal") -> None:
        bboxes.append(_estimate_text_bbox(txt, x, y, size, anchor))
        lines.append(
            f'  <text x="{x:.1f}" y="{y:.1f}" font-family="sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{_esc(txt)}</text>'
        )

    add_text(title, left_col_x, 34, 16, pal["text"], "start", "bold")
    lines.append(f'  <line x1="{bar_x0}" y1="{top_pad - 10}" x2="{bar_x0}" y2="{height - bottom_pad}" stroke="{pal["node_stroke"]}" stroke-width="1.5" />')

    for idx, bar in enumerate(bars):
        cy = top_pad + (idx * row_h)
        label = str(bar["label"])
        val = float(bar["value"])
        bw = max(2.0, sx(val) - bar_x0)
        lines.append(
            f'  <rect x="{bar_x0}" y="{cy:.1f}" width="{bw:.2f}" height="22" rx="3" fill="{pal["primary_mark"]}" />'
        )
        add_text(label, left_col_x, cy + 16, 13, pal["text"], "start")
        val_txt = f"{val:g}{(' ' + unit) if unit else ''}"
        add_text(val_txt, val_col_x, cy + 16, 12, pal["muted_text"], "end")

    if threshold is not None:
        tx = sx(float(threshold))
        lines.append(
            f'  <line x1="{tx:.2f}" y1="{top_pad - 12}" x2="{tx:.2f}" y2="{height - bottom_pad + 4}" '
            f'stroke="{pal["accent_mark"]}" stroke-width="2" stroke-dasharray="5 3" />'
        )
        add_text(f"target {float(threshold):g}", tx, height - 12, 11, pal["accent_mark"], "middle")

    lines.append("</svg>")
    return "\n".join(lines), bboxes


def _render_edge_packet_diagram(spec: dict[str, Any], pal: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
    nodes = spec.get("nodes") or []
    packets = spec.get("packets") or []
    if len(nodes) < 2:
        raise ValueError("edge_packet_diagram requires at least 2 nodes")
    title = str(spec.get("title") or "Component Edge-Packet Trace")
    desc = str(spec.get("description") or f"Message trace across {len(nodes)} components and {len(packets)} packets.")

    col_spacing = max(190, int(spec.get("column_spacing", 210)))
    margin_x = 110
    width = (margin_x * 2) + col_spacing * (len(nodes) - 1)
    lane_h = 46
    header_y = 66
    start_y = 128
    bottom_pad = 44
    height = start_y + max(1, len(packets)) * lane_h + bottom_pad

    node_x: dict[str, float] = {}
    for idx, node in enumerate(nodes):
        nid = str(node["id"])
        node_x[nid] = float(margin_x + idx * col_spacing)

    lines = _svg_header(width, height, "svg-title", "svg-desc", title, desc, pal["background"])
    lines.extend(
        [
            "  <defs>",
            f'    <marker id="arrow-ok" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">',
            f'      <path d="M 0 1 L 10 5 L 0 9 z" fill="{pal["primary_mark"]}" />',
            "    </marker>",
            f'    <marker id="arrow-err" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">',
            f'      <path d="M 0 1 L 10 5 L 0 9 z" fill="{pal["error_mark"]}" />',
            "    </marker>",
            "  </defs>",
        ]
    )
    bboxes: list[dict[str, Any]] = []

    def add_text(txt: str, x: float, y: float, size: int, fill: str, anchor: str = "start", weight: str = "normal") -> None:
        bboxes.append(_estimate_text_bbox(txt, x, y, size, anchor))
        lines.append(
            f'  <text x="{x:.1f}" y="{y:.1f}" font-family="sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{_esc(txt)}</text>'
        )

    add_text(title, 24, 32, 16, pal["text"], "start", "bold")

    for node in nodes:
        nid = str(node["id"])
        lbl = str(node.get("label") or nid)
        cx = node_x[nid]
        box_w, box_h = 136, 34
        lines.append(
            f'  <rect x="{cx - box_w / 2:.1f}" y="{header_y - box_h / 2:.1f}" width="{box_w}" height="{box_h}" '
            f'rx="5" fill="{pal["node_fill"]}" stroke="{pal["node_stroke"]}" stroke-width="1.5" />'
        )
        add_text(lbl, cx, header_y + 5, 13, pal["text"], "middle", "bold")
        lines.append(
            f'  <line x1="{cx:.1f}" y1="{header_y + box_h / 2:.1f}" x2="{cx:.1f}" y2="{height - 24:.1f}" '
            f'stroke="{pal["grid"]}" stroke-width="1.5" stroke-dasharray="4 4" />'
        )

    for idx, pkt in enumerate(packets):
        src = str(pkt["from"])
        dst = str(pkt["to"])
        if src not in node_x or dst not in node_x:
            raise ValueError(f"packet {idx}: unknown endpoint {src!r} -> {dst!r}")
        y = start_y + idx * lane_h
        x1, x2 = node_x[src], node_x[dst]
        is_err = str(pkt.get("status", "ok")).lower() == "error"
        stroke = pal["error_mark"] if is_err else pal["primary_mark"]
        marker = "url(#arrow-err)" if is_err else "url(#arrow-ok)"
        dash = ' stroke-dasharray="5 3"' if is_err else ""
        if src == dst:
            loop_w = 42
            lines.append(
                f'  <path d="M {x1:.1f} {y - 6:.1f} L {x1 + loop_w:.1f} {y - 6:.1f} L {x1 + loop_w:.1f} {y + 10:.1f} L {x1 + 4:.1f} {y + 10:.1f}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" marker-end="{marker}"{dash} />'
            )
            mid_x = x1 + loop_w + 8
            add_text(str(pkt["label"]), mid_x, y + 6, 12, pal["text"], "start")
        else:
            pad = 6.0 if x2 > x1 else -6.0
            lines.append(
                f'  <line x1="{x1 + pad:.1f}" y1="{y:.1f}" x2="{x2 - pad:.1f}" y2="{y:.1f}" '
                f'stroke="{stroke}" stroke-width="2" marker-end="{marker}"{dash} />'
            )
            mid_x = (x1 + x2) / 2.0
            add_text(str(pkt["label"]), mid_x, y - 8, 12, pal["text"], "middle")

    lines.append("</svg>")
    return "\n".join(lines), bboxes


def audit_svg_document(svg_text: str, palette: dict[str, str], bboxes: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate XML well-formedness, accessibility nodes, script absence, contrast, and label collisions."""
    root = ET.fromstring(svg_text)
    ns = "{http://www.w3.org/2000/svg}"
    has_role_img = root.attrib.get("role") == "img"
    has_aria = bool(root.attrib.get("aria-labelledby", "").strip())
    has_title = root.find(f"{ns}title") is not None and bool((root.findtext(f"{ns}title") or "").strip())
    has_desc = root.find(f"{ns}desc") is not None and bool((root.findtext(f"{ns}desc") or "").strip())

    forbidden_elements: list[str] = []
    forbidden_attrs: list[str] = []
    for elem in root.iter():
        local_name = elem.tag.split("}")[-1].lower()
        if local_name in {"script", "foreignobject", "iframe"}:
            forbidden_elements.append(local_name)
        for attr_k, attr_v in elem.attrib.items():
            clean_k = attr_k.split("}")[-1].lower()
            if clean_k.startswith("on") or "javascript:" in str(attr_v).lower():
                forbidden_attrs.append(clean_k)

    bg = palette["background"]
    text_ratio = contrast_ratio(palette["text"], bg)
    muted_ratio = contrast_ratio(palette["muted_text"], bg)
    mark_ratio = contrast_ratio(palette["primary_mark"], bg)
    err_ratio = contrast_ratio(palette["error_mark"], bg)

    contrast_checks = {
        "text_vs_background": {"ratio": text_ratio, "passes_aa_4_5": text_ratio >= 4.5},
        "muted_text_vs_background": {"ratio": muted_ratio, "passes_aa_4_5": muted_ratio >= 4.5},
        "primary_mark_vs_background": {"ratio": mark_ratio, "passes_graphical_3_0": mark_ratio >= 3.0},
        "error_mark_vs_background": {"ratio": err_ratio, "passes_graphical_3_0": err_ratio >= 3.0},
    }
    contrast_ok = (
        contrast_checks["text_vs_background"]["passes_aa_4_5"]
        and contrast_checks["muted_text_vs_background"]["passes_aa_4_5"]
        and contrast_checks["primary_mark_vs_background"]["passes_graphical_3_0"]
        and contrast_checks["error_mark_vs_background"]["passes_graphical_3_0"]
    )

    collisions = detect_label_collisions(bboxes)
    passed = (
        has_role_img
        and has_aria
        and has_title
        and has_desc
        and not forbidden_elements
        and not forbidden_attrs
        and contrast_ok
        and len(collisions) == 0
    )
    return {
        "passed": passed,
        "xml_well_formed": True,
        "accessibility": {
            "role_img": has_role_img,
            "aria_labelledby": has_aria,
            "has_title": has_title,
            "has_desc": has_desc,
        },
        "static_safety": {
            "forbidden_elements": forbidden_elements,
            "forbidden_attributes": forbidden_attrs,
        },
        "wcag_contrast": contrast_checks,
        "label_count": len(bboxes),
        "label_collisions": collisions,
    }


def compile_diagram(spec: dict[str, Any]) -> dict[str, Any]:
    """Compile a declarative spec into SVG markup plus its deterministic quality audit."""
    chart_kind = str(spec.get("chart_kind") or "")
    pal = _merged_palette(spec)
    if chart_kind == "forest_plot":
        svg, bboxes = _render_forest_plot(spec, pal)
    elif chart_kind == "progression_bars":
        svg, bboxes = _render_progression_bars(spec, pal)
    elif chart_kind == "edge_packet_diagram":
        svg, bboxes = _render_edge_packet_diagram(spec, pal)
    else:
        raise ValueError(f"unsupported chart_kind {chart_kind!r}")

    audit = audit_svg_document(svg, pal, bboxes)
    return {
        "chart_kind": chart_kind,
        "svg": svg,
        "audit": audit,
    }
