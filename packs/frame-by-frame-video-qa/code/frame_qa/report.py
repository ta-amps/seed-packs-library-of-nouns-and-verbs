"""The `report` verb's work: findings with ids, shots and findings-to-fixes records; findings.json, a timeline
CSV and chart, and REPORT.md. Output is deterministic for the same measurements, spec and options."""

from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .cluster import Cluster
from .detectors import SEVERITY_RANK
from .spec import DETECTORS, PRIORITY

FINDINGS_FORMAT = "frame-qa.findings.v1"
SHORT = {"cut_off_content": "CUT", "cut_off_windows": "WIN", "overlaps": "OVL", "small_text": "SML", "transitions": "TRN",
         "freezes_and_motion": "MOT", "caption_collisions": "CAP", "contrast": "CON", "layered_edges": "EDG"}
QUESTION = {
    ("cut_off_content", "text_at_edge"): 0, ("cut_off_content", "text_in_action_margin"): 1,
    ("cut_off_content", "text_in_title_margin"): 2, ("cut_off_content", "ui_off_edge"): 3,
    ("cut_off_windows", "panel_at_edge"): 0, ("cut_off_windows", "panel_at_edge_with_cut_text"): 1,
    ("overlaps", "text_on_text"): 0, ("overlaps", "chip_covers_text"): 1,
    ("small_text", "under_24_px"): 0, ("small_text", "under_16_px"): 1, ("small_text", "under_12_px_on_phone"): 2,
    ("transitions", "double_exposure"): 1, ("transitions", "flash_frame"): 2, ("transitions", "jump_cut"): 3,
    ("transitions", "black_frames"): 4, ("transitions", "blank_frames"): 4,
    ("freezes_and_motion", "freeze"): 0, ("freezes_and_motion", "near_static"): 1,
    ("freezes_and_motion", "text_motion"): 2, ("freezes_and_motion", "motion_spike"): 3,
    ("caption_collisions", "in_band_beside_caption"): 0, ("caption_collisions", "under_caption_box"): 1,
    ("contrast", "below_minimum"): 0, ("contrast", "below_2"): 1,
    ("layered_edges", "busy_frame"): 0, ("layered_edges", "spill"): 1,
}
FIX_VERB = {
    "cut_off_content": "reframe the shot or move the text inside the title-safe area",
    "cut_off_windows": "reframe the capture so the window or panel sits inside the frame, or crop it on purpose with a margin",
    "overlaps": "move the callout or the text so nothing covers page text",
    "small_text": "enlarge the text, crop tighter, or say it in narration instead",
    "transitions": "replace the dissolve with a cut, remove the stray frame, or hold the layout across the change",
    "freezes_and_motion": "add a planned build or hold with narration, or slow the move while text is read",
    "caption_collisions": "keep text and proof out of the caption band while a cue shows, or move the cue",
    "contrast": "raise the text's contrast against its background",
    "layered_edges": "simplify the frame, or keep content inside its container",
}


def _ts(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:05.2f}"


def _summary(c: Cluster, rep, fps: float) -> str:
    d = rep.detail
    k = c.kind
    if k == "text_at_edge":
        return f"Text touches the {', '.join(d['sides'])} frame edge ({d['margin_px']} px), so it is likely cut."
    if k == "text_in_action_margin":
        return f"Text sits {d['margin_px']} px from the {', '.join(d['sides'])} edge, inside the 3.5 percent action-safe margin."
    if k == "text_in_title_margin":
        return f"Text sits {d['margin_px']} px from the {', '.join(d['sides'])} edge, inside the 5 percent title-safe margin."
    if k == "ui_off_edge":
        return f"Interface content runs off the {d['side']} edge ({d['crossings']} edge crossings on the frame's outermost pixels)."
    if k == "panel_at_edge":
        return f"A panel ({d['panel_color']}) reaches the {', '.join(d['sides'])} frame edge, so part of it may be outside the frame."
    if k == "panel_at_edge_with_cut_text":
        return f"A panel reaches the {', '.join(d['sides'])} edge and text inside it is cut by the same edge."
    if k == "text_on_text":
        return f"Two text lines overlap by {d['overlap_share']:.0%} of the smaller one."
    if k == "chip_covers_text":
        return f"A callout chip ({d['chip_color']}) covers {d['covered_share']:.0%} of a line of page text."
    if k == "under_16_px":
        return f"Text is about {d['font_px_1080p']:.0f} px at 1080p, under 16 px ({d['phone_px']:.1f} px on a 390 px phone)."
    if k == "under_24_px":
        return f"Text is about {d['font_px_1080p']:.0f} px at 1080p, under 24 px ({d['phone_px']:.1f} px on a 390 px phone)."
    if k == "under_12_px_on_phone":
        return (f"{d['lines_failing']} of {d['lines']} text lines would be under 12 px on a 390 px phone; the largest failing line is "
                f"{d['largest_failing_font_px_1080p']:.0f} px at 1080p.")
    if k == "double_exposure":
        return (f"A {d['frames']}-frame dissolve blends two text-heavy frames: {d['text_overlap']:.0%} of the smaller text area "
                f"lies over the other frame's text.")
    if k == "flash_frame":
        return f"{d['frames']} frame(s) unlike both neighbours, which match each other (change {d['into']:.0f} in, {d['out']:.0f} out)."
    if k == "jump_cut":
        if d["jump"] == "reframe":
            return f"An abrupt jump of the same layout by {d['shift_px']} px inside a shot."
        return f"An element pops in or out abruptly with {d['unchanged_share']:.0%} of the frame unchanged."
    if k in ("black_frames", "blank_frames"):
        return f"{d['seconds']:.2f} s of {k.split('_')[0]} frames."
    if k == "freeze":
        return f"The picture is frozen for {d['seconds']:.2f} s" + (" at the end." if d.get("at_end") else ".")
    if k == "near_static":
        return f"Nothing but a camera drift changes for {d['seconds']:.2f} s."
    if k == "text_motion":
        bound = "at least " if d.get("at_window_limit") else "up to "
        return (f"Text moves at {bound}{d['peak_px_per_frame']:.1f} px a frame ({d['peak_px_per_frame'] * fps:.0f} px a second at 1080p) "
                "while on screen.")
    if k == "motion_spike":
        return f"Camera speed spikes to {d['speed_px_per_frame_1080p']:.1f} px a frame against a local median of {d['local_median']:.1f}."
    if k == "under_caption_box":
        return f"Text sits where the player draws caption {d['cue']} (“{d['cue_text'][:60]}”)."
    if k == "in_band_beside_caption":
        return f"Text sits in the bottom 18 percent band while caption {d['cue']} shows."
    if k == "below_2":
        return f"Text contrast is {d['ratio']:.2f} to 1 ({d['fg']} on {d['bg']}), under 2 to 1."
    if k == "below_minimum":
        return f"Text contrast is {d['ratio']:.2f} to 1 ({d['fg']} on {d['bg']}), under its {d['minimum']} to 1 minimum."
    if k == "busy_frame":
        return f"Dense edges at all three scales ({d['edge_density']}) for {d['seconds']:.1f} s."
    if k == "spill":
        return f"Text crosses its panel's boundary: {d['outside_share']:.0%} of it ({d['outside_px']} px) lies outside."
    return k.replace("_", " ")


def shot_of(shots: list[dict], frame: int) -> str:
    for shot in shots:
        if shot["start_frame"] <= frame <= shot["end_frame"]:
            return shot["id"]
    return shots[-1]["id"] if shots else "S01"


def storyboard_of(board: list[dict], seconds: float) -> str | None:
    current = None
    for row in board:
        if row["start_s"] <= seconds + 1e-6:
            current = row["id"]
    return current


def parse_storyboard(text: str) -> list[dict]:
    """Shot rows of a markdown table: `| shot04 | 0:24.30 | ... |`."""
    rows = []
    for match in re.finditer(r"^\|\s*([A-Za-z][\w.-]*)\s*\|\s*(\d+):(\d{2}(?:\.\d+)?)\s*\|", text, re.MULTILINE):
        rows.append({"id": match.group(1), "start_s": int(match.group(2)) * 60 + float(match.group(3))})
    rows.sort(key=lambda r: r["start_s"])
    return rows


def finding_record(f: dict, label: str, video_name: str, noticed_at: str) -> dict | None:
    """A findings-to-fixes `template.finding` instance for every finding above note."""
    priority = PRIORITY[f["severity"]]
    if priority is None:
        return None
    symptom = f["kind"].replace("_", "-")
    component = re.sub(r"[^a-z0-9-]+", "-", f"film-{label}-{f['detector'].replace('_', '-')}").strip("-")[:60]
    evidence = [{
        "kind": "measurement",
        "detail": f"{f['summary']} Measured by frame-by-frame video QA {f['detector']} on {video_name}.",
        "location": f"{video_name} frames {f['frame_start']}-{f['frame_end']} ({_ts(f['t_start'])}-{_ts(f['t_end'])})",
    }]
    if f.get("image") and f.get("image_sha256"):
        evidence.append({"kind": "screenshot", "detail": f"Annotated frame {f['rep_frame']} with the finding's box.",
                         "location": f["image"], "sha256": f["image_sha256"], "widths_px": [f["frame_width"]]})
    return {
        "id": f["id"],
        "title": f["summary"][:300],
        "kind": "design_flaw",
        "severity": priority,
        "where": f"{video_name} at {_ts(f['t_start'])} ({f.get('shot', '')})"[:300],
        "expected": FIX_VERB[f["detector"]][:600],
        "evidence": evidence,
        "noticed_by": "frame-by-frame video QA (automated detector; a person confirms)",
        "noticed_at": noticed_at,
        "fingerprint": f"design_flaw/{component}/{symptom}",
        "status": "open",
        "sensitivity": "none",
        "public": False,
    }


def build_findings(clusters: list[Cluster], label: str, fps: float, width: int, height: int, total_frames: int,
                   shots: list[dict], board: list[dict], video_name: str, noticed_at: str) -> list[dict]:
    findings = []
    counters: dict[str, int] = {}
    ordered = sorted(clusters, key=lambda c: (c.first, DETECTORS.index(c.detector), c.kind, c.union_box or (0, 0, 0, 0)))
    for c in ordered:
        rep = c.representative
        code = SHORT[c.detector]
        counters[code] = counters.get(code, 0) + 1
        fid = f"{label}-{code}-{counters[code]:03d}"
        temporal = c.detector in ("transitions", "freezes_and_motion")
        if c.kind in ("freeze", "near_static", "black_frames", "blank_frames"):
            first = int(rep.detail.get("start_frame", rep.detail.get("run_start", c.first)))
            last = int(rep.detail.get("end_frame", rep.detail.get("run_end", c.last)))
        elif c.kind == "double_exposure":
            first, last = int(rep.detail["start_frame"]), int(rep.detail["end_frame"])
        else:
            first, last = c.first, c.last
        span_end = last + 1 if temporal else last + 2
        text_boxes = []
        if rep.box is not None and c.detector in ("cut_off_content", "small_text", "contrast", "caption_collisions") and c.kind != "ui_off_edge":
            text_boxes = [list(rep.box)]
        elif c.kind == "chip_covers_text":
            text_boxes = [rep.detail["text_box"]]
        elif c.kind == "text_on_text":
            text_boxes = rep.detail["boxes"]
        elif c.kind == "spill":
            text_boxes = [rep.detail["text_box"]]
        f = {
            "id": fid,
            "detector": c.detector,
            "kind": c.kind,
            "severity": rep.severity,
            "priority": PRIORITY[rep.severity],
            "question": QUESTION.get((c.detector, c.kind), 0),
            "frame_start": first,
            "frame_end": min(last, total_frames - 1),
            "t_start": round(first / fps, 3),
            "t_end": round(min(span_end, total_frames) / fps, 3),
            "duration_s": round((min(span_end, total_frames) - first) / fps, 3),
            "intervals_s": [[round(a / fps, 3), round(min(b + (1 if temporal else 2), total_frames) / fps, 3)] for a, b in c.intervals],
            "frames_hit": len({h.frame for h in c.hits}),
            "rep_frame": rep.frame,
            "rep_t": round(rep.frame / fps, 3),
            "box": list(rep.box) if rep.box else None,
            "union_box": list(c.union_box) if c.union_box else None,
            "detail": rep.detail,
            "summary": _summary(c, rep, fps),
            "shot": shot_of(shots, rep.frame),
            "storyboard_shot": storyboard_of(board, rep.frame / fps) if board else None,
            "frame_width": width,
            "frame_height": height,
            "frames_total": total_frames,
            "text_boxes": text_boxes,
            "text": [],
            "image": None,
            "image_sha256": None,
        }
        findings.append(f)
    return findings


def attach_records(findings: list[dict], label: str, video_name: str, noticed_at: str) -> None:
    for f in findings:
        f["record"] = finding_record(f, label, video_name, noticed_at)


def counts(findings: list[dict]) -> dict:
    out: dict[str, Any] = {}
    for name in DETECTORS:
        rows = [f for f in findings if f["detector"] == name]
        out[name] = {"findings": len(rows), **{s: sum(1 for f in rows if f["severity"] == s) for s in ("blocker", "major", "minor", "note")},
                     "kinds": {k: sum(1 for f in rows if f["kind"] == k) for k in sorted({f["kind"] for f in rows})}}
    return out


def rank_key(f: dict) -> tuple:
    weight = {"overlaps": 6, "caption_collisions": 6, "cut_off_content": 5, "transitions": 5, "cut_off_windows": 4,
              "contrast": 4, "small_text": 3, "freezes_and_motion": 3, "layered_edges": 1}[f["detector"]]
    return (-SEVERITY_RANK[f["severity"]], -weight, -min(f["duration_s"], 30.0), f["t_start"], f["id"])


def write_timeline_csv(path: Path, cuts: list[dict]) -> None:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["cut", "id", "detector", "kind", "severity", "t_start", "t_end", "duration_s", "shot", "storyboard_shot", "rep_t", "summary"])
    for cut in cuts:
        for f in cut["findings"]:
            writer.writerow([cut["label"], f["id"], f["detector"], f["kind"], f["severity"], f"{f['t_start']:.3f}", f"{f['t_end']:.3f}",
                             f"{f['duration_s']:.3f}", f["shot"], f.get("storyboard_shot") or "", f"{f['rep_t']:.3f}", f["summary"]])
    path.write_text(buf.getvalue(), encoding="utf-8")


def draw_timeline(path: Path, cut: dict) -> None:
    """Detectors as rows, time across, a bar per finding coloured by severity; shot boundaries as ticks."""
    duration = max(1e-3, cut["video"]["duration_s"])
    left, top, row_h, width = 230, 70, 34, 1800
    height = top + row_h * len(DETECTORS) + 60
    img = np.full((height, left + width + 30, 3), 250, np.uint8)
    colors = {"blocker": (40, 40, 200), "major": (40, 110, 235), "minor": (40, 190, 235), "note": (180, 180, 180)}
    cv2.putText(img, f"{cut['label']}  {cut['video']['path']}  {cut['video']['sha256'][:12]}  {len(cut['findings'])} findings",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 1, cv2.LINE_AA)
    for k, name in enumerate(DETECTORS):
        y = top + k * row_h
        cv2.rectangle(img, (left, y), (left + width, y + row_h - 6), (238, 238, 238), -1)
        cv2.putText(img, name, (10, y + row_h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 40), 1, cv2.LINE_AA)
    for shot in cut.get("shots", []):
        x = left + int(width * shot["start_s"] / duration)
        cv2.line(img, (x, top - 8), (x, top + row_h * len(DETECTORS)), (205, 205, 205), 1)
    order = sorted(cut["findings"], key=lambda f: SEVERITY_RANK[f["severity"]])
    for f in order:
        k = DETECTORS.index(f["detector"])
        y = top + k * row_h
        for a, b in f["intervals_s"]:
            x0 = left + int(width * a / duration)
            x1 = max(x0 + 2, left + int(width * b / duration))
            cv2.rectangle(img, (x0, y + 3), (x1, y + row_h - 9), colors[f["severity"]], -1)
    for s in range(0, int(math.ceil(duration)) + 1, 10 if duration > 60 else 5):
        x = left + int(width * s / duration)
        cv2.line(img, (x, height - 52), (x, height - 44), (60, 60, 60), 1)
        cv2.putText(img, _ts(s)[:-3], (x - 16, height - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 60), 1, cv2.LINE_AA)
    lx = left
    for name in ("blocker", "major", "minor", "note"):
        cv2.rectangle(img, (lx, 40), (lx + 18, 54), colors[name], -1)
        cv2.putText(img, name, (lx + 24, 53), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)
        lx += 110
    ok, data = cv2.imencode(".png", img)
    path.write_bytes(data.tobytes())


def dumps(document: Any) -> str:
    return json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
