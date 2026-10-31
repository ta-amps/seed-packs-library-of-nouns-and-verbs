"""Per-frame measurements that need no model: layered edges, the frame's border bands, flat panels and text motion.

Every function is a pure function of the pixels it is given, so a frame measured twice gives the same record.
"""

from __future__ import annotations

import cv2
import numpy as np

SIDES = ("left", "top", "right", "bottom")


def gray_of(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def edge_layers(gray: np.ndarray, low: int, high: int, levels: int = 3) -> tuple[list[float], np.ndarray]:
    """Canny edge density at full size and at each halving, and the full-size edge map."""
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)
    densities = []
    full = None
    level = blurred
    for i in range(levels):
        edges = cv2.Canny(level, low, high, L2gradient=True)
        if i == 0:
            full = edges
        densities.append(float(np.count_nonzero(edges)) / edges.size)
        level = cv2.pyrDown(level)
    assert full is not None
    return densities, full


def local_contrast(gray: np.ndarray) -> float:
    """The 99.9th percentile of brightness steps between neighbouring pixels: about 0 to 3 on a flat frame,
    higher wherever anything is drawn, even text too faint for the edge detector."""
    g = gray.astype(np.int16)
    steps = np.concatenate([np.abs(np.diff(g[::2], axis=1)).ravel(), np.abs(np.diff(g[:, ::2], axis=0)).ravel()])
    return float(np.percentile(steps, 99.9))


def border_profile(gray: np.ndarray, edges: np.ndarray, action: float, title: float, step: int) -> dict:
    """For each side: changes along the outermost two pixel lines, and edge density in the safe-margin bands.

    `crossings` counts places where the brightness along the frame's own edge changes by at least `step`
    levels between neighbouring pixels: content that runs off the frame crosses that line, a background
    or a rule parallel to it does not.
    """
    height, width = gray.shape
    out = {}
    lines = {
        "left": gray[:, 0:2].mean(axis=1), "right": gray[:, width - 2:width].mean(axis=1),
        "top": gray[0:2, :].mean(axis=0), "bottom": gray[height - 2:height, :].mean(axis=0),
    }
    for side, line in lines.items():
        jumps = np.abs(np.diff(line.astype(np.float32)))
        crossings = int(np.count_nonzero((jumps[1:] >= step) & (jumps[:-1] < step)) + (1 if len(jumps) and jumps[0] >= step else 0))
        span = height if side in ("left", "right") else width
        across = width if side in ("left", "right") else height
        a, t = int(round(action * across)), int(round(title * across))
        if side == "left":
            band_a, band_t = edges[:, :a], edges[:, a:t]
        elif side == "right":
            band_a, band_t = edges[:, width - a:], edges[:, width - t:width - a]
        elif side == "top":
            band_a, band_t = edges[:a, :], edges[a:t, :]
        else:
            band_a, band_t = edges[height - a:, :], edges[height - t:height - a, :]
        out[side] = {
            "crossings": crossings,
            "per_1000px": round(1000.0 * crossings / span, 2),
            "action_band_density": round(float(np.count_nonzero(band_a)) / max(1, band_a.size), 4),
            "title_band_density": round(float(np.count_nonzero(band_t)) / max(1, band_t.size), 4),
        }
    return out


def dominant_border_color(small: np.ndarray, quant: int = 16) -> tuple[int, int, int]:
    """The most common colour along the frame's border, quantized, as BGR bin centres."""
    rim = np.concatenate([small[0], small[-1], small[:, 0], small[:, -1]]).astype(np.int32) // quant
    codes = rim[:, 0] * 4096 + rim[:, 1] * 64 + rim[:, 2]
    values, counts = np.unique(codes, return_counts=True)
    code = int(values[np.argmax(counts)])
    return ((code // 4096) * quant + quant // 2, ((code // 64) % 64) * quant + quant // 2, (code % 64) * quant + quant // 2)


def panels(frame: np.ndarray, scale: int, flat_std: float, step: float, min_area_share: float,
           min_side_px: int, rect_min: float) -> list[dict]:
    """Flat-filled rectangles: cards, windows, terminals, bars and chips.

    Pixels whose 5x5 neighbourhood is flat and whose colour changes by less than `step` levels to the
    right and below are joined into regions. A region whose outer outline fills at least `rect_min` of
    its bounding box is a panel; text inside it leaves holes but not a different outline. Boxes are in
    full-frame pixels. The region in the frame's dominant border colour is the background, not a panel.
    """
    height, width = frame.shape[:2]
    small = cv2.resize(frame, (width // scale, height // scale), interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    f = small.astype(np.float32)
    mean = cv2.blur(f, (5, 5))
    var = cv2.blur(f * f, (5, 5)) - mean * mean
    flat = var.max(axis=2) < flat_std * flat_std
    diff_x = np.zeros((sh, sw), bool)
    diff_y = np.zeros((sh, sw), bool)
    diff_x[:, :-1] = np.abs(f[:, 1:] - f[:, :-1]).max(axis=2) >= step
    diff_y[:-1, :] = np.abs(f[1:] - f[:-1]).max(axis=2) >= step
    region = (flat & ~diff_x & ~diff_y).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(region, connectivity=4)
    background = np.array(dominant_border_color(small), np.float32)
    min_area = min_area_share * sw * sh
    found = []
    for i in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area < min_area or w * scale < min_side_px or h * scale < min_side_px:
            continue
        if w >= sw - 1 and h >= sh - 1:
            continue
        mask = (labels[y:y + h, x:x + w] == i).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        outline = max(contours, key=cv2.contourArea)
        filled = float(cv2.contourArea(outline))
        if filled <= 0:
            continue
        rect = filled / float(w * h)
        if rect < rect_min:
            continue
        color = small[y:y + h, x:x + w][mask > 0].reshape(-1, 3).astype(np.float32).mean(axis=0)
        is_background = bool(np.abs(color - background).max() <= 12)
        touches = []
        if x <= 0:
            touches.append("left")
        if y <= 0:
            touches.append("top")
        if x + w >= sw:
            touches.append("right")
        if y + h >= sh:
            touches.append("bottom")
        found.append({
            "box": [x * scale, y * scale, min(width, (x + w) * scale), min(height, (y + h) * scale)],
            "rect": round(rect, 3),
            "solid": round(area / filled, 3),
            "color": "#%02x%02x%02x" % (int(color[2]), int(color[1]), int(color[0])),
            "background": is_background,
            "touches": touches,
        })
    found.sort(key=lambda p: (p["box"][1], p["box"][0], p["box"][2], p["box"][3]))
    return found


def phase_shift(a: np.ndarray, b: np.ndarray, window: np.ndarray | None = None) -> tuple[float, float, float]:
    """Sub-pixel shift (dx, dy) that maps a onto b, and the correlation peak's response.

    OpenCV 5.0's phaseCorrelate writes the window into its inputs, so it only ever sees copies here.
    """
    fa = np.array(a, dtype=np.float32, copy=True)
    fb = np.array(b, dtype=np.float32, copy=True)
    if window is None:
        window = cv2.createHanningWindow((fa.shape[1], fa.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(fa, fb, np.array(window, copy=True))
    return float(dx), float(dy), float(response)


def _subpixel(scores: np.ndarray, y: int, x: int) -> tuple[float, float]:
    def peak(left: float, mid: float, right: float) -> float:
        denom = left - 2 * mid + right
        return 0.0 if abs(denom) < 1e-9 else max(-0.5, min(0.5, 0.5 * (left - right) / denom))

    h, w = scores.shape
    ox = peak(scores[y, x - 1], scores[y, x], scores[y, x + 1]) if 0 < x < w - 1 else 0.0
    oy = peak(scores[y - 1, x], scores[y, x], scores[y + 1, x]) if 0 < y < h - 1 else 0.0
    return ox, oy


def text_motion(gray_a: np.ndarray, gray_b: np.ndarray, boxes: list[tuple[int, int, int, int]], limit: int = 12) -> dict:
    """How far the pixels under the largest text boxes move from one frame to the next.

    Each box's pixels are matched in the next frame within a search window of 1.5 box heights (at least 48 px)
    around it, by normalized cross-correlation at half size with a sub-pixel peak. Returns the median and maximum
    speed in full-size pixels per frame over boxes whose match is clear (correlation at least 0.6); a move
    larger than the window is reported at the window's size, as a lower bound.
    """
    height, width = gray_a.shape
    ranked = sorted(boxes, key=lambda b: (-(b[2] - b[0]) * (b[3] - b[1]), b))[:limit]
    speeds = []
    saturated = 0
    for x0, y0, x1, y1 in ranked:
        if x1 - x0 < 8 or y1 - y0 < 6:
            continue
        reach = max(48, int(1.5 * (y1 - y0)))
        tx0, ty0, tx1, ty1 = max(0, x0), max(0, y0), min(width, x1), min(height, y1)
        sx0, sy0, sx1, sy1 = max(0, tx0 - reach), max(0, ty0 - reach), min(width, tx1 + reach), min(height, ty1 + reach)
        template = gray_a[ty0:ty1, tx0:tx1]
        if float(template.std()) < 6:
            continue
        t_small = cv2.resize(template, ((tx1 - tx0) // 2 or 1, (ty1 - ty0) // 2 or 1), interpolation=cv2.INTER_AREA)
        region = gray_b[sy0:sy1, sx0:sx1]
        r_small = cv2.resize(region, ((sx1 - sx0) // 2 or 1, (sy1 - sy0) // 2 or 1), interpolation=cv2.INTER_AREA)
        if r_small.shape[0] < t_small.shape[0] or r_small.shape[1] < t_small.shape[1]:
            continue
        scores = cv2.matchTemplate(r_small, t_small, cv2.TM_CCOEFF_NORMED)
        _, best, _, (bx, by) = cv2.minMaxLoc(scores)
        if best < 0.6:
            continue
        ox, oy = _subpixel(scores, by, bx)
        dx = (bx + ox) * 2 + sx0 - tx0
        dy = (by + oy) * 2 + sy0 - ty0
        if bx in (0, scores.shape[1] - 1) or by in (0, scores.shape[0] - 1):
            saturated += 1
        speeds.append(float(np.hypot(dx, dy)))
    if not speeds:
        return {"boxes": 0, "median_px": None, "max_px": None, "at_window_limit": 0}
    return {"boxes": len(speeds), "median_px": round(float(np.median(speeds)), 2), "max_px": round(float(np.max(speeds)), 2),
            "at_window_limit": saturated}
