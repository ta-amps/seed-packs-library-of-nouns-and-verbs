"""Read WebVTT cues: their times, text and settings, and where a player would draw them."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_TIME = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})")
_ARROW = re.compile(r"^\s*(\S+)\s+-->\s+(\S+)(.*)$")


class CaptionError(ValueError):
    """A sidecar is not WebVTT or holds a malformed cue."""


def parse_time(text: str) -> float:
    match = _TIME.fullmatch(text.strip())
    if not match:
        raise CaptionError(f"bad cue time {text!r}")
    hours = int(match.group(1) or 0)
    return hours * 3600 + int(match.group(2)) * 60 + int(match.group(3)) + int(match.group(4)) / 1000


@dataclass(frozen=True)
class Cue:
    ident: str
    start_s: float
    end_s: float
    lines: tuple[str, ...]
    settings: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return " ".join(self.lines)

    def line_percent(self, default: float = 82.0) -> float:
        """The cue box's top edge as a share of frame height: WebVTT line:NN% with start alignment."""
        raw = str(self.settings.get("line", "")).split(",")[0]
        if raw.endswith("%"):
            try:
                return float(raw[:-1])
            except ValueError:
                return default
        return default


def parse_vtt(text: str) -> list[Cue]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or not lines[0].lstrip("﻿").startswith("WEBVTT"):
        raise CaptionError("not a WebVTT file: the first line must start with WEBVTT")
    cues: list[Cue] = []
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines[1:]:
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    for block in blocks:
        if block[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        timing = next((i for i, line in enumerate(block) if "-->" in line), None)
        if timing is None:
            continue
        ident = block[0].strip() if timing == 1 else str(len(cues) + 1)
        match = _ARROW.match(block[timing])
        if not match:
            raise CaptionError(f"bad timing line {block[timing]!r}")
        start, end = parse_time(match.group(1)), parse_time(match.group(2))
        if end <= start:
            raise CaptionError(f"cue {ident} ends before it starts")
        settings = dict(item.split(":", 1) for item in match.group(3).split() if ":" in item)
        text_lines = tuple(re.sub(r"<[^>]+>", "", line).strip() for line in block[timing + 1:])
        cues.append(Cue(ident, round(start, 3), round(end, 3), text_lines, settings))
    return cues


def load_vtt(path: str | Path) -> list[Cue]:
    return parse_vtt(Path(path).read_text(encoding="utf-8"))


def active_cue(cues: list[Cue], t: float) -> Cue | None:
    for cue in cues:
        if cue.start_s <= t < cue.end_s:
            return cue
    return None


def caption_box(cue: Cue, width: int, height: int, font_share: float, char_em: float, line_gap: float) -> tuple[int, int, int, int]:
    """The box a player would draw the cue in: top at line%, centred, sized from its lines.

    font_share is the caption font size as a share of frame height, char_em the average glyph advance in em,
    and line_gap the line height in em. The result is an estimate; players differ.
    """
    font = font_share * height
    longest = max((len(line) for line in cue.lines), default=0)
    box_w = min(width, int(round(longest * char_em * font + font)))
    box_h = int(round(len(cue.lines) * line_gap * font + 0.3 * font))
    top = int(round(cue.line_percent() / 100.0 * height))
    left = int(round((width - box_w) / 2))
    return left, top, left + box_w, min(height, top + box_h)
