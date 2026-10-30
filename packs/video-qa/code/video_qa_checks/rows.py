"""Check rows from already-read inputs, so the command line, the worked example and the tests build them one way."""

from __future__ import annotations

from typing import Any

from . import captions, checks, ffmpeg_logs, layout, mp4

Series = list[tuple[float, float]]


def captions_row(vtt_text: str, srt_text: str | None = None, speech_ms: list[list[int]] | None = None,
                 limits: dict[str, Any] | None = None, duration_ms: int | None = None) -> dict[str, Any]:
    """Lint problems fail, except a cue's line position, which warns; differing sidecars fail; speech coverage
    and cues without speech fail, and cues early or late against their words warn."""
    vtt = captions.parse_webvtt(vtt_text)
    problems = captions.lint(vtt, limits, duration_ms)
    findings = [{"start_s": p["start_ms"] / 1000, "what": f"{p['cue']}: {p['rule']} {p['measured']} (limit {p['limit']})",
                 "severity": "warn" if p["rule"] == "line_position" else "fail"} for p in problems]
    measured: dict[str, Any] = {"vtt": captions.stats(vtt)}
    if srt_text is not None:
        differences = captions.parity(vtt, captions.parse_srt(srt_text))
        measured["srt_differences"] = len(differences)
        findings += [{"what": f"sidecars differ: {d}", "severity": "fail"} for d in differences]
    if speech_ms is not None:
        sync = captions.speech_sync(vtt, speech_ms)
        measured["sync"] = {k: sync[k] for k in ("coverage", "cues_without_speech", "unmeasured", "median_offset_ms")}
        for problem in sync["problems"]:
            soft = "before its words" in problem or "after its words" in problem
            findings.append({"what": problem, "severity": "warn" if soft else "fail"})
    limit = {**captions.DEFAULT_LIMITS, **(limits or {}), "sync": captions.DEFAULT_SYNC}
    return checks.row("captions", findings, measured, limit, [f["severity"] for f in findings])


def picture_rows(plan: dict[str, Any], picture_log: str, ymin: Series, ymax: Series, scores: Series,
                 limits: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """blank_frames, frozen_stretches and cut_cadence from a blackdetect and freezedetect log and two series."""
    black = ffmpeg_logs.parse_blackdetect(picture_log)
    freezes = ffmpeg_logs.parse_freezedetect(picture_log)
    return [checks.check_blank(black, ymin, ymax, plan, limits), checks.check_frozen(freezes, plan, limits),
            checks.check_cadence(scores, plan, limits)]


def sound_rows(plan: dict[str, Any], ebur128_log: str, silence_log: str | None = None, astats_log: str | None = None,
               limits: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """loudness, silence_gaps and clipping; a log that was not given makes its row not_run."""
    rows = [checks.check_loudness(ffmpeg_logs.parse_ebur128_summary(ebur128_log),
                                  ffmpeg_logs.parse_ebur128_frames(ebur128_log), plan, limits)]
    if silence_log is None:
        rows.append(checks.not_run("silence_gaps", "no silencedetect log"))
    else:
        silences = ffmpeg_logs.close_open(ffmpeg_logs.parse_silencedetect(silence_log), plan["duration_s"])
        rows.append(checks.check_silence(silences, plan, limits))
    if astats_log is None:
        rows.append(checks.not_run("clipping", "no astats log"))
    else:
        rows.append(checks.check_clipping(ffmpeg_logs.parse_astats_overall(astats_log), limits))
    return rows


def filespec_row(facts: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Failed spec items fail; items the file does not record warn as not measured."""
    items = mp4.check_spec(facts, spec)
    findings = [{"what": f"{i['check']}: {i['measured']} (limit {i['limit']})", "severity": "fail"}
                for i in items if i["result"] == "fail"]
    findings += [{"what": f"{i['check']}: not measured, {i['reason']}", "severity": "warn"}
                 for i in items if i["result"] == "not_run"]
    return checks.row("file_spec", findings, {"probe": facts, "items": items}, spec, [f["severity"] for f in findings])


def legibility_row(spec: dict[str, Any]) -> dict[str, Any]:
    """Size and reading-time problems warn; a box outside the safe area warns; a box over a keep-out fails."""
    found = layout.legibility(spec["items"], spec["frame"], spec["displays"], spec.get("min_css_px", 12.0),
                              spec.get("floors"))
    findings = [{"what": p, "severity": "warn"} for p in found["problems"]]
    findings += [{"what": p, "severity": "warn"} for p in layout.check_reading(spec["items"])]
    boxes = [item for item in spec["items"] if "box" in item]
    for problem in layout.check_boxes(boxes, spec["frame"], spec.get("safe"), spec.get("keep_outs")):
        findings.append({"what": problem, "severity": "fail" if "overlaps" in problem else "warn"})
    limit = {"min_css_px": found["min_css_px"], "smallest_display": found["smallest_display"]}
    return checks.row("legibility", findings, found, limit, [f["severity"] for f in findings])
