"""Contrast ratios as WCAG 2.2 defines them, for text (1.4.3, 1.4.6) and for non-text parts (1.4.11).

Colors are sRGB. A color with transparency is composited over the background first, in the same
gamma-encoded space browsers blend in. Pass and fail always use the unrounded ratio, so a ratio
that would round up to a threshold still fails it; `ratio` is rounded to two decimals for reading.
"""

from __future__ import annotations

import re
from typing import Any

# Large text is at least 18 point, or 14 point and bold. A point is 4/3 CSS pixels.
LARGE_PX = 24.0
LARGE_BOLD_PX = 56 / 3  # 14 pt
BOLD_WEIGHT = 700

THRESHOLDS = {
    "text": {"sc": "1.4.3", "name": "Contrast (Minimum)", "level": "AA", "normal": 4.5, "large": 3.0},
    "text_enhanced": {"sc": "1.4.6", "name": "Contrast (Enhanced)", "level": "AAA", "normal": 7.0, "large": 4.5},
    "non_text": {"sc": "1.4.11", "name": "Non-text Contrast", "level": "AA", "normal": 3.0, "large": 3.0},
}

NAMED = {"black": (0, 0, 0, 1.0), "white": (255, 255, 255, 1.0), "transparent": (0, 0, 0, 0.0)}
HEX = re.compile(r"#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
FUNC = re.compile(r"rgba?\(\s*([^)]*)\)", re.IGNORECASE)

Color = tuple  # (r, g, b, alpha) with r, g, b in 0..255 and alpha in 0..1


def _component(text: str, scale: float) -> float:
    text = text.strip()
    value = float(text[:-1]) / 100 * scale if text.endswith("%") else float(text)
    if not 0 <= value <= scale:
        raise ValueError(f"color component {text!r} is out of range")
    return value


def parse_color(text: str) -> Color:
    """Parse #rgb, #rgba, #rrggbb, #rrggbbaa, rgb() or rgba() (comma or space syntax), or black, white, transparent."""
    raw = str(text).strip()
    lowered = raw.lower()
    if lowered in NAMED:
        return NAMED[lowered]
    match = HEX.fullmatch(raw)
    if match:
        digits = match.group(1)
        if len(digits) in (3, 4):
            digits = "".join(ch * 2 for ch in digits)
        r, g, b = (int(digits[i:i + 2], 16) for i in (0, 2, 4))
        alpha = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
        return (r, g, b, alpha)
    match = FUNC.fullmatch(raw)
    if match:
        body = match.group(1).replace("/", " / ")
        if "," in body:
            parts = [p for p in body.replace("/", ",").split(",") if p.strip()]
        else:
            parts = [p for p in body.split() if p != "/"]
        if len(parts) not in (3, 4):
            raise ValueError(f"cannot parse color {text!r}")
        r, g, b = (_component(p, 255) for p in parts[:3])
        alpha = _component(parts[3], 1.0) if len(parts) == 4 else 1.0
        return (r, g, b, alpha)
    raise ValueError(f"cannot parse color {text!r}")


def composite(top: Color, bottom: Color) -> Color:
    """Source-over compositing of top onto bottom."""
    alpha = top[3] + bottom[3] * (1 - top[3])
    if alpha == 0:
        return (0.0, 0.0, 0.0, 0.0)
    mix = [(top[i] * top[3] + bottom[i] * bottom[3] * (1 - top[3])) / alpha for i in range(3)]
    return (mix[0], mix[1], mix[2], alpha)


def flatten(foreground: str, background: str, canvas: str = "white") -> tuple[Color, Color]:
    """Opaque foreground and background colors: the background over the canvas, the foreground over that."""
    bg = composite(parse_color(background), parse_color(canvas))
    fg = composite(parse_color(foreground), bg)
    return fg, bg


def _linear(channel: float) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(color: Color) -> float:
    r, g, b = (_linear(color[i]) for i in range(3))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio_of(a: Color, b: Color) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def is_large_text(size_px: float, weight: int | float = 400) -> bool:
    return size_px >= LARGE_PX or (size_px >= LARGE_BOLD_PX - 1e-9 and weight >= BOLD_WEIGHT)


def to_hex(color: Color) -> str:
    return "#" + "".join(f"{int(round(color[i])):02x}" for i in range(3))


def check_pair(foreground: str, background: str, *, size_px: float | None = None, weight: int | float = 400,
               kind: str = "text", canvas: str = "white") -> dict[str, Any]:
    """One color pair against its WCAG threshold. kind is text or non_text."""
    if kind not in ("text", "non_text"):
        raise ValueError("kind is text or non_text")
    fg, bg = flatten(foreground, background, canvas)
    exact = ratio_of(fg, bg)
    out: dict[str, Any] = {"foreground": to_hex(fg), "background": to_hex(bg), "ratio": round(exact, 2), "kind": kind}
    if kind == "non_text":
        rule = THRESHOLDS["non_text"]
        out.update({"sc": rule["sc"], "level": rule["level"], "required": rule["normal"], "passes": exact >= rule["normal"]})
        return out
    large = size_px is not None and is_large_text(size_px, weight)
    rule, enhanced = THRESHOLDS["text"], THRESHOLDS["text_enhanced"]
    required = rule["large"] if large else rule["normal"]
    required_enhanced = enhanced["large"] if large else enhanced["normal"]
    out.update({
        "large_text": large,
        "size_known": size_px is not None,
        "sc": rule["sc"],
        "level": rule["level"],
        "required": required,
        "passes": exact >= required,
        "enhanced": {"sc": enhanced["sc"], "level": enhanced["level"], "required": required_enhanced,
                     "passes": exact >= required_enhanced},
    })
    return out


def format_ratio(ratio: float) -> str:
    return f"{ratio:.2f}:1"
