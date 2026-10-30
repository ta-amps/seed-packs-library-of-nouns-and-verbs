"""Picture and sound checks from parsed FFmpeg logs and the cut's plan.

The plan declares, before anything is measured, where a still hold, a black frame or a pause is meant to
be: {"duration_s": 20, "fps": 30, "holds": [[start, end, why]], "black": [...], "pauses": [...]}.
A finding inside a declared span is not a problem; everything else is reported with its times.
Each check returns one row: pass, warn, fail or not_run, its measurement, its limit and its findings.
Thresholds are defaults from one production, not standards; a requester can override any of them.
"""

from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, Any] = {
    "black_min_s": 0.5,
    "uniform_max_range": 16,
    "freeze_warn_s": 1.5,
    "freeze_fail_s": 2.0,
    "hold_tail_s": 0.75,
    "cut_score": 0.12,
    "still_score": 0.002,
    "still_warn_s": 4.0,
    "target_lufs": -16.0,
    "tolerance_lu": 1.0,
    "true_peak_max_dbtp": -1.0,
    "lra_max_lu": 10.0,
    "short_term_floor_lufs": -28.0,
    "skip_edges_s": 3.0,
    "silence_warn_s": 0.5,
    "silence_fail_s": 2.0,
    "clip_peak_dbfs": -0.1,
    "clip_peak_count": 3,
}


def _limits(overrides: dict[str, Any] | None) -> dict[str, Any]:
    unknown = set(overrides or {}) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"unknown limits {sorted(unknown)}")
    return {**DEFAULTS, **(overrides or {})}


def inside(start: float, end: float, spans: list[list[Any]], tail: float = 0.0) -> bool:
    """True when [start, end] lies within one declared span, allowing `tail` seconds after it."""
    return any(s - 1e-6 <= start and end <= e + tail + 1e-6 for s, e, *_ in spans)


def row(check: str, findings: list[dict[str, Any]], measured: dict[str, Any], limit: dict[str, Any],
        severities: list[str]) -> dict[str, Any]:
    result = "fail" if "fail" in severities else ("warn" if "warn" in severities else "pass")
    return {"check": check, "result": result, "measured": measured, "limit": limit, "findings": findings}


def not_run(check: str, reason: str) -> dict[str, Any]:
    return {"check": check, "result": "not_run", "reason": reason, "measured": None, "limit": None, "findings": []}


def runs(series: list[tuple[float, float]], test: Any, last_s: float) -> list[tuple[float, float]]:
    """[start, end) spans of consecutive samples whose value passes `test`.

    Each sample lasts until the next sample's time, so a series sampled every frame or every half
    second measures the same way; the last sample lasts last_s.
    """
    spans: list[tuple[float, float]] = []
    start: float | None = None
    for t, value in series:
        if test(value):
            if start is None:
                start = t
        elif start is not None:
            spans.append((start, t))
            start = None
    if start is not None and series:
        spans.append((start, round(series[-1][0] + last_s, 6)))
    return spans


def check_blank(black: list[dict[str, Any]], ymin: list[tuple[float, float]], ymax: list[tuple[float, float]],
                plan: dict[str, Any], limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """Black runs (blackdetect) and frames of one flat value of any brightness (signalstats YMAX - YMIN).

    A flat run that overlaps a black run is the same event and is reported once, as black.
    """
    lim = _limits(limits)
    frame_s = 1 / plan["fps"]
    planned = plan.get("black", [])
    findings, severities = [], []
    for item in black:
        if inside(item["start_s"], item["end_s"], planned):
            continue
        severity = "fail" if item["duration_s"] >= lim["black_min_s"] else "warn"
        findings.append({"start_s": item["start_s"], "end_s": item["end_s"], "what": "black", "severity": severity})
        severities.append(severity)
    spread = [(t, hi - lo) for (t, lo), (_, hi) in zip(ymin, ymax)]
    flat = runs(spread, lambda r: r <= lim["uniform_max_range"], frame_s)
    for start, end in flat:
        same_as_black = any(start < b["end_s"] and b["start_s"] < end for b in black)
        if same_as_black or inside(start, end, planned):
            continue
        severity = "fail" if end - start >= lim["black_min_s"] else "warn"
        findings.append({"start_s": start, "end_s": end, "what": "flat frame", "severity": severity})
        severities.append(severity)
    measured = {"black_runs": len(black), "flat_runs": len(flat), "frames_measured": len(spread),
                "smallest_luma_range": min((r for _, r in spread), default=None)}
    return row("blank_frames", findings, measured, {"black_min_s": lim["black_min_s"],
               "uniform_max_range": lim["uniform_max_range"]}, severities)


def check_frozen(freezes: list[dict[str, Any]], plan: dict[str, Any], limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """Frozen stretches (freezedetect) outside declared holds: warn from freeze_warn_s, fail from freeze_fail_s."""
    lim = _limits(limits)
    findings, severities = [], []
    for item in freezes:
        end = item["end_s"] if item["end_s"] is not None else plan["duration_s"]
        length = end - item["start_s"]
        if inside(item["start_s"], end, plan.get("holds", []), lim["hold_tail_s"]) or length < lim["freeze_warn_s"]:
            continue
        severity = "fail" if length >= lim["freeze_fail_s"] else "warn"
        findings.append({"start_s": item["start_s"], "end_s": end, "what": f"frozen {round(length, 3)} s",
                         "severity": severity})
        severities.append(severity)
    longest = max(((i["end_s"] if i["end_s"] is not None else plan["duration_s"]) - i["start_s"] for i in freezes), default=0.0)
    return row("frozen_stretches", findings, {"freezes": len(freezes), "longest_s": round(longest, 3)},
               {"warn_s": lim["freeze_warn_s"], "fail_s": lim["freeze_fail_s"], "hold_tail_s": lim["hold_tail_s"]},
               severities)


def check_cadence(scores: list[tuple[float, float]], plan: dict[str, Any],
                  limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cuts from the scene score, shot lengths, and stretches with almost no visual change.

    A dissolve or a camera move rarely scores as a cut, so shot lengths here are an upper bound. Stretches
    of near-zero change outside declared holds are warnings: narration can carry a still, a person decides.
    """
    lim = _limits(limits)
    if not scores:
        return not_run("cut_cadence", "no scene scores were measured")
    frame_s = 1 / plan["fps"]
    cuts = [t for t, s in scores if s >= lim["cut_score"]]
    edges = [0.0, *cuts, plan["duration_s"]]
    shots = [round(b - a, 3) for a, b in zip(edges, edges[1:]) if b > a]
    still = runs(scores, lambda s: s < lim["still_score"], frame_s)
    findings, severities = [], []
    for start, end in still:
        if end - start >= lim["still_warn_s"] and not inside(start, end, plan.get("holds", []), lim["hold_tail_s"]):
            findings.append({"start_s": start, "end_s": end, "what": f"almost no visual change for {round(end - start, 2)} s",
                             "severity": "warn"})
            severities.append("warn")
    ordered = sorted(shots)
    measured = {"cuts": [round(t, 3) for t in cuts], "shots": len(shots), "longest_shot_s": max(shots),
                "median_shot_s": ordered[len(ordered) // 2],
                "cuts_per_minute": round(len(cuts) / (plan["duration_s"] / 60), 2)}
    return row("cut_cadence", findings, measured, {"cut_score": lim["cut_score"], "still_score": lim["still_score"],
               "still_warn_s": lim["still_warn_s"]}, severities)


def check_loudness(summary: dict[str, Any], frames: list[dict[str, float]], plan: dict[str, Any],
                   limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """Integrated loudness and true peak (fail), loudness range and the quietest short-term window (warn)."""
    lim = _limits(limits)
    if summary.get("integrated_lufs") is None:
        return not_run("loudness", "no ebur128 summary was measured")
    findings, severities = [], []
    integrated = summary["integrated_lufs"]
    if abs(integrated - lim["target_lufs"]) > lim["tolerance_lu"] + 1e-9:
        findings.append({"what": f"integrated {integrated} LUFS, target {lim['target_lufs']} +/- {lim['tolerance_lu']}",
                         "severity": "fail"})
        severities.append("fail")
    peak = summary.get("true_peak_dbtp")
    if peak is None:
        findings.append({"what": "true peak not measured; run ebur128 with peak=true", "severity": "warn"})
        severities.append("warn")
    elif peak > lim["true_peak_max_dbtp"]:
        findings.append({"what": f"true peak {peak} dBTP above {lim['true_peak_max_dbtp']}", "severity": "fail"})
        severities.append("fail")
    lra = summary.get("lra_lu")
    if lra is not None and lra > lim["lra_max_lu"]:
        findings.append({"what": f"loudness range {lra} LU above {lim['lra_max_lu']}", "severity": "warn"})
        severities.append("warn")
    body = [f for f in frames if lim["skip_edges_s"] <= f["t_s"] <= plan["duration_s"] - lim["skip_edges_s"]]
    quietest = min(body, key=lambda f: f["short_term_lufs"]) if body else None
    if quietest and quietest["short_term_lufs"] < lim["short_term_floor_lufs"]:
        pauses = plan.get("pauses", [])
        if not inside(quietest["t_s"] - 3, quietest["t_s"], pauses):
            findings.append({"start_s": round(quietest["t_s"] - 3, 3), "end_s": quietest["t_s"],
                             "what": f"short-term loudness falls to {quietest['short_term_lufs']} LUFS",
                             "severity": "warn"})
            severities.append("warn")
    measured = {"integrated_lufs": integrated, "true_peak_dbtp": peak, "lra_lu": lra,
                "quietest_short_term_lufs": quietest["short_term_lufs"] if quietest else None,
                "quietest_at_s": quietest["t_s"] if quietest else None}
    limit = {k: lim[k] for k in ("target_lufs", "tolerance_lu", "true_peak_max_dbtp", "lra_max_lu",
                                 "short_term_floor_lufs")}
    return row("loudness", findings, measured, limit, severities)


def check_silence(silences: list[dict[str, Any]], plan: dict[str, Any], limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """Silence gaps (silencedetect) outside declared pauses: warn from silence_warn_s, fail from silence_fail_s."""
    lim = _limits(limits)
    findings, severities = [], []
    for item in silences:
        end = item["end_s"] if item["end_s"] is not None else plan["duration_s"]
        length = end - item["start_s"]
        if length < lim["silence_warn_s"] or inside(item["start_s"], end, plan.get("pauses", [])):
            continue
        severity = "fail" if length >= lim["silence_fail_s"] else "warn"
        findings.append({"start_s": item["start_s"], "end_s": end, "what": f"silence {round(length, 3)} s",
                         "severity": severity})
        severities.append(severity)
    return row("silence_gaps", findings, {"silences": len(silences)},
               {"warn_s": lim["silence_warn_s"], "fail_s": lim["silence_fail_s"]}, severities)


def check_clipping(astats: dict[str, Any], limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """Clipping from astats: a sample peak at full scale with flat tops or repeated peak samples."""
    lim = _limits(limits)
    peak = astats.get("peak_level_db")
    if peak is None:
        return not_run("clipping", "no astats overall block was measured")
    count = astats.get("peak_count") or 0
    flat = astats.get("flat_factor") or 0
    clipped = peak >= lim["clip_peak_dbfs"] and (flat > 0 or count >= lim["clip_peak_count"])
    findings = [{"what": f"peak {round(peak, 3)} dBFS, peak count {count:g}, flat factor {flat:g}",
                 "severity": "fail"}] if clipped else []
    return row("clipping", findings, {"peak_level_db": peak, "peak_count": count, "flat_factor": flat},
               {"clip_peak_dbfs": lim["clip_peak_dbfs"], "clip_peak_count": lim["clip_peak_count"]},
               ["fail"] if clipped else [])
