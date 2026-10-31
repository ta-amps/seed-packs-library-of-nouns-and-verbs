"""The `review-sample` verb's tools: draw a seeded, stratified sample of findings for a person or a different
worker to label, and compute each detector's precision from the labels. The labelling is the reviewer's."""

from __future__ import annotations

import math
import random
from typing import Any

from .spec import DETECTORS

LABELS = ("true_positive", "false_positive")


def draw_sample(findings: list[dict], size: int, seed: int) -> list[dict]:
    """At least one finding from every detector that has any, the rest spread by each detector's share,
    each detector's picks drawn with a seeded generator so the same findings give the same sample."""
    by_detector: dict[str, list[dict]] = {}
    for f in sorted(findings, key=lambda f: f["id"]):
        by_detector.setdefault(f["detector"], []).append(f)
    present = [d for d in DETECTORS if by_detector.get(d)]
    if not present:
        return []
    quota = {d: 1 for d in present}
    left = max(0, size - len(present))
    total = sum(len(by_detector[d]) for d in present)
    shares = sorted(present, key=lambda d: (-len(by_detector[d]) / total, d))
    while left > 0:
        progressed = False
        for d in shares:
            if left <= 0:
                break
            want = math.ceil(size * len(by_detector[d]) / total)
            if quota[d] < min(want, len(by_detector[d])):
                quota[d] += 1
                left -= 1
                progressed = True
        if not progressed:
            break
    rng = random.Random(seed)
    picked = []
    for d in present:
        pool = by_detector[d]
        picked.extend(rng.sample(pool, min(quota[d], len(pool))))
    picked.sort(key=lambda f: (DETECTORS.index(f["detector"]), f["id"]))
    return [{"id": f["id"], "cut": f.get("cut"), "detector": f["detector"], "kind": f["kind"], "severity": f["severity"],
             "t_start": f["t_start"], "t_end": f["t_end"], "image": f.get("image_path") or f.get("image"),
             "summary": f["summary"], "label": None, "actionable": None, "note": ""} for f in picked]


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if total == 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)


def precision(labels: list[dict]) -> dict[str, Any]:
    """Precision per detector and overall from labelled sample rows; rows without a label are not counted."""
    rows = [r for r in labels if r.get("label") in LABELS]
    out: dict[str, Any] = {"labelled": len(rows), "unlabelled": len(labels) - len(rows), "detectors": {}}
    for d in DETECTORS:
        mine = [r for r in rows if r["detector"] == d]
        if not mine:
            continue
        tp = sum(1 for r in mine if r["label"] == "true_positive")
        act = sum(1 for r in mine if r.get("actionable") is True)
        out["detectors"][d] = {"labelled": len(mine), "true_positive": tp, "false_positive": len(mine) - tp,
                               "precision": round(tp / len(mine), 3), "wilson_95": wilson(tp, len(mine)),
                               "actionable": act}
    tp = sum(1 for r in rows if r["label"] == "true_positive")
    out["overall"] = {"labelled": len(rows), "true_positive": tp, "precision": round(tp / len(rows), 3) if rows else None,
                      "wilson_95": wilson(tp, len(rows)), "actionable": sum(1 for r in rows if r.get("actionable") is True)}
    return out
