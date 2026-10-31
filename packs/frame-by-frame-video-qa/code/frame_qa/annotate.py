"""Draw each finding on its frame: one PNG per finding, with its box, the safe areas and its measurements.

Spatial findings are drawn on their representative frame at full size. Temporal findings (flash frames,
double exposures, jump cuts, black runs, freezes, motion) become a strip of the frames around the event.
Frames are decoded once, in order, and only the frames a finding needs are kept.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from .media import VideoInfo, frames

COLORS = {"blocker": (40, 40, 230), "major": (30, 110, 250), "minor": (0, 200, 240), "note": (200, 200, 200)}
GUIDE_TITLE = (240, 200, 40)
GUIDE_ACTION = (80, 220, 120)


def needed_frames(finding: dict, total: int) -> list[int]:
    kind, rep = finding["kind"], finding["rep_frame"]
    d = finding.get("detail") or {}
    if finding["detector"] == "transitions":
        if kind == "flash_frame":
            width = int(d.get("frames", 1))
            picks = [rep - 1, rep, rep + width - 1, rep + width]
        elif kind == "double_exposure":
            a, b = int(d.get("start_frame", rep)), int(d.get("end_frame", rep))
            picks = [a - 1, (a + b) // 2, b]
        elif kind == "jump_cut":
            picks = [rep - 1, rep]
        else:
            picks = [finding["frame_start"] - 1, finding["frame_start"], finding["frame_end"] + 1]
    elif finding["detector"] == "freezes_and_motion":
        if kind in ("freeze", "near_static"):
            picks = [finding["frame_start"], (finding["frame_start"] + finding["frame_end"]) // 2, finding["frame_end"]]
        else:
            picks = [rep - 1, rep, rep + 1]
    else:
        picks = [rep]
    out = []
    for p in picks:
        p = min(max(0, p), total - 1)
        if p not in out:
            out.append(p)
    return out


def _dashed_rect(img: np.ndarray, box: tuple[int, int, int, int], color, dash: int = 14, thickness: int = 1) -> None:
    x0, y0, x1, y1 = box
    for x in range(x0, x1, 2 * dash):
        cv2.line(img, (x, y0), (min(x + dash, x1), y0), color, thickness)
        cv2.line(img, (x, y1), (min(x + dash, x1), y1), color, thickness)
    for y in range(y0, y1, 2 * dash):
        cv2.line(img, (x0, y), (x0, min(y + dash, y1)), color, thickness)
        cv2.line(img, (x1, y), (x1, min(y + dash, y1)), color, thickness)


def _header(img: np.ndarray, lines: list[str], color) -> np.ndarray:
    width = img.shape[1]
    scale = max(0.5, width / 1920 * 0.9)
    pad = int(14 * scale)
    line_h = int(34 * scale)
    bar = np.full((pad * 2 + line_h * len(lines), width, 3), 24, np.uint8)
    cv2.rectangle(bar, (0, 0), (int(10 * scale), bar.shape[0]), color, -1)
    for k, text in enumerate(lines):
        cv2.putText(bar, text, (int(24 * scale), pad + line_h * (k + 1) - int(8 * scale)), cv2.FONT_HERSHEY_SIMPLEX,
                    scale * (0.85 if k == 0 else 0.7), (245, 245, 245) if k == 0 else (205, 205, 205), 1 if k else 2, cv2.LINE_AA)
    return np.vstack([bar, img])


def _label(img: np.ndarray, box, text: str, color) -> None:
    x0, y0 = int(box[0]), int(box[1])
    scale = 0.6
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    ty = y0 - 6 if y0 - th - 10 > 0 else int(box[3]) + th + 8
    tx = min(max(0, x0), img.shape[1] - tw - 6)
    cv2.rectangle(img, (tx, ty - th - 5), (tx + tw + 6, ty + base), (20, 20, 20), -1)
    cv2.putText(img, text, (tx + 3, ty - 2), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def draw_spatial(frame: np.ndarray, finding: dict, spec: dict) -> np.ndarray:
    img = frame.copy()
    height, width = img.shape[:2]
    sa = spec["safe_areas"]
    color = COLORS[finding["severity"]]
    detector = finding["detector"]
    if detector in ("cut_off_content", "cut_off_windows", "small_text", "layered_edges"):
        tx, ty = int(sa["title_safe_share"] * width), int(sa["title_safe_share"] * height)
        ax, ay = int(sa["action_safe_share"] * width), int(sa["action_safe_share"] * height)
        _dashed_rect(img, (tx, ty, width - tx - 1, height - ty - 1), GUIDE_TITLE)
        _dashed_rect(img, (ax, ay, width - ax - 1, height - ay - 1), GUIDE_ACTION)
    d = finding.get("detail") or {}
    if detector == "caption_collisions":
        band = int(d.get("band_top_px", height * 0.82))
        cv2.line(img, (0, band), (width - 1, band), (255, 140, 60), 2)
        if d.get("caption_box"):
            cb = d["caption_box"]
            overlay = img.copy()
            cv2.rectangle(overlay, (cb[0], cb[1]), (cb[2], cb[3]), (255, 140, 60), -1)
            img = cv2.addWeighted(overlay, 0.25, img, 0.75, 0)
            _label(img, cb, "estimated caption box", (255, 170, 90))
    for extra_key, extra_color in (("chip_box", (255, 80, 200)), ("panel_box", (255, 80, 200)), ("text_box", (255, 255, 0))):
        if d.get(extra_key):
            b = d[extra_key]
            cv2.rectangle(img, (b[0], b[1]), (b[2] - 1, b[3] - 1), extra_color, 2)
    for b in d.get("boxes") or []:
        cv2.rectangle(img, (b[0], b[1]), (b[2] - 1, b[3] - 1), (255, 255, 0), 2)
    for b in d.get("cut_text_boxes") or []:
        cv2.rectangle(img, (b[0], b[1]), (b[2] - 1, b[3] - 1), (255, 255, 0), 2)
    if finding.get("box"):
        b = finding["box"]
        cv2.rectangle(img, (b[0] - 2, b[1] - 2), (b[2] + 1, b[3] + 1), color, 3)
        _label(img, b, finding["kind"], color)
    return img


def draw_strip(tiles: list[tuple[int, np.ndarray]], finding: dict, fps: float, tile_width: int = 640) -> np.ndarray:
    color = COLORS[finding["severity"]]
    scaled = []
    for index, frame in tiles:
        h = int(round(frame.shape[0] * tile_width / frame.shape[1]))
        tile = cv2.resize(frame, (tile_width, h), interpolation=cv2.INTER_AREA)
        is_rep = index == finding["rep_frame"]
        cv2.rectangle(tile, (0, 0), (tile_width - 1, h - 1), color if is_rep else (90, 90, 90), 4 if is_rep else 2)
        stamp = f"frame {index}  {index / fps:0.3f} s"
        cv2.rectangle(tile, (0, h - 30), (tile_width, h), (20, 20, 20), -1)
        cv2.putText(tile, stamp, (8, h - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1, cv2.LINE_AA)
        scaled.append(tile)
    gap = np.full((scaled[0].shape[0], 8, 3), 24, np.uint8)
    row = scaled[0]
    for tile in scaled[1:]:
        row = np.hstack([row, gap, tile])
    return row


def header_lines(finding: dict) -> list[str]:
    def ts(seconds: float) -> str:
        return f"{int(seconds // 60)}:{seconds % 60:06.3f}"

    first = f"{finding['id']}  {finding['detector']} / {finding['kind']}  [{finding['severity']}]  {ts(finding['t_start'])} - {ts(finding['t_end'])}  shot {finding.get('shot', '?')}"
    second = finding.get("summary", "")[:150]
    return [first, second]


def render_all(video: str | Path, ffmpeg: str, info: VideoInfo, findings: list[dict], spec: dict, out_dir: str | Path,
               recognizer=None, log=print) -> None:
    """Write `<id>.png` for every finding into out_dir and set its `image` and `image_sha256`; when a text
    recognizer is given, also read the text inside each spatial finding's box on its frame."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    total = max(1, info.frames_estimated)
    wanted: dict[int, list[dict]] = {}
    plans = {}
    for f in findings:
        picks = needed_frames(f, f.get("frames_total", total))
        plans[f["id"]] = picks
        for p in picks:
            wanted.setdefault(p, []).append(f)
    if not wanted:
        return
    have: dict[int, np.ndarray] = {}
    remaining = {f["id"]: set(plans[f["id"]]) for f in findings}
    last = max(wanted)
    by_id = {f["id"]: f for f in findings}
    done = 0
    for index, frame in enumerate(frames(video, ffmpeg, info.width, info.height, fps=info.fps)):
        if index > last:
            break
        if index not in wanted:
            continue
        have[index] = frame
        for f in wanted[index]:
            remaining[f["id"]].discard(index)
            if remaining[f["id"]]:
                continue
            picks = plans[f["id"]]
            if len(picks) == 1:
                if recognizer is not None and f.get("text_boxes"):
                    texts = recognizer(frame, [tuple(b) for b in f["text_boxes"]])
                    f["text"] = [t for t, conf in texts if t and conf >= 0.5][:4]
                image = draw_spatial(frame, f, spec)
            else:
                image = draw_strip([(p, have[p]) for p in picks], f, info.fps)
            image = _header(image, header_lines(f), COLORS[f["severity"]])
            path = out / f"{f['id']}.png"
            ok, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 6])
            if not ok:
                raise RuntimeError(f"could not encode {path.name}")
            data = encoded.tobytes()
            path.write_bytes(data)
            f["image"] = path.name
            f["image_sha256"] = hashlib.sha256(data).hexdigest()
            done += 1
        still_needed = {p for fid, rest in remaining.items() if rest for p in plans[fid]}
        for k in [k for k in have if k not in still_needed]:
            del have[k]
    missing = [fid for fid, rest in remaining.items() if rest]
    for fid in missing:
        by_id[fid]["image"] = None
        by_id[fid]["image_sha256"] = None
    log(f"annotate: {done} image(s), {len(missing)} without frames")
