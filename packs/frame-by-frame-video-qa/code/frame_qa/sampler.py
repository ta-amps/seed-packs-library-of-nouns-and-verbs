"""The `sample` verb's work: decode every frame once at thumbnail size for the temporal measurements, then
measure every frame (edges, border bands) and every second frame (text, panels, chips, text motion) at full
size in worker processes. Records come back in frame order, so the output does not depend on scheduling.
"""

from __future__ import annotations

import gzip
import json
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from . import __version__
from .features import border_profile, edge_layers, gray_of, local_contrast, panels, phase_shift, text_motion
from .media import VideoInfo, find_ffmpeg, ffmpeg_version, frames, probe
from .spec import canonical, spec_digest
from .text import TextLine, detect_lines, make_engine

CACHE_FORMAT = "frame-qa.measurements.v3"

_ENGINE = None
_ENGINE_NAME = None


def _engine(name: str):
    global _ENGINE, _ENGINE_NAME
    if _ENGINE is None or _ENGINE_NAME != name:
        cv2.setNumThreads(1)
        _ENGINE = make_engine(name)
        _ENGINE_NAME = name
    return _ENGINE


# ---------------------------------------------------------------------------
# Temporal pass: every frame, at thumbnail size, in the main process
# ---------------------------------------------------------------------------


def _ecc_change(prev: np.ndarray, cur: np.ndarray, level: int) -> float:
    """Share of pixels that changed by at least `level` after aligning `prev` to `cur` (affine, ECC)."""
    warp = np.eye(2, 3, dtype=np.float32)
    a = prev.astype(np.float32)
    b = cur.astype(np.float32)
    try:
        _, warp = cv2.findTransformECC(b, a, warp, cv2.MOTION_AFFINE,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 1e-4), None, 1)
        aligned = cv2.warpAffine(a, warp, (a.shape[1], a.shape[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                                 borderMode=cv2.BORDER_REPLICATE)
    except cv2.error:
        aligned = a
    m = 6
    diff = np.abs(aligned[m:-m, m:-m] - b[m:-m, m:-m])
    return float(np.count_nonzero(diff >= level)) / diff.size


def _blend_fit(window: list[np.ndarray], level: int) -> tuple[float, float, float]:
    """For the middle frame of a nine-frame window: how well it is the average of the frames k before and k after
    (k = 2 or 4), measured only where those two differ by `level` or more.

    Returns (error, share, distinct): error is the mean distance from the average as a share of the ends' mean
    difference (0 for a linear crossfade), share is the part of the frame that changes between the ends, and
    distinct is how far the middle frame is from the nearer end (about 0.5 inside a crossfade, 0 at a cut).
    """
    mid = window[4]
    best = (1.0, 0.0, 0.0)
    for k in (2, 4):
        a, b = window[4 - k], window[4 + k]
        span = np.abs(b - a)
        mask = span >= level
        share = float(mask.mean())
        if share < 0.0005:
            continue
        scale = float(span[mask].mean())
        error = float(np.abs(mid - 0.5 * (a + b))[mask].mean()) / scale
        distinct = min(float(np.abs(mid - a)[mask].mean()), float(np.abs(mid - b)[mask].mean())) / scale
        if error < best[0]:
            best = (error, share, distinct)
    return best


def temporal_pass(path: str, ffmpeg: str, info: VideoInfo, spec: dict) -> dict[str, np.ndarray]:
    tw = int(spec["sampling"]["thumb_width_px"])
    th = max(2, int(round(tw * info.height / info.width / 2)) * 2)
    fm = spec["detectors"]["freezes_and_motion"]["thresholds"]
    lag = int(fm["still_lag_frames"])
    level = int(fm["still_change_level"])
    cols: dict[str, list[float]] = {k: [] for k in ("diff", "changed", "luma_mean", "luma_std", "luma_p99", "still_change",
                                                     "shift_x", "shift_y", "shift_response", "aligned_gain")}
    small = []
    ring: list[np.ndarray] = []
    window9: list[np.ndarray] = []
    blend = []
    prev = None
    hann = cv2.createHanningWindow((tw, th), cv2.CV_32F)
    scale = info.width / tw
    for frame in frames(path, ffmpeg, info.width, info.height, fps=info.fps, scale=(tw, th), gray=True):
        cur = frame.astype(np.float32)
        cols["luma_mean"].append(float(cur.mean()))
        cols["luma_std"].append(float(cur.std()))
        cols["luma_p99"].append(float(np.percentile(cur, 99)))
        small.append(cv2.resize(frame, (tw // 2, th // 2), interpolation=cv2.INTER_AREA))
        if prev is None:
            for key in ("diff", "changed", "shift_x", "shift_y", "shift_response", "aligned_gain"):
                cols[key].append(0.0)
        else:
            delta = np.abs(cur - prev)
            cols["diff"].append(float(delta.mean()))
            cols["changed"].append(float(np.count_nonzero(delta >= level)) / delta.size)
            if float(prev.std()) > 1.0 and float(cur.std()) > 1.0:
                dx, dy, response = phase_shift(prev, cur, hann)
            else:
                dx = dy = response = 0.0
            gain = 0.0
            if abs(dx) + abs(dy) >= 0.25 and float(delta.mean()) > 0:
                moved = cv2.warpAffine(prev, np.float32([[1, 0, dx], [0, 1, dy]]), (tw, th), borderMode=cv2.BORDER_REPLICATE)
                m = 6
                gain = 1.0 - float(np.abs(moved - cur)[m:-m, m:-m].mean()) / max(1e-6, float(delta[m:-m, m:-m].mean()))
            cols["shift_x"].append(float(dx * scale))
            cols["shift_y"].append(float(dy * scale))
            cols["shift_response"].append(float(response))
            cols["aligned_gain"].append(float(gain))
        if len(ring) >= lag:
            cols["still_change"].append(_ecc_change(ring[-lag], frame, level))
        else:
            cols["still_change"].append(float("nan"))
        ring.append(frame.copy())
        if len(ring) > lag:
            ring.pop(0)
        window9.append(cur)
        if len(window9) > 9:
            window9.pop(0)
        if len(window9) == 9:
            blend.append(_blend_fit(window9, level))
        prev = cur
    if not cols["diff"]:
        raise RuntimeError(f"no frames decoded from {Path(path).name}")
    n = len(cols["diff"])
    pad = [(1.0, 0.0, 0.0)] * 4
    fits = (pad + blend + pad)[:n] if n >= 9 else [(1.0, 0.0, 0.0)] * n
    out = {key: np.round(np.array(values, np.float64), 5) for key, values in cols.items()}
    out["blend_error"] = np.round(np.array([f[0] for f in fits], np.float64), 4)
    out["blend_share"] = np.round(np.array([f[1] for f in fits], np.float64), 5)
    out["blend_distinct"] = np.round(np.array([f[2] for f in fits], np.float64), 4)
    out["small"] = np.stack(small)
    return out


# ---------------------------------------------------------------------------
# Spatial pass: full-size frames in workers
# ---------------------------------------------------------------------------


def _chips(frame: np.ndarray, lines: list[TextLine], spec: dict) -> list[dict]:
    """The filled chip or label behind a text line, when its colour differs from what surrounds the line."""
    ov = spec["detectors"]["overlaps"]["thresholds"]
    step = int(ov["chip_color_step"])
    height, width = frame.shape[:2]
    max_area = float(ov["chip_max_area_share"]) * width * height
    out = []
    for index, line in enumerate(lines):
        x0, y0, x1, y1 = line.box
        h = max(1, y1 - y0)
        pad = int(round(1.2 * h))
        rx0, ry0, rx1, ry1 = max(0, x0 - pad), max(0, y0 - pad), min(width, x1 + pad), min(height, y1 + pad)
        ring = frame[ry0:ry1, rx0:rx1].reshape(-1, 3).astype(np.int32)
        bg = np.array([int(line.bg[5:7], 16), int(line.bg[3:5], 16), int(line.bg[1:3], 16)], np.int32)
        if len(ring) == 0:
            continue
        near = np.abs(ring - bg).max(axis=1) <= step
        if near.mean() > 0.85:
            continue
        # Seed the fill on a background pixel inside the line's detection box.
        dx0, dy0, dx1, dy1 = line.det
        region = frame[max(0, dy0):min(height, dy1), max(0, dx0):min(width, dx1)].astype(np.int32)
        match = np.argwhere(np.abs(region - bg).max(axis=2) <= 4)
        if len(match) == 0:
            continue
        sy, sx = (int(v) for v in match[len(match) // 2])
        seed = (max(0, dx0) + sx, max(0, dy0) + sy)
        mask = np.zeros((height + 2, width + 2), np.uint8)
        flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
        cv2.floodFill(frame, mask, seed, (0, 0, 0), (step,) * 3, (step,) * 3, flags)
        filled = mask[1:-1, 1:-1]
        area = int(np.count_nonzero(filled))
        if area == 0 or area > max_area:
            continue
        ys, xs = np.nonzero(filled)
        cx0, cy0, cx1, cy1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        if cy1 - cy0 > 4 * h or cx1 - cx0 < line.width:
            continue
        out.append({"line": index, "box": [cx0, cy0, cx1, cy1], "color": line.bg, "fill_share": round(area / float((cx1 - cx0) * (cy1 - cy0)), 3)})
    return out


def _measure_segment(job: tuple) -> list[dict]:
    path, ffmpeg, info_dict, start, count, spec, engine_name, last_index, known = job
    info = VideoInfo(**info_dict)
    st = spec["sampling"]
    every = int(st["spatial_every_frames"])
    le = spec["detectors"]["layered_edges"]["thresholds"]
    sa = spec["safe_areas"]
    co = spec["detectors"]["cut_off_content"]["thresholds"]
    cw = spec["detectors"]["cut_off_windows"]["thresholds"]
    tx = spec["text"]
    engine = _engine(engine_name)
    extra = 1 if start + count <= last_index else 0
    records: list[dict] = []
    pending: tuple[int, np.ndarray, list[tuple[int, int, int, int]]] | None = None
    index = start
    for frame in frames(path, ffmpeg, info.width, info.height, fps=info.fps, start=start, count=count + extra):
        gray = gray_of(frame)
        if pending is not None:
            p_index, p_gray, p_boxes = pending
            records[p_index - start]["motion"] = text_motion(p_gray, gray, p_boxes)
            pending = None
        if index >= start + count:
            break
        densities, edges = edge_layers(gray, int(le["canny_low"]), int(le["canny_high"]))
        record: dict[str, Any] = {
            "i": index,
            "edges": [round(d, 4) for d in densities],
            "grad_p999": local_contrast(gray),
            "border": border_profile(gray, edges, float(sa["action_safe_share"]), float(sa["title_safe_share"]), int(co["border_step_levels"])),
        }
        if index % every == 0:
            raw = known.get(index) if known else None
            if raw is None:
                raw = [[*box, round(score, 4)] for box, score in engine.detect(frame)]
            lines = detect_lines(engine, frame, gray, int(tx["min_line_px"]), [((b[0], b[1], b[2], b[3]), b[4]) for b in raw])
            record["det_raw"] = raw
            record["text"] = [line.to_json() for line in lines]
            record["chips"] = _chips(frame, lines, spec)
            record["panels"] = panels(frame, int(st["panel_scale"]), float(cw["flat_std"]), float(cw["step_levels"]),
                                      0.0004, 24, float(cw["rect_min"]))
            record["motion"] = None
            pending = (index, gray, [line.box for line in lines])
        records.append(record)
        index += 1
    return records


def _segments(total: int, workers: int, every: int) -> list[tuple[int, int]]:
    size = max(every * 8, int(np.ceil(total / max(1, workers * 6) / every)) * every)
    return [(start, min(size, total - start)) for start in range(0, total, size)]


def sample(video: str | Path, spec: dict, cache_dir: str | Path, *, workers: int = 4, engine: str | None = None,
           ffmpeg: str | None = None, reuse: bool = True, log=print) -> dict:
    """Measure every frame of one video and write the records; reuse a cache that matches exactly."""
    ffmpeg = find_ffmpeg(ffmpeg)
    info = probe(video, ffmpeg)
    engine_name = engine or spec["text"]["engine"]
    described = make_engine(engine_name).describe()
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    sampling_view = {"sampling": spec["sampling"], "text": spec["text"], "safe_areas": spec["safe_areas"],
                     "edges": {k: spec["detectors"]["layered_edges"]["thresholds"][k] for k in ("canny_low", "canny_high")},
                     "border_step": spec["detectors"]["cut_off_content"]["thresholds"]["border_step_levels"],
                     "panels": {k: spec["detectors"]["cut_off_windows"]["thresholds"][k] for k in ("rect_min", "flat_std", "step_levels")},
                     "chips": {k: spec["detectors"]["overlaps"]["thresholds"][k] for k in ("chip_color_step", "chip_max_area_share")},
                     "still": {k: spec["detectors"]["freezes_and_motion"]["thresholds"][k] for k in ("still_lag_frames", "still_change_level")}}
    meta = {
        "format": CACHE_FORMAT,
        "tool_version": __version__,
        "video": info.to_json(),
        "engine": described,
        "ffmpeg": ffmpeg_version(ffmpeg),
        "versions": versions(),
        "sampling_digest": spec_digest(sampling_view),
        "detector_digest": spec_digest({"engine": described, "box_thresh": spec["text"]["box_thresh"],
                                        "every": spec["sampling"]["spatial_every_frames"]}),
    }
    meta_path = cache / "meta.json"
    if reuse and meta_path.is_file() and (cache / "frames.jsonl.gz").is_file() and (cache / "temporal.npz").is_file():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        if canonical({k: v for k, v in old.items() if k != "frames"}) == canonical(meta):
            log(f"sample: reusing measurements in {cache}")
            return old
    log(f"sample: {info.to_json()['path']} {info.width}x{info.height} {info.fps:g} fps, engine {described['engine']}")
    temporal = temporal_pass(str(video), ffmpeg, info, spec)
    total = len(temporal["diff"])
    np.savez_compressed(cache / "temporal.npz", **temporal)
    known = _known_boxes(cache, meta) if reuse else {}
    if known:
        log(f"sample: reusing {len(known)} frames of text-detector boxes from the previous measurement")
    jobs = [(str(video), ffmpeg, _info_dict(info), start, count, spec, engine_name, total - 1,
             {i: known[i] for i in range(start, start + count) if i in known})
            for start, count in _segments(total, workers, int(spec["sampling"]["spatial_every_frames"]))]
    log(f"sample: {total} frames in {len(jobs)} segments on {workers} worker(s)")
    tmp = cache / "frames.jsonl.gz.part"
    done = 0
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as out:
        if workers <= 1:
            results = map(_measure_segment, jobs)
            pool = None
        else:
            pool = mp.get_context("spawn").Pool(workers, initializer=_init_worker, initargs=(engine_name,))
            results = pool.imap(_measure_segment, jobs)
        try:
            for records in results:
                for record in records:
                    out.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                done += len(records)
                log(f"sample: {done}/{total} frames")
        finally:
            if pool is not None:
                pool.close()
                pool.join()
    if done != total:
        raise RuntimeError(f"measured {done} of {total} frames")
    os.replace(tmp, cache / "frames.jsonl.gz")
    meta["frames"] = total
    meta_path.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return meta


def _known_boxes(cache: Path, meta: dict) -> dict[int, list]:
    """Text-detector boxes from an earlier measurement of the same bytes with the same engine and sampling.

    Re-measuring then decodes and measures again but skips the detector, which is most of the cost.
    """
    meta_path, frames_path = cache / "meta.json", cache / "frames.jsonl.gz"
    if not (meta_path.is_file() and frames_path.is_file()):
        return {}
    old = json.loads(meta_path.read_text(encoding="utf-8"))
    same = (old.get("video", {}).get("sha256") == meta["video"]["sha256"] and canonical(old.get("engine")) == canonical(meta["engine"])
            and old.get("detector_digest") == meta.get("detector_digest"))
    if not same:
        return {}
    known = {}
    with gzip.open(frames_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if "det_raw" in record:
                known[record["i"]] = record["det_raw"]
    return known


def _init_worker(engine_name: str) -> None:
    _engine(engine_name)


def _info_dict(info: VideoInfo) -> dict:
    return {"path": info.path, "sha256": info.sha256, "bytes": info.bytes, "codec": info.codec, "width": info.width,
            "height": info.height, "fps_num": info.fps_num, "fps_den": info.fps_den, "duration_s": info.duration_s,
            "frames_estimated": info.frames_estimated}


def load(cache_dir: str | Path) -> tuple[dict, dict[str, np.ndarray], list[dict]]:
    cache = Path(cache_dir)
    meta = json.loads((cache / "meta.json").read_text(encoding="utf-8"))
    temporal = dict(np.load(cache / "temporal.npz"))
    with gzip.open(cache / "frames.jsonl.gz", "rt", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle]
    return meta, temporal, records


def versions() -> dict:
    from importlib.metadata import PackageNotFoundError, version

    out = {"python": ".".join(str(v) for v in __import__("sys").version_info[:3]), "frame_qa": __version__}
    for name in ("numpy", "opencv-python-headless", "onnxruntime", "rapidocr-onnxruntime", "imageio-ffmpeg"):
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = None
    out["opencv_runtime"] = cv2.__version__
    return out
