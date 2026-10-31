"""Zero-double-exposure transition validator and subtle aura / Bezier edge-packet curves."""

from __future__ import annotations

import math
from typing import Any, Sequence

ALLOWED_TEXT_TRANSITIONS = ("hard_cut", "camera_move", "dip_to_slate")
BLEND_TRANSITIONS = ("crossfade", "dissolve", "alpha_blend")


def validate_zero_double_exposure(
    shots: Sequence[dict[str, Any]],
    transitions: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Forbid crossfades or dissolves when both adjacent shots display text or UI chrome.

    Enforces clean cuts, 3D camera moves, or brief dips to clean background slate so viewers
    never see ghosted overlapping typography during transitions.
    """
    by_id = {str(s["id"]): s for s in shots}
    violations: list[dict[str, Any]] = []

    for tr in transitions:
        from_id = str(tr["from_shot"])
        to_id = str(tr["to_shot"])
        kind = str(tr["kind"])
        dur = float(tr.get("duration_s", 0.0))

        s_a = by_id.get(from_id)
        s_b = by_id.get(to_id)
        if s_a is None or s_b is None:
            violations.append({
                "from_shot": from_id,
                "to_shot": to_id,
                "kind": "unknown_shot_reference",
                "severity": "blocker",
            })
            continue

        a_text = bool(s_a.get("has_text", True) or s_a.get("has_ui_chrome", False))
        b_text = bool(s_b.get("has_text", True) or s_b.get("has_ui_chrome", False))

        if kind in BLEND_TRANSITIONS and dur > 0.0 and a_text and b_text:
            violations.append({
                "from_shot": from_id,
                "to_shot": to_id,
                "transition_kind": kind,
                "duration_s": round(dur, 3),
                "kind": "double_exposure_text_crossfade",
                "severity": "blocker",
                "allowed_replacements": list(ALLOWED_TEXT_TRANSITIONS),
                "remediation": "Replace text-on-text crossfade with a 3D camera_move, hard_cut, or dip_to_slate.",
            })

    return {
        "checked_transitions": len(transitions),
        "valid": len(violations) == 0,
        "violations": violations,
    }


def interpolate_edge_packet(
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    u: float,
    *,
    curvature_px: float = 28.0,
    max_opacity: float = 0.55,
) -> dict[str, float]:
    """Quadratic Bezier packet travel curve between two architecture cards with smooth endpoint fade."""
    t = max(0.0, min(1.0, float(u)))
    x0, y0 = float(start_xy[0]), float(start_xy[1])
    x1, y1 = float(end_xy[0]), float(end_xy[1])
    mx, my = 0.5 * (x0 + x1), 0.5 * (y0 + y1)

    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length > 1e-6:
        nx, ny = -dy / length, dx / length
    else:
        nx, ny = 0.0, -1.0

    cx = mx + nx * curvature_px
    cy = my + ny * curvature_px

    inv = 1.0 - t
    px = inv * inv * x0 + 2.0 * inv * t * cx + t * t * x1
    py = inv * inv * y0 + 2.0 * inv * t * cy + t * t * y1
    # Bell envelope 4*t*(1-t) reaches 1.0 at midpoint and 0.0 at card borders so packets never clip abruptly
    envelope = 4.0 * t * inv
    opacity = max_opacity * envelope
    return {
        "u": round(t, 4),
        "x": round(px, 2),
        "y": round(py, 2),
        "opacity": round(opacity, 4),
    }


def compute_card_aura(
    t_s: float,
    *,
    focused: bool,
    base_opacity: float = 0.08,
    focus_boost: float = 0.10,
    pulse_amp: float = 0.03,
    pulse_hz: float = 0.5,
    ceiling_opacity: float = 0.22,
) -> dict[str, float]:
    """Subtle card aura glow curve clamped strictly below `ceiling_opacity` to prevent neon glare."""
    if not focused:
        op = min(ceiling_opacity, max(0.0, base_opacity * 0.5))
        return {"time_s": round(t_s, 3), "opacity": round(op, 4), "spread_px": 10.0}
    wave = 0.5 * (1.0 + math.sin(2.0 * math.pi * pulse_hz * t_s - 0.5 * math.pi))
    raw = base_opacity + focus_boost + pulse_amp * wave
    clamped = min(ceiling_opacity, max(0.0, raw))
    spread = 14.0 + 4.0 * wave
    return {
        "time_s": round(t_s, 3),
        "opacity": round(clamped, 4),
        "spread_px": round(spread, 2),
    }
