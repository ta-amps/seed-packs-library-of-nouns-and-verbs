"""Connected-component UI region segmentation and optional local Meta SAM mask adapter.

Segments rectangular UI controls, cards, buttons, inputs and panels from a video frame,
and checks whether caption boxes or callout overlays obscure interactive UI regions.

By default this module runs deterministically with OpenCV connected components (or a pure
Python stdlib grid fallback when OpenCV is unavailable). An optional local Meta SAM adapter
(`facebook/sam-vit-base`) converts precomputed or locally loaded SAM segmentation masks into
the same `UIRegion` contract without making any network calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]

SAM_MODEL_ID = "facebook/sam-vit-base"


@dataclass(frozen=True)
class UIRegion:
    """A segmented UI control or panel in frame pixel coordinates (x0, y0, x1, y1)."""

    region_id: str
    role: str
    box: tuple[int, int, int, int]
    area_px: int
    rectangularity: float
    fill_ratio: float
    source: str
    score: float = 1.0
    mask: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "role": self.role,
            "box": list(self.box),
            "area_px": self.area_px,
            "rectangularity": round(self.rectangularity, 4),
            "fill_ratio": round(self.fill_ratio, 4),
            "source": self.source,
            "score": round(self.score, 4),
        }


def _classify_role(w: int, h: int, frame_w: int, frame_h: int, fill_ratio: float) -> str:
    area_share = (w * h) / max(1, frame_w * frame_h)
    aspect = w / max(1, h)
    if area_share >= 0.06:
        return "panel"
    if h <= max(44, int(frame_h * 0.055)) and aspect >= 3.2:
        return "input"
    if h <= max(64, int(frame_h * 0.08)) and 1.4 <= aspect <= 6.5 and fill_ratio >= 0.55:
        return "button"
    if area_share <= 0.012:
        return "badge"
    return "card"


def _segment_stdlib(rows: Sequence[Sequence[Sequence[int]]], min_area_px: int) -> list[UIRegion]:
    """Pure Python connected-component segmentation for nested RGB/BGR lists."""
    h = len(rows)
    w = len(rows[0]) if h else 0
    if h == 0 or w == 0:
        return []
    corners = [rows[0][0], rows[0][w - 1], rows[h - 1][0], rows[h - 1][w - 1]]
    bg = [sum(c[ch] for c in corners) / 4.0 for ch in range(3)]
    fg = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            px = rows[y][x]
            dist = abs(px[0] - bg[0]) + abs(px[1] - bg[1]) + abs(px[2] - bg[2])
            fg[y][x] = dist >= 36.0

    seen = [[False] * w for _ in range(h)]
    regions: list[UIRegion] = []
    idx = 0
    for y0 in range(h):
        for x0 in range(w):
            if not fg[y0][x0] or seen[y0][x0]:
                continue
            stack = [(x0, y0)]
            seen[y0][x0] = True
            min_x = max_x = x0
            min_y = max_y = y0
            area = 0
            while stack:
                cx, cy = stack.pop()
                area += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and fg[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            bw = max_x - min_x + 1
            bh = max_y - min_y + 1
            box_area = bw * bh
            if area < min_area_px or box_area >= int(0.88 * w * h):
                continue
            rect = area / max(1, box_area)
            if rect < 0.45:
                continue
            idx += 1
            role = _classify_role(bw, bh, w, h, rect)
            regions.append(
                UIRegion(
                    region_id=f"ui-cc-{idx:03d}",
                    role=role,
                    box=(min_x, min_y, max_x + 1, max_y + 1),
                    area_px=area,
                    rectangularity=rect,
                    fill_ratio=rect,
                    source="connected_components_stdlib",
                    score=min(1.0, rect),
                    mask=None,
                )
            )
    regions.sort(key=lambda r: (r.box[1], r.box[0], r.region_id))
    return regions


def segment_ui_regions(
    frame_bgr: Any,
    *,
    min_area_px: int = 320,
    min_side_px: int = 16,
    max_frame_share: float = 0.88,
    color_step: float = 24.0,
) -> list[UIRegion]:
    """Segment distinct UI controls, buttons, inputs and panels via connected components."""
    if np is None or not isinstance(frame_bgr, np.ndarray):
        return _segment_stdlib(frame_bgr, min_area_px=min_area_px)
    if frame_bgr.ndim == 2:
        img = np.stack([frame_bgr, frame_bgr, frame_bgr], axis=-1)
    else:
        img = frame_bgr[:, :, :3]
    h, w = img.shape[:2]
    if h == 0 or w == 0:
        return []

    border_pixels = np.concatenate(
        [img[0, :, :], img[h - 1, :, :], img[:, 0, :], img[:, w - 1, :]],
        axis=0,
    ).astype(np.float32)
    bg_color = np.median(border_pixels, axis=0)
    diff = np.abs(img.astype(np.float32) - bg_color).sum(axis=2)
    binary = (diff >= color_step).astype(np.uint8)

    if cv2 is not None:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
        candidates: list[UIRegion] = []
        idx = 0
        for label_id in range(1, num_labels):
            x = int(stats[label_id, cv2.CC_STAT_LEFT])
            y = int(stats[label_id, cv2.CC_STAT_TOP])
            bw = int(stats[label_id, cv2.CC_STAT_WIDTH])
            bh = int(stats[label_id, cv2.CC_STAT_HEIGHT])
            area = int(stats[label_id, cv2.CC_STAT_AREA])
            box_area = bw * bh
            if area < min_area_px or bw < min_side_px or bh < min_side_px:
                continue
            if box_area >= int(max_frame_share * w * h):
                continue
            rect = area / max(1, box_area)
            if rect < 0.42:
                continue
            comp_mask = labels[y : y + bh, x : x + bw] == label_id
            fill_ratio = float(binary[y : y + bh, x : x + bw][comp_mask].mean()) if area > 0 else rect
            idx += 1
            role = _classify_role(bw, bh, w, h, fill_ratio)
            candidates.append(
                UIRegion(
                    region_id=f"ui-cc-{idx:03d}",
                    role=role,
                    box=(x, y, x + bw, y + bh),
                    area_px=area,
                    rectangularity=rect,
                    fill_ratio=fill_ratio,
                    source="connected_components",
                    score=min(1.0, 0.5 * rect + 0.5 * fill_ratio),
                    mask=comp_mask,
                )
            )
        candidates.sort(key=lambda r: (r.box[1], r.box[0], r.region_id))
        return candidates

    return _segment_stdlib(img.tolist(), min_area_px=min_area_px)


class SamMaskAdapter:
    """Optional local adapter for Meta SAM (`facebook/sam-vit-base`) masks with deterministic fallback.

    Never downloads weights over the network. Callers may supply an in-memory `predictor`
    callable returning SAM mask dictionaries or boolean masks, or a `local_model_path` to a
    locally cached `transformers` mask-generation checkpoint (`local_files_only=True`).
    When neither is present, `segment()` falls back cleanly to `segment_ui_regions()`.
    """

    def __init__(
        self,
        model_id: str = SAM_MODEL_ID,
        *,
        local_model_path: str | Path | None = None,
        predictor: Callable[[Any], Sequence[Any]] | None = None,
        min_area_px: int = 320,
        max_frame_share: float = 0.88,
    ) -> None:
        self.model_id = model_id
        self.local_model_path = Path(local_model_path) if local_model_path else None
        self._predictor = predictor
        self.min_area_px = min_area_px
        self.max_frame_share = max_frame_share

    def sam_available(self) -> bool:
        if self._predictor is not None:
            return True
        if self.local_model_path is None or not self.local_model_path.exists():
            return False
        try:
            import transformers  # noqa: F401
        except ImportError:
            return False
        return True

    def _load_local_predictor(self) -> Callable[[Any], Sequence[Any]] | None:
        if self._predictor is not None:
            return self._predictor
        if self.local_model_path is None or not self.local_model_path.exists():
            return None
        try:
            from PIL import Image
            from transformers import pipeline  # type: ignore[import-not-found]
        except ImportError:
            return None

        gen = pipeline(
            "mask-generation",
            model=str(self.local_model_path),
            local_files_only=True,
        )

        def _predict(frame_bgr: Any) -> Sequence[Any]:
            rgb = frame_bgr[:, :, ::-1]
            pil_img = Image.fromarray(rgb)
            out = gen(pil_img)
            masks = out.get("masks", []) if isinstance(out, dict) else []
            scores = out.get("scores", [1.0] * len(masks)) if isinstance(out, dict) else []
            return [{"segmentation": m, "predicted_iou": float(s)} for m, s in zip(masks, scores)]

        self._predictor = _predict
        return self._predictor

    def segment(self, frame_bgr: Any) -> tuple[list[UIRegion], str]:
        """Return `(regions, backend_used)` where `backend_used` is `sam` or `connected_components`."""
        predictor = self._load_local_predictor()
        if predictor is None or np is None:
            return segment_ui_regions(
                frame_bgr,
                min_area_px=self.min_area_px,
                max_frame_share=self.max_frame_share,
            ), "connected_components"

        arr = np.asarray(frame_bgr)
        h, w = arr.shape[:2]
        raw_items = predictor(arr)
        regions: list[UIRegion] = []
        idx = 0
        for item in raw_items:
            if isinstance(item, dict):
                seg = np.asarray(item["segmentation"], dtype=bool)
                score = float(item.get("predicted_iou", item.get("stability_score", 1.0)))
            else:
                seg = np.asarray(item, dtype=bool)
                score = 1.0
            if seg.shape != (h, w):
                continue
            ys, xs = np.nonzero(seg)
            area = int(xs.size)
            if area < self.min_area_px or area >= int(self.max_frame_share * w * h):
                continue
            x0, x1 = int(xs.min()), int(xs.max()) + 1
            y0, y1 = int(ys.min()), int(ys.max()) + 1
            bw, bh = x1 - x0, y1 - y0
            rect = area / max(1, bw * bh)
            crop_mask = seg[y0:y1, x0:x1]
            idx += 1
            role = _classify_role(bw, bh, w, h, rect)
            regions.append(
                UIRegion(
                    region_id=f"ui-sam-{idx:03d}",
                    role=role,
                    box=(x0, y0, x1, y1),
                    area_px=area,
                    rectangularity=rect,
                    fill_ratio=rect,
                    source=f"sam:{self.model_id}",
                    score=score,
                    mask=crop_mask,
                )
            )
        regions.sort(key=lambda r: (r.box[1], r.box[0], r.region_id))
        return regions, f"sam:{self.model_id}"


def detect_ui_mask_occlusions(
    regions: Sequence[UIRegion],
    overlays: Sequence[dict[str, Any]],
    *,
    min_cover_share: float = 0.15,
    major_cover_share: float = 0.35,
) -> list[dict[str, Any]]:
    """Detect when captions or callouts obscure segmented UI controls or panels.

    Each overlay dict provides:
      - `id`: identifier such as `"cue-01"` or `"callout-02"`
      - `kind`: `"caption"` or `"callout"`
      - `box`: `[x0, y0, x1, y1]` in frame pixel coordinates
    """
    hits: list[dict[str, Any]] = []
    for ov in overlays:
        obox = ov["box"]
        ox0, oy0, ox1, oy1 = int(obox[0]), int(obox[1]), int(obox[2]), int(obox[3])
        if ox1 <= ox0 or oy1 <= oy0:
            continue
        ov_kind = str(ov.get("kind", "caption"))
        ov_id = str(ov.get("id", ov_kind))
        hit_kind = "caption_obscures_ui" if ov_kind == "caption" else "callout_obscures_ui"

        for reg in regions:
            rx0, ry0, rx1, ry1 = reg.box
            ix0, iy0 = max(ox0, rx0), max(oy0, ry0)
            ix1, iy1 = min(ox1, rx1), min(oy1, ry1)
            if ix1 <= ix0 or iy1 <= iy0:
                continue

            if np is not None and isinstance(reg.mask, np.ndarray):
                sub = reg.mask[iy0 - ry0 : iy1 - ry0, ix0 - rx0 : ix1 - rx0]
                inter_px = int(np.count_nonzero(sub))
            else:
                inter_px = int((ix1 - ix0) * (iy1 - iy0) * reg.fill_ratio)

            if inter_px <= 0:
                continue
            denom = max(1, min(reg.area_px, (ox1 - ox0) * (oy1 - oy0)) if reg.role == "panel" else reg.area_px)
            cover_share = inter_px / denom
            if cover_share < min_cover_share:
                continue
            severity = "major" if cover_share >= major_cover_share or reg.role in ("button", "input") and cover_share >= 0.25 else "minor"
            hits.append(
                {
                    "detector": "ui_masks",
                    "kind": hit_kind,
                    "severity": severity,
                    "region_id": reg.region_id,
                    "region_role": reg.role,
                    "region_source": reg.source,
                    "overlay_id": ov_id,
                    "overlay_kind": ov_kind,
                    "box": [ix0, iy0, ix1, iy1],
                    "region_box": list(reg.box),
                    "overlay_box": [ox0, oy0, ox1, oy1],
                    "intersection_px": inter_px,
                    "covered_share": round(cover_share, 4),
                }
            )
    hits.sort(key=lambda h: (-h["covered_share"], h["region_id"], h["overlay_id"]))
    return hits
