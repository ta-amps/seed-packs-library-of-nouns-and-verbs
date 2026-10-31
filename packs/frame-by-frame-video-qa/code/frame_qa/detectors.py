"""The `detect` verb's work: nine detectors over the measurements of every frame, each returning hits.

A hit is one frame's evidence for one finding: the detector, the kind of problem, the frame, a severity,
a box in frame pixels (or none for whole-frame events) and the measurements behind it. The cluster step
joins hits on nearby frames into findings. Every detector is a pure function of the records and the spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import cv2
import numpy as np

from .captions import Cue, active_cue, caption_box
from .features import phase_shift

Box = tuple[int, int, int, int]


@dataclass
class Hit:
    detector: str
    kind: str
    frame: int
    severity: str
    box: Box | None
    score: float
    detail: dict = field(default_factory=dict)
    key: str = ""


@dataclass
class Context:
    width: int
    height: int
    fps: float
    frames: int
    spec: dict
    temporal: dict
    records: list[dict]
    cues: list[Cue]
    transitions: list[dict] = field(default_factory=list)
    skip: set[int] = field(default_factory=set)
    shot_ids: list[str] = field(default_factory=list)

    def shot(self, frame: int) -> str:
        return self.shot_ids[frame] if 0 <= frame < len(self.shot_ids) else "S01"

    def t(self, frame: int) -> float:
        return frame / self.fps

    def th(self, detector: str) -> dict:
        return self.spec["detectors"][detector]["thresholds"]

    @property
    def scale_1080(self) -> float:
        return float(self.spec["text"]["reference_height_px"]) / self.height


SEVERITY_RANK = {"blocker": 3, "major": 2, "minor": 1, "note": 0}


def worse(a: str, b: str) -> str:
    return a if SEVERITY_RANK[a] >= SEVERITY_RANK[b] else b


def area(box: Box) -> int:
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def intersect(a: Box, b: Box) -> Box:
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


def iou(a: Box, b: Box) -> float:
    inter = area(intersect(a, b))
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def union(a: Box, b: Box) -> Box:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


# ---------------------------------------------------------------------------
# Text lines, with the paragraph-neighbour font rule
# ---------------------------------------------------------------------------


def lines_of(record: dict) -> list[dict]:
    """The record's text lines with `font` set: the measured size, or a paragraph neighbour's when the line
    holds only x-height letters (its cap and x-height agree) and the neighbour's x-height matches them."""
    lines = [dict(line) for line in record.get("text") or []]
    for line in lines:
        line["font"] = float(line["font_px"])
        line["box"] = tuple(line["box"])
    for line in lines:
        cap, xh = float(line["cap_px"]), float(line["xh_px"])
        if line["glyphs"] < 3 or cap <= 0 or xh / cap < 0.85:
            continue
        x0, y0, x1, y1 = line["box"]
        h = y1 - y0
        best = None
        for other in lines:
            if other is line or other["glyphs"] < 4:
                continue
            ocap, oxh = float(other["cap_px"]), float(other["xh_px"])
            if ocap <= 0 or oxh / ocap >= 0.8:
                continue
            ox0, oy0, ox1, oy1 = other["box"]
            same_left = abs(ox0 - x0) <= 8
            same_row = abs(oy1 - y1) <= max(3, 0.25 * h) and (abs(ox1 - x0) <= 3 * h or abs(x1 - ox0) <= 3 * h)
            stacked = same_left and (0 <= y0 - oy1 <= 1.6 * (oy1 - oy0) or 0 <= oy0 - y1 <= 1.6 * (oy1 - oy0))
            if not (stacked or same_row):
                continue
            if abs(oxh - cap) > 0.2 * max(1.0, oxh):
                continue
            stroke, ostroke = float(line["stroke_px"]), float(other["stroke_px"])
            if ostroke > 0 and abs(stroke - ostroke) > 0.35 * ostroke + 0.6:
                continue
            if best is None or abs(oy0 - y0) < abs(best["box"][1] - y0):
                best = other
        if best is not None:
            line["font"] = float(best["font_px"])
            line["font_from_neighbour"] = True
    return lines


def spatial_records(ctx: Context) -> Iterable[tuple[dict, list[dict]]]:
    for record in ctx.records:
        if "text" not in record or record["i"] in ctx.skip:
            continue
        yield record, lines_of(record)


def aggregate(ctx: Context, detector: str, frame: int, per_line: list[tuple[str, str, dict, Box, float]]) -> list[Hit]:
    """One hit per kind per frame for detectors that flag many lines at once: the union of their boxes, the
    worst line's measurements, and every line's box and value. Such hits join by kind and shot, not by box."""
    by_kind: dict[str, list[tuple[str, dict, Box, float]]] = {}
    for kind, severity, detail, box, score in per_line:
        by_kind.setdefault(kind, []).append((severity, detail, box, score))
    out = []
    for kind, items in sorted(by_kind.items()):
        items.sort(key=lambda it: (-SEVERITY_RANK[it[0]], -it[3], it[2]))
        severity, detail, box, score = items[0]
        whole = box
        for _, _, b, _ in items[1:]:
            whole = union(whole, b)
        lines = [{"box": list(b), **{k: v for k, v in d.items() if k in ("font_px_1080p", "ratio", "phone_px")}} for _, d, b, _ in items[:12]]
        out.append(Hit(detector, kind, frame, severity, whole, score, {**detail, "lines": len(items), "line_boxes": lines},
                       f"shot:{ctx.shot(frame)}"))
    return out


# ---------------------------------------------------------------------------
# 1. Cut-off content
# ---------------------------------------------------------------------------


def detect_cut_off_content(ctx: Context) -> list[Hit]:
    th = ctx.th("cut_off_content")
    sa = ctx.spec["safe_areas"]
    W, H = ctx.width, ctx.height
    title_x, title_y = sa["title_safe_share"] * W, sa["title_safe_share"] * H
    action_x, action_y = sa["action_safe_share"] * W, sa["action_safe_share"] * H
    touch = int(sa["touch_px"])
    hits = []
    for record, lines in spatial_records(ctx):
        for line in lines:
            if line["glyphs"] < 2:
                continue
            x0, y0, x1, y1 = line["box"]
            margins = {"left": x0, "top": y0, "right": W - x1, "bottom": H - y1}
            limits_action = {"left": action_x, "right": action_x, "top": action_y, "bottom": action_y}
            limits_title = {"left": title_x, "right": title_x, "top": title_y, "bottom": title_y}
            at_edge = sorted({s for s, m in margins.items() if m <= touch} | set(line["edge_clipped"]))
            in_action = sorted(s for s, m in margins.items() if m < limits_action[s])
            in_title = sorted(s for s, m in margins.items() if m < limits_title[s])
            if at_edge:
                kind, sides, severity = "text_at_edge", at_edge, "minor"
            elif in_action:
                kind, sides, severity = "text_in_action_margin", in_action, "minor"
            elif in_title:
                kind, sides, severity = "text_in_title_margin", in_title, "note"
            else:
                continue
            nearest = min(margins[s] for s in sides)
            hits.append(Hit("cut_off_content", kind, record["i"], severity, line["box"], -float(nearest),
                            {"sides": sides, "margin_px": int(nearest), "font_px": round(line["font"], 1),
                             "clipped_by_frame": list(line["edge_clipped"])}, "-".join(sides)))
    step = int(th["border_step_levels"])
    for record in ctx.records:
        if record["i"] in ctx.skip:
            continue
        for side, band in record["border"].items():
            if band["crossings"] >= th["ui_min_crossings"] and band["action_band_density"] >= th["ui_min_band_density"]:
                a = int(round(sa["action_safe_share"] * (W if side in ("left", "right") else H)))
                box = {"left": (0, 0, a, H), "right": (W - a, 0, W, H), "top": (0, 0, W, a), "bottom": (0, H - a, W, H)}[side]
                hits.append(Hit("cut_off_content", "ui_off_edge", record["i"], "note", box, float(band["crossings"]),
                                {"side": side, "crossings": band["crossings"], "band_edge_density": band["action_band_density"],
                                 "step_levels": step}, side))
    return hits


# ---------------------------------------------------------------------------
# 2. Cut-off windows
# ---------------------------------------------------------------------------


def detect_cut_off_windows(ctx: Context) -> list[Hit]:
    th = ctx.th("cut_off_windows")
    touch = int(ctx.spec["safe_areas"]["touch_px"])
    W, H = ctx.width, ctx.height
    tol = int(th["edge_tolerance_px"])
    hits = []
    for record, lines in spatial_records(ctx):
        for panel in record.get("panels") or []:
            if panel["background"]:
                continue
            box = tuple(panel["box"])
            x0, y0, x1, y1 = box
            if area(box) < th["min_area_share"] * W * H or (x1 - x0) < th["min_side_px"] or (y1 - y0) < th["min_side_px"]:
                continue
            if area(box) > 0.9 * W * H:
                continue
            sides = [s for s, gap in (("left", x0), ("top", y0), ("right", W - x1), ("bottom", H - y1)) if gap <= tol]
            if not sides or len(sides) == 4:
                continue
            cut_text = []
            for line in lines:
                lb = line["box"]
                if area(intersect(lb, box)) < 0.6 * max(1, area(lb)):
                    continue
                margins = {"left": lb[0], "top": lb[1], "right": W - lb[2], "bottom": H - lb[3]}
                if any(margins[s] <= touch or s in line["edge_clipped"] for s in sides):
                    cut_text.append(list(lb))
            kind = "panel_at_edge_with_cut_text" if cut_text else "panel_at_edge"
            severity = "major" if cut_text else "minor"
            hits.append(Hit("cut_off_windows", kind, record["i"], severity, box, float(area(box)),
                            {"sides": sides, "panel_color": panel["color"], "cut_text_boxes": cut_text[:6]}, "-".join(sides)))
    return hits


# ---------------------------------------------------------------------------
# 3. Overlaps
# ---------------------------------------------------------------------------


def _hex_bgr(color: str) -> np.ndarray:
    return np.array([int(color[5:7], 16), int(color[3:5], 16), int(color[1:3], 16)], np.int32)


def detect_overlaps(ctx: Context) -> list[Hit]:
    th = ctx.th("overlaps")
    hits = []
    for record, lines in spatial_records(ctx):
        boxes = [line["box"] for line in lines]
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                a, b = boxes[i], boxes[j]
                inter = area(intersect(a, b))
                if inter <= 0:
                    continue
                share = inter / float(min(area(a), area(b)))
                if share < th["text_overlap_min_share"] or iou(a, b) >= th["duplicate_iou"]:
                    continue
                severity = "major" if share >= th["text_overlap_major_share"] else "minor"
                hits.append(Hit("overlaps", "text_on_text", record["i"], severity, union(a, b), share,
                                {"boxes": [list(a), list(b)], "overlap_share": round(share, 3)}))
        for chip in record.get("chips") or []:
            cbox = tuple(chip["box"])
            ccolor = _hex_bgr(chip["color"])
            for k, line in enumerate(lines):
                if k == chip["line"]:
                    continue
                lb = line["box"]
                ix0, iy0, ix1, iy1 = intersect(lb, cbox)
                if ix1 - ix0 < th["chip_min_overlap_px"] or iy1 - iy0 < th["chip_min_overlap_px"]:
                    continue
                if np.abs(_hex_bgr(line["bg"]) - ccolor).max() <= th["chip_color_step"]:
                    continue
                if area(intersect(lb, cbox)) >= 0.9 * area(lb):
                    continue
                height = max(1, lb[3] - lb[1])
                width = max(1, lb[2] - lb[0])
                covered = max((iy1 - iy0) / height if (ix1 - ix0) >= 0.5 * min(width, cbox[2] - cbox[0]) else 0.0,
                              (ix1 - ix0) / width if (iy1 - iy0) >= 0.5 * height else 0.0)
                severity = "major" if covered >= th["chip_major_share"] else "minor"
                hits.append(Hit("overlaps", "chip_covers_text", record["i"], severity, union(lb, cbox), covered,
                                {"chip_box": list(cbox), "chip_color": chip["color"], "text_box": list(lb),
                                 "covered_share": round(covered, 3)}))
    return hits


# ---------------------------------------------------------------------------
# 4. Small text
# ---------------------------------------------------------------------------


def detect_small_text(ctx: Context) -> list[Hit]:
    th = ctx.th("small_text")
    scale = ctx.scale_1080
    phone = float(th["phone_width_px"]) / ctx.width
    hits = []
    for record, lines in spatial_records(ctx):
        phone_fail = []
        per_line: list[tuple[str, str, dict, Box, float]] = []
        for line in lines:
            if line["glyphs"] < th["min_glyphs"]:
                continue
            font = line["font"] * scale
            on_phone = line["font"] * phone
            detail = {"font_px_1080p": round(font, 1), "phone_px": round(on_phone, 1), "cap_px": line["cap_px"],
                      "from_neighbour": bool(line.get("font_from_neighbour"))}
            if font < th["major_font_px"]:
                per_line.append(("under_16_px", "major", detail, line["box"], -font))
            elif font < th["min_font_px"]:
                per_line.append(("under_24_px", "minor", detail, line["box"], -font))
            if on_phone < th["min_phone_px"]:
                phone_fail.append((line["box"], font, on_phone))
        hits.extend(aggregate(ctx, "small_text", record["i"], per_line))
        counted = [line for line in lines if line["glyphs"] >= th["min_glyphs"]]
        if phone_fail and counted:
            box = phone_fail[0][0]
            for b, _, _ in phone_fail[1:]:
                box = union(box, b)
            largest = max(f for _, f, _ in phone_fail)
            hits.append(Hit("small_text", "under_12_px_on_phone", record["i"], "note", box, len(phone_fail) / len(counted),
                            {"lines_failing": len(phone_fail), "lines": len(counted),
                             "share": round(len(phone_fail) / len(counted), 3),
                             "largest_failing_font_px_1080p": round(largest, 1),
                             "smallest_phone_px": round(min(p for _, _, p in phone_fail), 1)}, f"shot:{ctx.shot(record['i'])}"))
    return hits


# ---------------------------------------------------------------------------
# 5. Transitions (every frame)
# ---------------------------------------------------------------------------


def _mad(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean())


def _text_mask(record: dict | None, shape: tuple[int, int], width: int, height: int) -> np.ndarray:
    mask = np.zeros(shape, bool)
    if not record:
        return mask
    sy, sx = shape[0] / height, shape[1] / width
    for line in record.get("text") or []:
        x0, y0, x1, y1 = line["box"]
        mask[int(y0 * sy):max(int(y0 * sy) + 1, int(np.ceil(y1 * sy))), int(x0 * sx):max(int(x0 * sx) + 1, int(np.ceil(x1 * sx)))] = True
    return mask


def _nearest_spatial(ctx: Context, frame: int, direction: int) -> dict | None:
    every = int(ctx.spec["sampling"]["spatial_every_frames"])
    for offset in range(0, 4 * every):
        i = frame + direction * offset
        if 0 <= i < len(ctx.records) and "text" in ctx.records[i]:
            return ctx.records[i]
    return None


def _endpoint_blend(small: np.ndarray, a: int, b: int) -> tuple[float, bool]:
    """Worst relative residual of frames a..b-1 against a blend of frame a-1 and frame b, and whether the blend
    weight falls steadily from the first frame to the second."""
    A, B = small[a - 1].astype(np.float32).ravel(), small[b].astype(np.float32).ravel()
    v = A - B
    vv = float(v @ v)
    if vv <= 0 or b <= a:
        return 1.0, False
    alphas, residuals = [], []
    for k in range(a, b):
        f = small[k].astype(np.float32).ravel() - B
        alpha = float(f @ v) / vv
        alphas.append(alpha)
        residuals.append(float(np.linalg.norm(f - alpha * v) / np.sqrt(vv)))
    steady = all(alphas[k + 1] <= alphas[k] + 0.05 for k in range(len(alphas) - 1))
    return max(residuals), steady


def _jump(ctx: Context, A: np.ndarray, B: np.ndarray, th: dict) -> dict:
    """A pop keeps most of the layout and changes a part; a reframe moves the same picture."""
    same = float(np.count_nonzero(np.abs(A - B) < 8)) / A.size
    out: dict[str, Any] = {"unchanged_share": round(same, 3)}
    dx, dy, response = phase_shift(A, B)
    if abs(dx) + abs(dy) >= 1.0 and response >= 0.2:
        moved = cv2.warpAffine(A, np.float32([[1, 0, dx], [0, 1, dy]]), (A.shape[1], A.shape[0]), borderMode=cv2.BORDER_REPLICATE)
        m = 3
        before = float(np.abs(A - B)[m:-m, m:-m].mean())
        after = float(np.abs(moved - B)[m:-m, m:-m].mean())
        if before > 0 and after <= 0.5 * before:
            out["jump"] = "reframe"
            out["shift_px"] = [round(dx * ctx.width / A.shape[1], 1), round(dy * ctx.height / A.shape[0], 1)]
            return out
    if same >= th["jump_same_layout_share"] and 1.0 - same >= th["jump_min_changed_share"]:
        out["jump"] = "pop"
    return out


def classify_transitions(ctx: Context) -> list[dict]:
    """Cuts, pops, reframes, dissolves and motion, from frame differences and the sliding blend fit.

    A dissolve is a run of frames that are each the average of their neighbours two or four frames away, where
    those neighbours differ; it is found even when two slides share a background and the frame changes little
    from one frame to the next. Abrupt changes are frames whose difference or changed share jumps.
    """
    th = ctx.th("transitions")
    T = ctx.temporal
    diff, changed, small = T["diff"], T["changed"], T["small"]
    n = len(diff)
    dissolving = (T["blend_error"] <= th["blend_max_error"]) & (T["blend_share"] >= th["blend_min_share"]) & \
                 (T["blend_distinct"] >= th["blend_min_distinct"])
    events: list[dict] = []
    covered = np.zeros(n, bool)
    runs = _runs(dissolving)
    joined: list[list[int]] = []
    for a, b in runs:
        if joined and a - joined[-1][1] <= 2:
            joined[-1][1] = b
        else:
            joined.append([a, b])
    for a, b in joined:
        start, end = max(1, a - 2), min(n - 1, b + 2)
        if end - start + 1 < th["dissolve_min_frames"] or end - start + 1 > th["dissolve_max_frames"]:
            continue
        residual, steady = _endpoint_blend(small, start, end)
        A, B = small[start - 1].astype(np.float32), small[end].astype(np.float32)
        events.append({"type": "dissolve", "start": start, "end": end, "frames": end - start + 1,
                       "total_change": round(_mad(A, B), 2), "peak_change": round(float(diff[start:end + 1].max()), 2),
                       "blend_residual": round(residual, 3), "steady": steady, "found_by": "blend_fit"})
        covered[start - 1:end + 1] = True
    abrupt = ((diff >= th["change_level"]) | (changed >= th["change_share"])) & ~covered
    abrupt[0] = False
    for a, b in _runs(abrupt):
        A, B = small[a - 1].astype(np.float32), small[b].astype(np.float32)
        length = b - a + 1
        total = _mad(A, B)
        event: dict[str, Any] = {"start": a, "end": b, "frames": length, "total_change": round(total, 2),
                                 "peak_change": round(float(diff[a:b + 1].max()), 2)}
        if length == 1 or (length == 2 and diff[b] < 0.3 * diff[a] and changed[b] < 0.3 * max(changed[a], 1e-9)):
            event.update(_jump(ctx, A, B, th))
            big = diff[a] >= th["cut_level"] or (1.0 - event["unchanged_share"]) >= th["cut_share"]
            event["type"] = "cut" if big and event.get("jump") is None else "change"
        elif th["dissolve_min_frames"] <= length + 1 and length <= th["dissolve_max_frames"]:
            residual, steady = _endpoint_blend(small, a, b)
            if steady and residual <= th["blend_max_residual"]:
                event.update({"type": "dissolve", "blend_residual": round(residual, 3), "steady": steady, "found_by": "endpoint_fit"})
            else:
                event["type"] = "motion"
        else:
            event["type"] = "motion"
        events.append(event)
    events.sort(key=lambda e: (e["start"], e["end"]))
    return events


def blank_kind(ctx: Context, t: int) -> str | None:
    """`black` for a dark frame, `blank` for a flat frame of any brightness (almost no edges at full size), else None."""
    th = ctx.th("transitions")
    T = ctx.temporal
    if T["luma_mean"][t] <= th["black_max_luma"] and T["luma_p99"][t] <= th["black_max_p99"]:
        return "black"
    steps = ctx.records[t].get("grad_p999", 255.0) if t < len(ctx.records) else 255.0
    if T["luma_std"][t] <= th["blank_max_std"] and steps <= th["blank_max_step"]:
        return "blank"
    return None


def detect_transitions(ctx: Context) -> list[Hit]:
    th = ctx.th("transitions")
    small = ctx.temporal["small"]
    n = len(small)
    hits = []
    for event in ctx.transitions:
        a, b = event["start"], event["end"]
        if event["type"] == "dissolve":
            before, after = _nearest_spatial(ctx, a - 2, -1), _nearest_spatial(ctx, b + 1, 1)
            shape = small.shape[1:]
            ma = _text_mask(before, shape, ctx.width, ctx.height)
            mb = _text_mask(after, shape, ctx.width, ctx.height)
            cov_a, cov_b = float(ma.mean()), float(mb.mean())
            overlap = float(np.count_nonzero(ma & mb)) / max(1, min(np.count_nonzero(ma), np.count_nonzero(mb)))
            if cov_a >= th["text_heavy_share"] and cov_b >= th["text_heavy_share"] and overlap >= th["text_ghost_overlap"]:
                severity = "major" if event["frames"] >= 6 else "minor"
                ys, xs = np.nonzero(ma & mb)
                sy, sx = ctx.height / shape[0], ctx.width / shape[1]
                box = (int(xs.min() * sx), int(ys.min() * sy), int((xs.max() + 1) * sx), int((ys.max() + 1) * sy))
                hits.append(Hit("transitions", "double_exposure", (a + b) // 2, severity, box, overlap,
                                {"start_frame": a, "end_frame": b, "frames": event["frames"], "text_share_before": round(cov_a, 3),
                                 "text_share_after": round(cov_b, 3), "text_overlap": round(overlap, 3),
                                 "blend_residual": event.get("blend_residual")}))
        if event.get("jump"):
            severity = "minor" if event["jump"] == "reframe" else "note"
            hits.append(Hit("transitions", "jump_cut", a, severity, None, event["total_change"],
                            {"jump": event["jump"], "unchanged_share": event.get("unchanged_share"),
                             "shift_px": event.get("shift_px"), "change": event["total_change"]}, event["jump"]))
    # Flash frames: one or two frames unlike both neighbours, which agree with each other.
    level, share = th["flash_min_level"], th["flash_return_share"]
    for t in range(1, n - 1):
        for width in range(1, int(th["flash_max_frames"]) + 1):
            if t + width >= n:
                continue
            into = _mad(small[t - 1], small[t])
            out = _mad(small[t + width - 1], small[t + width])
            if into < level or out < level:
                continue
            back = _mad(small[t - 1], small[t + width])
            if back <= share * min(into, out):
                lum = float(ctx.temporal["luma_mean"][t])
                hits.append(Hit("transitions", "flash_frame", t, "major", None, min(into, out),
                                {"frames": width, "into": round(into, 2), "out": round(out, 2), "return": round(back, 2),
                                 "luma": round(lum, 1)}, str(width)))
                break
    # Black and blank frames; a one- or two-frame run that is a flash is reported once, as the flash.
    mean, std = ctx.temporal["luma_mean"], ctx.temporal["luma_std"]
    flash_frames = {h.frame + k for h in hits if h.kind == "flash_frame" for k in range(int(h.detail["frames"]))}
    flagged = [(t, kind) for t in range(n) if (kind := blank_kind(ctx, t)) and t not in flash_frames]
    runs: list[list[tuple[int, str]]] = []
    for t, kind in flagged:
        if runs and runs[-1][-1][0] == t - 1 and runs[-1][-1][1] == kind:
            runs[-1].append((t, kind))
        else:
            runs.append([(t, kind)])
    for run in runs:
        start, end, kind = run[0][0], run[-1][0], run[0][1]
        seconds = (end - start + 1) / ctx.fps
        if start == 0 or end == n - 1:
            severity = "note"
        elif seconds >= 0.5:
            severity = "major"
        else:
            severity = "minor"
        for t, _ in run:
            hits.append(Hit("transitions", f"{kind}_frames", t, severity, None, seconds,
                            {"run_start": start, "run_end": end, "seconds": round(seconds, 3),
                             "luma": round(float(mean[t]), 1), "luma_std": round(float(std[t]), 2)}, kind))
    return hits


# ---------------------------------------------------------------------------
# 6. Freezes and motion (every frame)
# ---------------------------------------------------------------------------


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for i, flag in enumerate(mask):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def detect_freezes_and_motion(ctx: Context) -> list[Hit]:
    th = ctx.th("freezes_and_motion")
    fps = ctx.fps
    diff = ctx.temporal["diff"]
    n = len(diff)
    hits = []
    frozen = diff <= th["freeze_max_level"]
    frozen[0] = False
    freeze_spans = []
    for a, b in _runs(frozen):
        start = a - 1
        seconds = (b - start + 1) / fps
        if seconds < th["freeze_min_s"]:
            continue
        freeze_spans.append((start, b))
        severity = "major" if seconds >= 4.0 else "minor"
        if b == n - 1:
            severity = "note"
        for t in range(start, b + 1):
            hits.append(Hit("freezes_and_motion", "freeze", t, severity, None, seconds,
                            {"start_frame": start, "end_frame": b, "seconds": round(seconds, 2), "at_end": b == n - 1}))
    still = ctx.temporal["still_change"]
    lag = int(th["still_lag_frames"])
    calm = np.nan_to_num(still, nan=1.0) <= th["still_max_changed_share"]
    for a, b in _runs(calm):
        start = max(0, a - lag)
        seconds = (b - start + 1) / fps
        if seconds < th["still_min_s"]:
            continue
        if any(fs <= start and b <= fe for fs, fe in freeze_spans):
            continue
        severity = "minor" if seconds >= th["still_minor_s"] else "note"
        if b == n - 1:
            severity = "note"
        for t in range(start, b + 1):
            hits.append(Hit("freezes_and_motion", "near_static", t, severity, None, seconds,
                            {"start_frame": start, "end_frame": b, "seconds": round(seconds, 2),
                             "changed_share_limit": th["still_max_changed_share"]}))
    # Text moving fast while on screen, from phase correlation under the text boxes.
    scale = ctx.scale_1080
    series = []
    for record in ctx.records:
        motion = record.get("motion")
        if record["i"] in ctx.skip or not motion or motion.get("median_px") is None:
            continue
        series.append((record["i"], float(motion["median_px"]) * scale, motion))
    min_frames = th["text_motion_min_s"] * fps
    every = int(ctx.spec["sampling"]["spatial_every_frames"])
    groups: list[list[tuple[int, float, dict]]] = []
    for item in series:
        if item[1] < th["text_speed_minor_px"]:
            continue
        if groups and item[0] - groups[-1][-1][0] <= 2 * every:
            groups[-1].append(item)
        else:
            groups.append([item])
    for group in groups:
        span = group[-1][0] - group[0][0] + every
        if span < min_frames:
            continue
        peak = max(s for _, s, _ in group)
        severity = "major" if peak >= th["text_speed_major_px"] else "minor"
        for frame, speed, motion in group:
            hits.append(Hit("freezes_and_motion", "text_motion", frame, severity, None, speed,
                            {"text_speed_px_per_frame_1080p": round(speed, 2), "text_speed_px_per_s_1080p": round(speed * fps, 1),
                             "boxes": motion["boxes"], "peak_px_per_frame": round(peak, 2),
                             "at_window_limit": any(m.get("at_window_limit") for _, _, m in group)}))
    # Spikes in camera speed.
    sx, sy = ctx.temporal["shift_x"], ctx.temporal["shift_y"]
    trusted = (ctx.temporal["shift_response"] >= th["shift_min_response"]) & (ctx.temporal["aligned_gain"] >= th["shift_min_gain"])
    speed = np.where(trusted, np.hypot(sx, sy) * scale, 0.0)
    cut_frames = {e["start"] + k for e in ctx.transitions if e["type"] in ("cut", "dissolve", "change") for k in range(-1, e["frames"] + 1)}
    for t in range(1, n):
        if t in cut_frames or t in ctx.skip or not trusted[t]:
            continue
        lo, hi = max(1, t - 15), min(n, t + 16)
        local = np.median(speed[lo:hi])
        if speed[t] >= th["spike_min_px"] and speed[t] >= th["spike_ratio"] * max(local, 0.25):
            hits.append(Hit("freezes_and_motion", "motion_spike", t, "minor", None, float(speed[t]),
                            {"speed_px_per_frame_1080p": round(float(speed[t]), 2), "local_median": round(float(local), 2)}))
    return hits


# ---------------------------------------------------------------------------
# 7. Caption collisions
# ---------------------------------------------------------------------------


def detect_caption_collisions(ctx: Context) -> list[Hit]:
    th = ctx.th("caption_collisions")
    if not ctx.cues:
        return []
    W, H = ctx.width, ctx.height
    band_top = H * (1.0 - th["band_share"])
    hits = []
    for record, lines in spatial_records(ctx):
        cue = active_cue(ctx.cues, ctx.t(record["i"]))
        if cue is None:
            continue
        cbox = caption_box(cue, W, H, th["caption_font_share"], th["char_em"], th["line_gap_em"])
        per_line = []
        for line in lines:
            if line["glyphs"] < th["min_glyphs"] or line["box"][3] <= band_top:
                continue
            under = area(intersect(line["box"], cbox)) > 0
            kind = "under_caption_box" if under else "in_band_beside_caption"
            per_line.append((kind, "major" if under else "minor",
                             {"cue": cue.ident, "cue_text": cue.text[:120], "caption_box": list(cbox), "band_top_px": int(round(band_top))},
                             line["box"], float(area(intersect(line["box"], cbox)))))
        hits.extend(aggregate(ctx, "caption_collisions", record["i"], per_line))
    return hits


# ---------------------------------------------------------------------------
# 8. Contrast
# ---------------------------------------------------------------------------


def detect_contrast(ctx: Context) -> list[Hit]:
    th = ctx.th("contrast")
    scale = ctx.scale_1080
    hits = []
    for record, lines in spatial_records(ctx):
        per_line: list[tuple[str, str, dict, Box, float]] = []
        for line in lines:
            if line["glyphs"] < th["min_glyphs"] or (line["box"][3] - line["box"][1]) < th["min_line_px"]:
                continue
            font = line["font"] * scale
            minimum = th["large_min"] if font >= th["large_font_px"] else th["normal_min"]
            ratio = float(line["contrast"])
            if ratio >= minimum:
                continue
            severity = "major" if ratio < th["major_below"] else "minor"
            kind = "below_2" if ratio < th["major_below"] else "below_minimum"
            per_line.append((kind, severity, {"ratio": round(ratio, 2), "minimum": minimum, "fg": line["fg"], "bg": line["bg"],
                                              "font_px_1080p": round(font, 1)}, line["box"], -ratio))
        hits.extend(aggregate(ctx, "contrast", record["i"], per_line))
    return hits


# ---------------------------------------------------------------------------
# 9. Layered edges
# ---------------------------------------------------------------------------


def detect_layered_edges(ctx: Context) -> list[Hit]:
    th = ctx.th("layered_edges")
    limits = th["busy_density"]
    fps = ctx.fps
    hits = []
    busy = np.array([all(d >= lim for d, lim in zip(r["edges"], limits)) and r["i"] not in ctx.skip for r in ctx.records])
    for a, b in _runs(busy):
        seconds = (b - a + 1) / fps
        if seconds < th["busy_min_s"]:
            continue
        for t in range(a, b + 1):
            hits.append(Hit("layered_edges", "busy_frame", t, "note", None, float(sum(ctx.records[t]["edges"])),
                            {"edge_density": ctx.records[t]["edges"], "limits": limits, "seconds": round(seconds, 2)}))
    W, H = ctx.width, ctx.height
    for record, lines in spatial_records(ctx):
        for panel in record.get("panels") or []:
            if panel["background"]:
                continue
            pbox = tuple(panel["box"])
            if area(pbox) < 0.003 * W * H:
                continue
            for line in lines:
                lb = line["box"]
                inter = area(intersect(lb, pbox))
                total = area(lb)
                if inter <= 0 or inter >= total:
                    continue
                inside = inter / total
                outside = 1.0 - inside
                ox = max(pbox[0] - lb[0], 0) + max(lb[2] - pbox[2], 0)
                oy = max(pbox[1] - lb[1], 0) + max(lb[3] - pbox[3], 0)
                extent = max(ox, oy)
                if inside < 0.1 or outside < th["spill_min_share"] or extent < th["spill_min_px"]:
                    continue
                # Text on a chip inside the panel, or a heading on the panel's own border, is drawn there on purpose
                # when the text's background differs from the panel's fill.
                if np.abs(_hex_bgr(line["bg"]) - _hex_bgr(panel["color"])).max() > 24:
                    continue
                severity = "major" if outside >= th["spill_major_share"] else "minor"
                hits.append(Hit("layered_edges", "spill", record["i"], severity, union(lb, pbox), outside,
                                {"text_box": list(lb), "panel_box": list(pbox), "outside_share": round(outside, 3),
                                 "outside_px": int(extent)}))
    return hits


DETECTOR_FUNCTIONS = {
    "cut_off_content": detect_cut_off_content,
    "cut_off_windows": detect_cut_off_windows,
    "overlaps": detect_overlaps,
    "small_text": detect_small_text,
    "transitions": detect_transitions,
    "freezes_and_motion": detect_freezes_and_motion,
    "caption_collisions": detect_caption_collisions,
    "contrast": detect_contrast,
    "layered_edges": detect_layered_edges,
}


def run_all(ctx: Context, only: Iterable[str] | None = None) -> list[Hit]:
    """Classify transitions first, so spatial detectors skip frames inside a dissolve or a black run."""
    ctx.transitions = classify_transitions(ctx)
    skip = set()
    for event in ctx.transitions:
        if event["type"] == "dissolve":
            skip.update(range(event["start"], event["end"]))
    for t in range(len(ctx.temporal["luma_mean"])):
        if blank_kind(ctx, t):
            skip.add(t)
    ctx.skip = skip
    ctx.shot_ids = ["S01"] * ctx.frames
    for shot in shots(ctx):
        for t in range(shot["start_frame"], shot["end_frame"] + 1):
            if t < ctx.frames:
                ctx.shot_ids[t] = shot["id"]
    hits = []
    for name, function in DETECTOR_FUNCTIONS.items():
        if only and name not in only:
            continue
        hits.extend(function(ctx))
    hits.sort(key=lambda h: (h.detector, h.kind, h.frame, h.box or (0, 0, 0, 0)))
    return hits


def shots(ctx: Context) -> list[dict]:
    """Shots between cuts and dissolve midpoints, and motion transitions that replace most of the frame."""
    n = ctx.frames
    bounds = [0]
    for event in ctx.transitions:
        if event["type"] == "cut":
            bounds.append(event["start"])
        elif event["type"] == "dissolve":
            bounds.append((event["start"] + event["end"] + 1) // 2)
        elif event["type"] == "motion" and event["total_change"] >= 25:
            bounds.append((event["start"] + event["end"] + 1) // 2)
    bounds = sorted(set(b for b in bounds if 0 <= b < n))
    merged = [bounds[0]]
    for b in bounds[1:]:
        if b - merged[-1] >= int(0.5 * ctx.fps):
            merged.append(b)
    out = []
    for k, start in enumerate(merged):
        end = (merged[k + 1] if k + 1 < len(merged) else n) - 1
        out.append({"id": f"S{k + 1:02d}", "start_frame": start, "end_frame": end,
                    "start_s": round(start / ctx.fps, 3), "end_s": round((end + 1) / ctx.fps, 3)})
    return out
