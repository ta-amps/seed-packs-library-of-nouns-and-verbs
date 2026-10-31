"""Shared fixtures: hand-built measurement records and temporal arrays, so detectors run without a video."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from frame_qa.detectors import Context
from frame_qa.spec import load_spec

PACKS = Path(__file__).resolve().parents[3]
CODE = Path(__file__).resolve().parents[1]


def pack_nouns(pack: str) -> dict[str, dict]:
    source = json.loads((PACKS / pack / "source.json").read_text(encoding="utf-8"))
    return {noun["slug"]: noun["value"] for noun in source["nouns"]}


def line(box, font=30.0, contrast=12.0, glyphs=10, fg="#222222", bg="#f4f0e8", clipped=(), cap=None, xh=None, stroke=3.0):
    cap = font * 0.71 if cap is None else cap
    return {"box": list(box), "det": [box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4], "cap_px": round(cap, 1), "font_px": font,
            "xh_px": round(cap * 0.72, 1) if xh is None else xh, "stroke_px": stroke, "glyphs": glyphs, "fg": fg, "bg": bg,
            "contrast": contrast, "edge_clipped": list(clipped), "score": 1.0}


def border(crossings=0, density=0.0):
    side = {"crossings": crossings, "per_1000px": 0.0, "action_band_density": density, "title_band_density": 0.0}
    return {s: dict(side) for s in ("left", "top", "right", "bottom")}


def record(i, texts=None, panels=None, chips=None, edges=(0.02, 0.03, 0.04), motion=None, spatial=True):
    rec = {"i": i, "edges": list(edges), "grad_p999": 40.0, "border": border()}
    if spatial:
        rec.update({"text": texts or [], "panels": panels or [], "chips": chips or [], "det_raw": [], "motion": motion})
    return rec


def temporal(n, shape=(45, 80), diff=0.5):
    small = np.full((n, *shape), 128, np.uint8)
    for t in range(n):
        small[t, :, :] = 128 + (t % 3)
    return {
        "diff": np.full(n, diff, float), "changed": np.zeros(n), "luma_mean": np.full(n, 128.0), "luma_std": np.full(n, 30.0),
        "luma_p99": np.full(n, 240.0), "still_change": np.full(n, 0.05), "shift_x": np.zeros(n), "shift_y": np.zeros(n),
        "shift_response": np.zeros(n), "aligned_gain": np.zeros(n), "blend_error": np.ones(n), "blend_share": np.zeros(n),
        "blend_distinct": np.zeros(n), "small": small,
    }


def context(records, temporal_arrays=None, cues=None, width=1920, height=1080, fps=30.0, spec=None):
    n = len(records)
    return Context(width, height, fps, n, spec or load_spec(), temporal_arrays or temporal(n), records, cues or [])


def spatial_run(n, texts_fn=None, **kwargs):
    """n frames; every second frame is a spatial record whose text lines come from texts_fn(i)."""
    out = []
    for i in range(n):
        if i % 2 == 0:
            out.append(record(i, texts=texts_fn(i) if texts_fn else [], **kwargs))
        else:
            out.append(record(i, spatial=False))
    return out
