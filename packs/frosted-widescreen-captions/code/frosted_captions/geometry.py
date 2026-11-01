"""Frame and pill geometry from the canonical film-frame v6 contract (embedded as frame_v6.json)."""
import json
import pathlib

FRAME = json.loads((pathlib.Path(__file__).with_name("frame_v6.json")).read_text(encoding="utf-8"))
GRID = FRAME["wrap_and_render_grid"]
PILL = FRAME["caption_pill"]
BOX = PILL["box"]
CENTER = tuple(PILL["center_px"])
BAND_Y = tuple(FRAME["frame"]["band"]["y"])
STAGE_Y = tuple(FRAME["frame"]["stage"]["y"])
FRAME_WIDTH_PX = FRAME["frame"]["output_px"][0]
FONT_PX = PILL["font"]["size_px"]
LINE_PX = PILL["font"]["line_height_px"]
PAD_Y, PAD_X = BOX["padding_px"]["y"], BOX["padding_px"]["x"]
AVG_ADVANCE_EM = GRID["avg_advance_em"]
FLOAT_TOL = GRID["float_tol"]
HALF_DIV = GRID["half_divisor"]
DOUBLE_MULT = GRID["double_multiplier"]
SQRT_EXP = GRID["sqrt_exp"]


def text_width(line, font_px=FONT_PX):
    return len(line) * font_px * AVG_ADVANCE_EM


def pill_box(lines):
    """(x, y, w, h) of the pill for these lines, centered on the contract's center."""
    widest = max((text_width(x) for x in lines), default=0.0)
    w = max(BOX["min_width_px"], min(BOX["max_text_width_px"], widest) + DOUBLE_MULT * PAD_X)
    h = len(lines) * LINE_PX + DOUBLE_MULT * PAD_Y
    cx, cy = CENTER
    return (cx - w / HALF_DIV, cy - h / HALF_DIV, w, h)


def inside_band(box, clearance=FRAME["pacing"]["clearance_px"]):
    x, y, w, h = box
    return (
        y >= BAND_Y[0] + clearance - FLOAT_TOL
        and y + h <= BAND_Y[1] - clearance + FLOAT_TOL
        and x >= 0
        and x + w <= FRAME_WIDTH_PX
    )


def gap(a, b):
    """Smallest distance between two boxes (0 if they touch or overlap)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = max(bx - (ax + aw), ax - (bx + bw), 0)
    dy = max(by - (ay + ah), ay - (by + bh), 0)
    return (dx * dx + dy * dy) ** SQRT_EXP if dx and dy else max(dx, dy)


def clear_of(box, others, min_px=FRAME["pacing"]["clearance_px"]):
    return all(gap(box, o) >= min_px for o in others)
