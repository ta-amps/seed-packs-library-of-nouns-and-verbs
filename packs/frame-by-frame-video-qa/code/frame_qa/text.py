"""Find text lines in a frame and measure each one: its glyph box, letter heights, colours and contrast.

Two engines find text lines. `ocr` runs the PP-OCRv4 text detector bundled with rapidocr-onnxruntime on
the CPU with one thread, which is deterministic on one machine. `cv` is a model-free fallback from
OpenCV morphology; it finds more false lines on busy user interfaces. Both hand their boxes to the same
measurement, which works from the pixels: Otsu inside the box, the background taken from the box's rim.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import cv2
import numpy as np

# Cap or ascender height as a share of the font size, measured on the film's fonts (see the pack's spec).
CAP_EM = 0.71


def srgb_luminance(bgr: tuple[float, float, float]) -> float:
    """WCAG relative luminance of an 8-bit sRGB colour given as (B, G, R)."""
    def channel(value: float) -> float:
        c = value / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    b, g, r = bgr
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, lb = srgb_luminance(a), srgb_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hex_color(bgr: tuple[float, float, float]) -> str:
    b, g, r = (int(round(min(255.0, max(0.0, v)))) for v in bgr)
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class TextLine:
    """One measured text line in frame pixels. Boxes are (x0, y0, x1, y1), with x1 and y1 exclusive."""

    box: tuple[int, int, int, int]
    det: tuple[int, int, int, int]
    cap_px: float
    font_px: float
    xh_px: float
    stroke_px: float
    glyphs: int
    fg: str
    bg: str
    contrast: float
    edge_clipped: tuple[str, ...]
    score: float

    @property
    def height(self) -> int:
        return self.box[3] - self.box[1]

    @property
    def width(self) -> int:
        return self.box[2] - self.box[0]

    def to_json(self) -> dict:
        return {
            "box": list(self.box), "det": list(self.det), "cap_px": round(self.cap_px, 1),
            "font_px": round(self.font_px, 1), "xh_px": round(self.xh_px, 1), "stroke_px": round(self.stroke_px, 1),
            "glyphs": self.glyphs, "fg": self.fg, "bg": self.bg, "contrast": round(self.contrast, 2),
            "edge_clipped": list(self.edge_clipped), "score": round(self.score, 3),
        }

    @staticmethod
    def from_json(data: dict) -> "TextLine":
        return TextLine(tuple(data["box"]), tuple(data["det"]), data["cap_px"], data["font_px"], data["xh_px"],
                        data["stroke_px"], data["glyphs"], data["fg"], data["bg"], data["contrast"],
                        tuple(data["edge_clipped"]), data["score"])


def _free_marks(marks: list[tuple[int, int, int, int, int]], others: list[tuple[int, int, int, int, int]]) -> int:
    """Marks (id, left, top, w, h) that no mark of the other class encloses."""
    free = 0
    for _, left, top, w, h in marks:
        enclosed = any(ol < left and ot < top and ol + ow > left + w and ot + oh > top + h
                       for _, ol, ot, ow, oh in others)
        free += 0 if enclosed else 1
    return free


def _rim_mask(height: int, width: int, band: int = 2) -> np.ndarray:
    rim = np.zeros((height, width), bool)
    rim[:band] = rim[-band:] = True
    rim[:, :band] = rim[:, -band:] = True
    return rim


def measure_line(frame: np.ndarray, gray: np.ndarray, det: tuple[int, int, int, int], score: float = 1.0) -> TextLine | None:
    """Measure the glyphs inside one detected box, or None when the box holds no glyph-like pixels."""
    height, width = gray.shape
    x0, y0, x1, y1 = det
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(width, x1), min(height, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    crop = gray[y0:y1, x0:x1]
    if int(crop.max()) - int(crop.min()) < 12:
        return None
    _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    on = binary > 0
    ch, cw = crop.shape
    frame_edges = {"left": x0 == 0, "top": y0 == 0, "right": x1 == width, "bottom": y1 == height}
    # Glyphs are the Otsu class made of many small marks; the background is one large region. When the
    # box spills past a chip, the page at the rim is a third, bright region, so the rim alone can mislead.
    candidates = []
    for cls in (~on, on):
        count, labels, stats, _ = cv2.connectedComponentsWithStats(cls.astype(np.uint8), connectivity=8)
        keep = []
        for i in range(1, count):
            left, top, w, h, area = (int(v) for v in stats[i])
            if area < 3 or h < 2:
                continue
            touches = (left == 0 and not frame_edges["left"]) or (top == 0 and not frame_edges["top"]) or \
                      (left + w == cw and not frame_edges["right"]) or (top + h == ch and not frame_edges["bottom"])
            # Rules, panel borders, chips and backgrounds run along the box or fill much of it; a glyph does neither.
            if (touches and (w > 0.9 * cw or h > 0.9 * ch)) or (w > 0.6 * cw and h > 0.8 * ch) or area > 0.35 * cw * ch:
                continue
            keep.append((i, left, top, w, h))
        candidates.append((keep, labels, float(cls[_rim_mask(ch, cw)].mean())))
    (keep_dark, labels_dark, rim_dark), (keep_light, labels_light, rim_light) = candidates
    # The counters of letters (the inside of o, e, a) are marks of the other class enclosed by a letter.
    free_dark = _free_marks(keep_dark, keep_light)
    free_light = _free_marks(keep_light, keep_dark)
    if free_dark == free_light:
        dark_glyphs = rim_dark < rim_light
    else:
        dark_glyphs = free_dark > free_light
    keep, labels = (keep_dark, labels_dark) if dark_glyphs else (keep_light, labels_light)
    if not keep:
        return None
    ids = np.array([k[0] for k in keep])
    lefts = np.array([k[1] for k in keep])
    tops = np.array([k[2] for k in keep])
    widths = np.array([k[3] for k in keep])
    heights = np.array([k[4] for k in keep])
    # Drop specks far smaller than the line's letters, such as compression noise.
    tall = float(np.percentile(heights, 90))
    good = heights >= max(2.0, 0.25 * tall)
    if not good.any():
        return None
    ids, lefts, tops, widths, heights = ids[good], lefts[good], tops[good], widths[good], heights[good]
    bottoms = tops + heights
    gx0, gy0 = int(lefts.min()), int(tops.min())
    gx1, gy1 = int((lefts + widths).max()), int(bottoms.max())
    baseline = float(np.percentile(bottoms, 60))
    body = bottoms <= baseline + max(1.0, 0.12 * tall)
    above = (baseline - tops[body]) if body.any() else heights.astype(float)
    cap = float(np.percentile(above, 90))
    xh = float(np.percentile(above, 30))
    font = cap / CAP_EM if cap > 0 else 0.0
    mask = np.isin(labels, ids)
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    stroke = float(2.0 * np.percentile(dist[mask], 90)) if mask.any() else 0.0
    # Colours: the background from a thin ring just outside the strokes, so a chip's own fill is used and not
    # the page beyond it; the foreground from the strokes' cores.
    frame_crop = frame[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
    m8 = mask.astype(np.uint8)
    near = cv2.dilate(m8, np.ones((3, 3), np.uint8)) > 0
    ring_px = max(3, int(round(0.25 * max(2.0, cap))))
    outer = cv2.dilate(m8, np.ones((2 * ring_px + 1, 2 * ring_px + 1), np.uint8)) > 0
    bg_pixels = frame_crop[(outer & ~near).ravel()]
    if len(bg_pixels) < 8:
        bg_pixels = frame_crop[~mask.ravel()]
    if len(bg_pixels) < 1:
        return None
    bg = tuple(float(v) for v in np.median(bg_pixels, axis=0))
    fg_pixels = frame_crop[mask.ravel()]
    lum = fg_pixels @ np.array([0.0722, 0.7152, 0.2126], dtype=np.float32)
    bg_lum = 0.0722 * bg[0] + 0.7152 * bg[1] + 0.2126 * bg[2]
    far = np.abs(lum - bg_lum)
    core = fg_pixels[far >= np.percentile(far, 75)] if len(far) >= 4 else fg_pixels
    fg = tuple(float(v) for v in np.median(core, axis=0))
    clipped = []
    if frame_edges["left"] and gx0 == 0:
        clipped.append("left")
    if frame_edges["top"] and gy0 == 0:
        clipped.append("top")
    if frame_edges["right"] and x0 + gx1 == width:
        clipped.append("right")
    if frame_edges["bottom"] and y0 + gy1 == height:
        clipped.append("bottom")
    return TextLine(
        box=(x0 + gx0, y0 + gy0, x0 + gx1, y0 + gy1),
        det=(x0, y0, x1, y1),
        cap_px=cap,
        font_px=font,
        xh_px=xh,
        stroke_px=stroke,
        glyphs=int(len(heights)),
        fg=hex_color(fg),
        bg=hex_color(bg),
        contrast=contrast_ratio(fg, bg),
        edge_clipped=tuple(clipped),
        score=float(score),
    )


class OcrEngine:
    """PP-OCRv4 text detection and recognition from rapidocr-onnxruntime, on the CPU with one thread."""

    name = "ocr"

    def __init__(self, box_thresh: float = 0.5, threads: int = 1) -> None:
        import rapidocr_onnxruntime
        from rapidocr_onnxruntime.ch_ppocr_det import TextDetector

        self.models = os.path.join(os.path.dirname(rapidocr_onnxruntime.__file__), "models")
        self.threads = threads
        self.version = getattr(rapidocr_onnxruntime, "__version__", None) or _dist_version("rapidocr-onnxruntime")
        self.config = {
            "intra_op_num_threads": threads, "inter_op_num_threads": threads, "use_cuda": False, "use_dml": False,
            "model_path": os.path.join(self.models, "ch_PP-OCRv4_det_infer.onnx"),
            "limit_side_len": 736, "limit_type": "min", "std": [0.5, 0.5, 0.5], "mean": [0.5, 0.5, 0.5],
            "thresh": 0.3, "box_thresh": box_thresh, "max_candidates": 1000, "unclip_ratio": 1.6,
            "use_dilation": True, "score_mode": "fast",
        }
        self.detector = TextDetector(self.config)
        self._recognizer = None

    def describe(self) -> dict:
        return {"engine": "ocr", "detector": "PP-OCRv4 det (rapidocr-onnxruntime)", "package_version": self.version,
                "onnxruntime": _dist_version("onnxruntime"), "threads": self.threads,
                "box_thresh": self.config["box_thresh"], "unclip_ratio": self.config["unclip_ratio"]}

    def detect(self, frame: np.ndarray) -> list[tuple[tuple[int, int, int, int], float]]:
        boxes, _ = self.detector(frame)
        out = []
        if boxes is None:
            return out
        for poly in boxes:
            pts = np.asarray(poly, dtype=np.float32)
            x0, y0 = np.floor(pts.min(axis=0)).astype(int)
            x1, y1 = np.ceil(pts.max(axis=0)).astype(int) + 1
            out.append(((int(x0), int(y0), int(x1), int(y1)), 1.0))
        out.sort(key=lambda item: (item[0][1], item[0][0]))
        return out

    def recognize(self, frame: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> list[tuple[str, float]]:
        if not boxes:
            return []
        if self._recognizer is None:
            from rapidocr_onnxruntime.ch_ppocr_rec import TextRecognizer

            self._recognizer = TextRecognizer({
                "intra_op_num_threads": self.threads, "inter_op_num_threads": self.threads, "use_cuda": False,
                "use_dml": False, "model_path": os.path.join(self.models, "ch_PP-OCRv4_rec_infer.onnx"),
                "rec_img_shape": [3, 48, 320], "rec_batch_num": 6,
            })
        height, width = frame.shape[:2]
        crops = []
        for x0, y0, x1, y1 in boxes:
            pad = max(2, (y1 - y0) // 4)
            crops.append(frame[max(0, y0 - pad):min(height, y1 + pad), max(0, x0 - pad):min(width, x1 + pad)].copy())
        result, _ = self._recognizer(crops)
        return [(str(text), float(conf)) for text, conf in result]


class CvEngine:
    """A model-free text-line finder: morphological gradient, Otsu, a horizontal close, then shape filters."""

    name = "cv"

    def describe(self) -> dict:
        return {"engine": "cv", "detector": "OpenCV morphological gradient and horizontal close", "model": None}

    def detect(self, frame: np.ndarray) -> list[tuple[tuple[int, int, int, int], float]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        _, binary = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        binary = cv2.threshold(grad, max(24, _otsu(grad)), 255, cv2.THRESH_BINARY)[1]
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (max(9, width // 160), 1)))
        count, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
        out = []
        for i in range(1, count):
            left, top, w, h, area = (int(v) for v in stats[i])
            if h < 6 or h > height // 4 or w < 0.8 * h or w > 0.98 * width:
                continue
            fill = area / float(w * h)
            if fill < 0.25 or fill > 0.97:
                continue
            region = binary[top:top + h, left:left + w] > 0
            density = float(region.mean())
            if density < 0.12:
                continue
            # A text line has many vertical stroke edges; a filled bar or a rule has few.
            transitions = np.count_nonzero(np.diff(region[h // 2].astype(np.int8)))
            if transitions < max(4, w // max(1, 2 * h)):
                continue
            pad = max(2, h // 5)
            out.append(((max(0, left - pad), max(0, top - pad), min(width, left + w + pad), min(height, top + h + pad)), 1.0))
        out.sort(key=lambda item: (item[0][1], item[0][0]))
        return out

    def recognize(self, frame: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> list[tuple[str, float]]:
        return [("", 0.0) for _ in boxes]


def _otsu(values: np.ndarray) -> int:
    threshold, _ = cv2.threshold(values, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return int(threshold)


def _dist_version(name: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:  # noqa: BLE001
        return None


def make_engine(name: str = "auto"):
    """`ocr`, `cv`, or `auto` (ocr when rapidocr-onnxruntime imports, else cv)."""
    if name not in {"auto", "ocr", "cv"}:
        raise ValueError(f"unknown text engine {name!r}")
    if name in {"auto", "ocr"}:
        try:
            return OcrEngine()
        except ImportError:
            if name == "ocr":
                raise
    return CvEngine()


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


def detect_lines(engine, frame: np.ndarray, gray: np.ndarray | None = None, min_height: int = 5,
                 boxes: list[tuple[tuple[int, int, int, int], float]] | None = None) -> list[TextLine]:
    """Detect text lines (or take boxes the engine found earlier on the same frame) and measure each one."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if gray is None else gray
    lines = []
    for det, score in (engine.detect(frame) if boxes is None else boxes):
        line = measure_line(frame, gray, det, score)
        if line is not None and line.height >= min_height and line.glyphs >= 1:
            lines.append(line)
    return lines
