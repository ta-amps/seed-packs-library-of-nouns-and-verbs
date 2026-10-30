"""Parsers for the text FFmpeg writes when its analysis filters run, so checks read numbers, not prose.

Each parser takes the log text of one run (stderr, or a file written by the metadata filter) and returns
plain values. The formats are those of FFmpeg 7: blackdetect, freezedetect and silencedetect intervals,
the ebur128 summary and its per-frame log (written only at the verbose log level), the astats overall
block, and metadata=mode=print files of per-frame values such as lavfi.scene_score or
lavfi.signalstats.YMIN. Nothing here runs FFmpeg.
"""

from __future__ import annotations

import re
from typing import Any

NUMBER = r"(-?(?:\d+(?:\.\d*)?|\.\d+)|-?inf|nan)"


def _num(text: str) -> float:
    return float(text)


def parse_blackdetect(text: str) -> list[dict[str, float]]:
    """black_start / black_end / black_duration lines, as intervals in seconds."""
    out = []
    pattern = re.compile(rf"black_start:{NUMBER}\s+black_end:{NUMBER}\s+black_duration:{NUMBER}")
    for start, end, duration in pattern.findall(text):
        out.append({"start_s": _num(start), "end_s": _num(end), "duration_s": _num(duration)})
    return out


def _paired(text: str, kind: str, end_key: str) -> list[dict[str, Any]]:
    """Intervals from separate start and end lines; a start with no end runs to the end of the media."""
    events = re.findall(rf"{kind}_(start|{end_key}):\s*{NUMBER}", text)
    out: list[dict[str, Any]] = []
    for name, value in events:
        if name == "start":
            out.append({"start_s": _num(value), "end_s": None, "duration_s": None})
        elif out and out[-1]["end_s"] is None:
            out[-1]["end_s"] = _num(value)
            out[-1]["duration_s"] = round(out[-1]["end_s"] - out[-1]["start_s"], 6)
    return out


def parse_freezedetect(text: str) -> list[dict[str, Any]]:
    """lavfi.freezedetect.freeze_start / freeze_end lines, as intervals in seconds."""
    return _paired(text, "freeze", "end")


def parse_silencedetect(text: str) -> list[dict[str, Any]]:
    """silence_start / silence_end lines, as intervals in seconds."""
    return _paired(text, "silence", "end")


def close_open(intervals: list[dict[str, Any]], duration_s: float) -> list[dict[str, Any]]:
    """Give an interval still open at the end of the log the media's duration as its end."""
    out = []
    for item in intervals:
        if item["end_s"] is None:
            item = {**item, "end_s": duration_s, "duration_s": round(duration_s - item["start_s"], 6)}
        out.append(item)
    return out


def parse_ebur128_summary(text: str) -> dict[str, float | None]:
    """Integrated loudness, loudness range and true peak from the ebur128 summary block."""
    summary = text[text.rfind("Summary:"):] if "Summary:" in text else ""

    def grab(label: str) -> float | None:
        match = re.search(rf"{label}:\s*{NUMBER}", summary)
        return None if match is None else _num(match.group(1))

    return {"integrated_lufs": grab(r"\bI"), "lra_lu": grab("LRA"), "true_peak_dbtp": grab("Peak")}


def parse_ebur128_frames(text: str) -> list[dict[str, float]]:
    """Per-frame lines (t, momentary M and short-term S) from ebur128 with framelog=verbose."""
    pattern = re.compile(rf"\bt:\s*{NUMBER}\s+TARGET:.*?\bM:\s*{NUMBER}\s+S:\s*{NUMBER}")
    return [{"t_s": _num(t), "momentary_lufs": _num(m), "short_term_lufs": _num(s)}
            for t, m, s in pattern.findall(text)]


def parse_astats_overall(text: str) -> dict[str, float | None]:
    """Peak level, RMS level, flat factor, peak count and sample count from astats' Overall block."""
    block = text[text.rfind("Overall"):] if "Overall" in text else ""
    names = {"peak_level_db": "Peak level dB", "rms_level_db": "RMS level dB", "flat_factor": "Flat factor",
             "peak_count": "Peak count", "samples": "Number of samples"}
    out: dict[str, float | None] = {}
    for key, label in names.items():
        match = re.search(rf"{re.escape(label)}:\s*{NUMBER}", block)
        out[key] = None if match is None else _num(match.group(1))
    return out


def parse_metadata_print(text: str, key: str) -> list[tuple[float, float]]:
    """(pts_time, value) pairs for one key from a metadata=mode=print file or log."""
    out = []
    current: float | None = None
    for line in text.splitlines():
        frame = re.search(rf"pts_time:{NUMBER}", line)
        if frame:
            current = _num(frame.group(1))
            continue
        match = re.search(rf"{re.escape(key)}={NUMBER}", line)
        if match and current is not None:
            out.append((current, _num(match.group(1))))
    return out
