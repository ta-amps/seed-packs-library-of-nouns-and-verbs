"""Caption sidecar checks: parse WebVTT and SRT, lint every cue, compare the two sidecars, and time cues
against measured speech.

The default limits are the video showcase style guide's: at most 2 lines of 42 characters, 1 to 7 seconds
on screen, at most 17 characters per second, no overlaps and no gap of 1 or 2 frames between cues.
Characters are counted on the cue text with its lines joined by one space, the same count the narrated
explainer video pack uses. Times are whole milliseconds, so every result is exact.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_LIMITS: dict[str, Any] = {
    "max_lines": 2,
    "max_chars_per_line": 42,
    "max_cps": 17.0,
    "min_cue_ms": 1000,
    "max_cue_ms": 7000,
    "blink_gap_frames": 3,
    "fps": 30,
    "line_percent_range": [5.0, 90.0],
}
DEFAULT_SYNC: dict[str, Any] = {
    "min_coverage": 0.95,
    "max_early_ms": 500,
    "max_late_ms": 300,
    "min_cue_speech_share": 0.10,
    "split_window_ms": 1000,
}

TIMING = re.compile(
    r"^\s*((?:\d{1,}:)?\d{2}:\d{2}[.,]\d{3})\s*-->\s*((?:\d{1,}:)?\d{2}:\d{2}[.,]\d{3})(.*)$"
)
TAG = re.compile(r"<[^>]*>")
ENTITIES = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&nbsp;": " ", "&lrm;": "", "&rlm;": ""}


def to_ms(stamp: str) -> int:
    """A WebVTT or SRT timestamp (hh:mm:ss.ttt, mm:ss.ttt or hh:mm:ss,ttt) as whole milliseconds."""
    clock, millis = re.split(r"[.,]", stamp.strip())
    parts = [int(p) for p in clock.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts
    if minutes > 59 or seconds > 59:
        raise ValueError(f"invalid timestamp {stamp!r}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + int(millis)


def plain(line: str) -> str:
    """Cue text without markup: tags such as <v Name>, <i> or <c.x> removed and entities decoded."""
    text = TAG.sub("", line)
    for entity, char in ENTITIES.items():
        text = text.replace(entity, char)
    return text.strip()


def _blocks(text: str) -> list[list[str]]:
    lines = text.replace("﻿", "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip():
            current.append(line.rstrip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _cue(block: list[str], timing_at: int, fallback_id: str) -> dict[str, Any]:
    match = TIMING.match(block[timing_at])
    if match is None:
        raise ValueError(f"cue {fallback_id}: no timing line in {block[timing_at]!r}")
    lines = [plain(line) for line in block[timing_at + 1:]]
    cue_id = block[0].strip() if timing_at == 1 else fallback_id
    return {"cue_id": cue_id, "start_ms": to_ms(match.group(1)), "end_ms": to_ms(match.group(2)),
            "settings": match.group(3).strip(), "lines": [line for line in lines if line]}


def parse_webvtt(text: str) -> list[dict[str, Any]]:
    """Cues from WebVTT text. NOTE, STYLE and REGION blocks are skipped; a missing header is an error."""
    blocks = _blocks(text)
    if not blocks or not blocks[0][0].startswith("WEBVTT"):
        raise ValueError("a WebVTT file starts with WEBVTT")
    cues = []
    for block in blocks[1:]:
        if block[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        timing_at = 0 if "-->" in block[0] else 1
        if timing_at >= len(block) or "-->" not in block[timing_at]:
            raise ValueError(f"block without a timing line: {block[0]!r}")
        cues.append(_cue(block, timing_at, f"cue{len(cues) + 1}"))
    return cues


def parse_srt(text: str) -> list[dict[str, Any]]:
    """Cues from SRT text: an index line, a timing line with commas, then the text lines."""
    cues = []
    for block in _blocks(text):
        timing_at = 0 if "-->" in block[0] else 1
        if timing_at >= len(block) or "-->" not in block[timing_at]:
            raise ValueError(f"block without a timing line: {block[0]!r}")
        cues.append(_cue(block, timing_at, f"cue{len(cues) + 1}"))
    return cues


def cue_text(cue: dict[str, Any]) -> str:
    return " ".join(cue["lines"])


def line_percent(settings: str) -> float | None:
    match = re.search(r"(?:^|\s)line:(-?\d+(?:\.\d+)?)%", settings)
    return float(match.group(1)) if match else None


def lint(cues: list[dict[str, Any]], limits: dict[str, Any] | None = None,
         duration_ms: int | None = None) -> list[dict[str, Any]]:
    """Every rule problem in a cue list, in cue order; an empty list means every rule holds."""
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    blink_ms = lim["blink_gap_frames"] * 1000 / lim["fps"]
    low, high = lim["line_percent_range"]
    problems: list[dict[str, Any]] = []

    def add(cue: dict[str, Any], rule: str, measured: Any, limit: Any) -> None:
        problems.append({"cue": cue["cue_id"], "start_ms": cue["start_ms"], "rule": rule,
                         "measured": measured, "limit": limit})

    for i, cue in enumerate(cues):
        text = cue_text(cue)
        span = cue["end_ms"] - cue["start_ms"]
        if not text:
            add(cue, "empty_cue", 0, "text")
        if len(cue["lines"]) > lim["max_lines"]:
            add(cue, "too_many_lines", len(cue["lines"]), lim["max_lines"])
        longest = max((len(line) for line in cue["lines"]), default=0)
        if longest > lim["max_chars_per_line"]:
            add(cue, "line_too_long", longest, lim["max_chars_per_line"])
        if span <= 0:
            add(cue, "ends_before_start", span, "> 0 ms")
            continue
        if span < lim["min_cue_ms"]:
            add(cue, "too_short", span, lim["min_cue_ms"])
        if span > lim["max_cue_ms"]:
            add(cue, "too_long", span, lim["max_cue_ms"])
        cps = round(len(text) * 1000 / span, 2)
        if cps > lim["max_cps"]:
            add(cue, "reading_speed", cps, lim["max_cps"])
        percent = line_percent(cue.get("settings", ""))
        if percent is not None and not low <= percent <= high:
            add(cue, "line_position", percent, [low, high])
        if duration_ms is not None and cue["end_ms"] > duration_ms:
            add(cue, "ends_after_media", cue["end_ms"], duration_ms)
        if i:
            before = cues[i - 1]
            if cue["start_ms"] < before["start_ms"]:
                add(cue, "out_of_order", cue["start_ms"], f">= {before['start_ms']}")
            elif cue["start_ms"] < before["end_ms"]:
                add(cue, "overlap", before["end_ms"] - cue["start_ms"], 0)
            elif 0 < cue["start_ms"] - before["end_ms"] < blink_ms:
                add(cue, "blink_gap", cue["start_ms"] - before["end_ms"], round(blink_ms, 1))
    return problems


def stats(cues: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts a reviewer reads first: cues, the fastest cue, the longest line and the longest gap."""
    if not cues:
        return {"cues": 0, "max_cps": None, "longest_line": 0, "longest_gap_ms": None, "on_screen_ms": 0}
    rates = [(round(len(cue_text(c)) * 1000 / (c["end_ms"] - c["start_ms"]), 2), c["cue_id"])
             for c in cues if c["end_ms"] > c["start_ms"]]
    gaps = [(b["start_ms"] - a["end_ms"], b["cue_id"]) for a, b in zip(cues, cues[1:])]
    fastest = max(rates) if rates else (None, None)
    widest = max(gaps) if gaps else (None, None)
    return {"cues": len(cues), "max_cps": fastest[0], "max_cps_cue": fastest[1],
            "longest_line": max(len(line) for c in cues for line in (c["lines"] or [""])),
            "longest_gap_ms": widest[0], "longest_gap_before": widest[1],
            "on_screen_ms": sum(max(0, c["end_ms"] - c["start_ms"]) for c in cues)}


def parity(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> list[str]:
    """Differences between two sidecars of one track, such as its WebVTT and SRT: count, times and text."""
    problems = []
    if len(first) != len(second):
        problems.append(f"cue count differs: {len(first)} and {len(second)}")
    for n, (a, b) in enumerate(zip(first, second), start=1):
        if (a["start_ms"], a["end_ms"]) != (b["start_ms"], b["end_ms"]):
            problems.append(f"cue {n}: times differ: {a['start_ms']}-{a['end_ms']} and {b['start_ms']}-{b['end_ms']}")
        if cue_text(a) != cue_text(b):
            problems.append(f"cue {n}: text differs")
    return problems


def _overlap(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


def _merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def speech_sync(cues: list[dict[str, Any]], speech_ms: list[list[int]],
                limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """How well cues follow measured speech: coverage, cues without speech, and each cue's start offset.

    speech_ms lists [start, end] intervals of speech, from a narration track or a voice activity log.
    A cue's offset is its start minus the start of the first speech interval it overlaps: negative
    means the cue appears before the words, positive means after. A cue that starts inside speech
    that began more than split_window_ms earlier follows a split inside one utterance; it has no onset
    to compare against and is listed as unmeasured, never as late.
    """
    lim = {**DEFAULT_SYNC, **(limits or {})}
    speech = _merge([(int(a), int(b)) for a, b in speech_ms if b > a])
    spans = _merge([(c["start_ms"], c["end_ms"]) for c in cues if c["end_ms"] > c["start_ms"]])
    total = sum(b - a for a, b in speech)
    covered = sum(_overlap(a, b, c, d) for a, b in speech for c, d in spans)
    coverage = round(covered / total, 4) if total else None
    without: list[str] = []
    unmeasured: list[str] = []
    early: list[dict[str, Any]] = []
    late: list[dict[str, Any]] = []
    offsets: list[int] = []
    for cue in cues:
        span = cue["end_ms"] - cue["start_ms"]
        heard = [(a, b) for a, b in speech if _overlap(a, b, cue["start_ms"], cue["end_ms"])]
        share = sum(_overlap(a, b, cue["start_ms"], cue["end_ms"]) for a, b in heard) / span if span > 0 else 0
        if share < lim["min_cue_speech_share"]:
            without.append(cue["cue_id"])
            continue
        onset = heard[0][0]
        if onset < cue["start_ms"] - lim["split_window_ms"]:
            unmeasured.append(cue["cue_id"])
            continue
        offset = cue["start_ms"] - onset
        offsets.append(offset)
        if offset < -lim["max_early_ms"]:
            early.append({"cue": cue["cue_id"], "offset_ms": offset})
        elif offset > lim["max_late_ms"]:
            late.append({"cue": cue["cue_id"], "offset_ms": offset})
    problems = []
    if coverage is not None and coverage < lim["min_coverage"]:
        problems.append(f"captions cover {coverage} of speech, under {lim['min_coverage']}")
    problems += [f"{cue}: no speech under this cue" for cue in without]
    problems += [f"{item['cue']}: appears {-item['offset_ms']} ms before its words" for item in early]
    problems += [f"{item['cue']}: appears {item['offset_ms']} ms after its words begin" for item in late]
    return {"speech_ms": total, "covered_ms": covered, "coverage": coverage, "cues_without_speech": without,
            "unmeasured": unmeasured, "early": early, "late": late,
            "median_offset_ms": sorted(offsets)[len(offsets) // 2] if offsets else None, "problems": problems}
