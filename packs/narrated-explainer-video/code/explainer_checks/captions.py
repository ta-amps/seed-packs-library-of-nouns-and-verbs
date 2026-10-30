"""Captions from the script, timed to the measured voice, written as WebVTT and SRT.

Cue text comes from the placed narration lines, never from speech recognition. Each line is split at
sentence ends, and a sentence too long for one cue is split at the comma nearest its middle. Splits
snap to the pauses measured in the line, and every cue is then lengthened to read at 16.4 characters
per second, kept clear of the next cue, capped at 7 seconds and snapped to frames. Rules: at most 2
lines of 42 characters, 1 to 7 seconds on screen, at most 17 characters per second, no overlaps and
no 1 or 2 frame gaps between cues.
"""

from __future__ import annotations

import re
from typing import Any

from .clock import frames_to_ms, ms_to_frame, to_ms

MAX_LINE = 42
MAX_LINES = 2
MAX_CPS = 17
MIN_CUE_MS = 1000
MAX_CUE_MS = 7000
READ_TENTHS_CPS = 164
TAIL_MS = 250
PAUSE_SNAP_MS = 1200
END_GUARD_MS = 50
BLINK_GAP_FRAMES = 3
SENTENCE_END = re.compile(r"(?<=[.!?…:])\s+(?=[A-Z…])")


def wrap(text: str, width: int = MAX_LINE) -> list[str]:
    """One line, or two lines as even as the words allow; ValueError when two lines cannot hold it."""
    if len(text) <= width:
        return [text]
    words = text.split()
    best: tuple[int, list[str]] | None = None
    for i in range(1, len(words)):
        first, second = " ".join(words[:i]), " ".join(words[i:])
        if len(first) > width or len(second) > width:
            continue
        cost = abs(len(first) - len(second))
        if best is None or cost < best[0]:
            best = (cost, [first, second])
    if best is None:
        raise ValueError(f"cannot fit {text!r} in {MAX_LINES} lines of {width} characters")
    return best[1]


def split_long(sentence: str) -> list[str]:
    """A sentence as one cue text, or split at the comma nearest its middle until every part fits."""
    if len(sentence) <= MAX_LINE * MAX_LINES - 4:
        try:
            wrap(sentence)
            return [sentence]
        except ValueError:
            pass
    commas = [m.end() for m in re.finditer(r",\s", sentence)]
    if not commas:
        words = sentence.split()
        if len(words) < 2:
            raise ValueError(f"cannot split {sentence!r} into cues")
        mid = len(words) // 2
        return [*split_long(" ".join(words[:mid])), *split_long(" ".join(words[mid:]))]
    cut = min(commas, key=lambda c: (abs(2 * c - len(sentence)), c))
    return [*split_long(sentence[:cut].strip()), *split_long(sentence[cut:].strip())]


def pieces(text: str, speech_ms: list[int], pauses_ms: list[list[int]]) -> list[dict[str, Any]]:
    """Cue texts for one placed line with their times; splits snap to the nearest unused measured pause."""
    parts: list[str] = []
    for sentence in SENTENCE_END.split(text.strip()):
        parts += split_long(" ".join(sentence.split()))
    start, stop = speech_ms
    total = sum(len(part) for part in parts)
    bounds = [(start, start)]
    used: set[int] = set()
    acc = 0
    for part in parts[:-1]:
        acc += len(part)
        estimate = start + (stop - start) * acc // total
        best = None
        for i, (a, b) in enumerate(pauses_ms):
            if i in used:
                continue
            if best is None or abs(a + b - 2 * estimate) < abs(sum(pauses_ms[best]) - 2 * estimate):
                best = i
        if best is not None and abs(sum(pauses_ms[best]) - 2 * estimate) < 2 * PAUSE_SNAP_MS:
            used.add(best)
            bounds.append((pauses_ms[best][0], pauses_ms[best][1]))
        else:
            bounds.append((estimate, estimate))
    bounds.append((stop, stop))
    return [{"text": part, "start_ms": bounds[i][1], "end_ms": bounds[i + 1][0]} for i, part in enumerate(parts)]


def build_cues(placements: list[dict[str, Any]], duration_s: float, fps: int) -> list[dict[str, Any]]:
    """Cues for one cut from its placed lines: text, speech span and pauses, all in seconds on the cut."""
    raw: list[dict[str, Any]] = []
    for item in placements:
        speech = [to_ms(t) for t in item["speech_s"]]
        pauses = [[to_ms(a), to_ms(b)] for a, b in item["pauses_s"]]
        for piece in pieces(item["text"], speech, pauses):
            raw.append({**piece, "line": item["line"], "beat_id": item["beat_id"]})
    raw.sort(key=lambda c: (c["start_ms"], c["line"]))
    duration_ms = to_ms(duration_s)
    cues: list[dict[str, Any]] = []
    for i, cue in enumerate(raw):
        following = raw[i + 1]["start_ms"] if i + 1 < len(raw) else duration_ms - END_GUARD_MS
        need = max(MIN_CUE_MS, -(-len(cue["text"]) * 10000 // READ_TENTHS_CPS))
        end = max(cue["end_ms"] + TAIL_MS, cue["start_ms"] + need)
        end = min(end, following, cue["start_ms"] + MAX_CUE_MS)
        cues.append({"start_frame": ms_to_frame(cue["start_ms"], fps), "end_frame": ms_to_frame(end, fps),
                     "text": cue["text"], "line": cue["line"], "beat_id": cue["beat_id"]})
    for i in range(len(cues) - 1):
        gap = cues[i + 1]["start_frame"] - cues[i]["end_frame"]
        if 0 < gap < BLINK_GAP_FRAMES:
            cues[i]["end_frame"] = cues[i + 1]["start_frame"]
    out = []
    for i, cue in enumerate(cues):
        out.append({"cue_id": f"c{i + 1:02d}", "start_frame": cue["start_frame"], "end_frame": cue["end_frame"],
                    "start_s": round(cue["start_frame"] / fps, 3), "end_s": round(cue["end_frame"] / fps, 3),
                    "text": cue["text"], "lines": wrap(cue["text"]), "line": cue["line"], "beat_id": cue["beat_id"]})
    return out


def check_cues(cues: list[dict[str, Any]], fps: int) -> list[str]:
    """Rule problems in a cue list; an empty list means every rule holds."""
    problems: list[str] = []
    for i, cue in enumerate(cues):
        try:
            lines = wrap(cue["text"])
        except ValueError:
            problems.append(f"{cue['cue_id']}: does not fit {MAX_LINES} lines of {MAX_LINE} characters")
            lines = cue.get("lines", [])
        if cue.get("lines", lines) != lines:
            problems.append(f"{cue['cue_id']}: its lines are not the balanced wrap of its text")
        frames = cue["end_frame"] - cue["start_frame"]
        if frames <= 0:
            problems.append(f"{cue['cue_id']}: ends before it starts")
            continue
        if not MIN_CUE_MS * fps <= frames * 1000 <= MAX_CUE_MS * fps:
            problems.append(f"{cue['cue_id']}: {frames_to_ms(frames, fps)} ms on screen, outside "
                            f"{MIN_CUE_MS} to {MAX_CUE_MS} ms")
        if len(cue["text"]) * fps > MAX_CPS * frames:
            problems.append(f"{cue['cue_id']}: reads faster than {MAX_CPS} characters per second")
        if i and cue["start_frame"] < cues[i - 1]["end_frame"]:
            problems.append(f"{cue['cue_id']}: overlaps the cue before it")
        if i and 0 < cue["start_frame"] - cues[i - 1]["end_frame"] < BLINK_GAP_FRAMES:
            problems.append(f"{cue['cue_id']}: a gap of under {BLINK_GAP_FRAMES} frames after the cue before it")
    return problems


def stamp(frame: int, fps: int, separator: str) -> str:
    ms = frames_to_ms(frame, fps)
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def to_webvtt(cues: list[dict[str, Any]], fps: int) -> str:
    """A WebVTT file: the header, then each cue's timing line and wrapped lines, separated by blank lines."""
    out = ["WEBVTT", ""]
    for cue in cues:
        out.append(f"{stamp(cue['start_frame'], fps, '.')} --> {stamp(cue['end_frame'], fps, '.')}")
        out += cue["lines"]
        out.append("")
    return "\n".join(out)


def to_srt(cues: list[dict[str, Any]], fps: int) -> str:
    """An SRT file with the same cues and timings as the WebVTT file."""
    out: list[str] = []
    for number, cue in enumerate(cues, 1):
        out.append(str(number))
        out.append(f"{stamp(cue['start_frame'], fps, ',')} --> {stamp(cue['end_frame'], fps, ',')}")
        out += cue["lines"]
        out.append("")
    return "\n".join(out)
