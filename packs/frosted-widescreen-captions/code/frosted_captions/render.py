"""Deterministic SVG of the caption band with its pill, for compositors that overlay images on video.

The band is a solid #11161F, so the backdrop blur has nothing to blur; the glass look comes from the fill
gradient, the rim and the shadow. A renderer that composites over an ambient band applies a 10 px blur
to the band behind the pill before drawing this SVG.
"""
from xml.sax.saxutils import escape

from .geometry import BAND_Y, BOX, CENTER, FONT_PX, FRAME, FRAME_WIDTH_PX, GRID, HALF_DIV, LINE_PX, pill_box
from .wrap import wrap_balanced

FONT = FRAME["caption_pill"]["font"]
SVG_CFG = GRID["svg"]


def band_svg(text, width=FRAME_WIDTH_PX):
    lines = wrap_balanced(text)
    x, y, w, h = pill_box(lines)
    top = BAND_Y[0]
    y_local = y - top
    band_h = BAND_Y[1] - BAND_Y[0]
    first_baseline = y_local + BOX["padding_px"]["y"] + (LINE_PX + FONT_PX * SVG_CFG["baseline_font_ratio"]) / HALF_DIV
    inset = SVG_CFG["rim_inset_px"]
    shrink = SVG_CFG["rim_shrink_px"]
    tspans = "".join(
        f'<tspan x="{CENTER[0]}" y="{first_baseline + i * LINE_PX:.1f}">{escape(t)}</tspan>' for i, t in enumerate(lines)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{band_h}" viewBox="0 0 {width} {band_h}">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#11161F" stop-opacity="0.80"/><stop offset="1" stop-color="#181F2C" stop-opacity="0.86"/>'
        '</linearGradient>'
        '<filter id="s" x="-10%" y="-30%" width="120%" height="160%"><feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000" flood-opacity="0.35"/></filter>'
        '</defs>'
        f'<rect width="{width}" height="{band_h}" fill="#11161F"/>'
        f'<rect x="{x:.1f}" y="{y_local:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{BOX["radius_px"]}" fill="url(#g)" filter="url(#s)"/>'
        f'<rect x="{x + inset:.1f}" y="{y_local + inset:.1f}" width="{w - shrink:.1f}" height="{h - shrink:.1f}" rx="{BOX["radius_px"] - inset}" fill="none" stroke="#F5F2EA" stroke-opacity="0.22" stroke-width="1.5"/>'
        f'<text text-anchor="middle" font-family="{FONT["family"]}" font-weight="{FONT["weight"]}" font-size="{FONT_PX}" fill="{FONT["color"]}">{tspans}</text>'
        '</svg>'
    )
