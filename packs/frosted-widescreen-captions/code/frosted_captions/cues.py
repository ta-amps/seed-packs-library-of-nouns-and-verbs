"""Cue timing: lead and linger, bridging small gaps so the pill never blinks, and the v6 checks."""
from dataclasses import dataclass

from .geometry import FLOAT_TOL, FRAME, GRID
from .wrap import wrap_balanced

T = FRAME["caption_pill"]["timing"]
FPS = FRAME["frame"]["fps"]
LEAD = T["lead_frames"] / FPS
LINGER = T["linger_frames"] / FPS
BRIDGE = T["bridge_gap_s"]
MAX_LINGER = T["max_linger_s"]
MAX_CHARS = FRAME["caption_pill"]["lines"]["max_chars_per_line"]
MAX_LINES = FRAME["caption_pill"]["lines"]["max_lines"]
ROUND_DIGITS = GRID["span_round_digits"]
FALLBACK_TAIL_S = GRID["fallback_tail_s"]
READING_BASE_S = GRID["reading_base_s"]
READING_WORDS_PER_S = GRID["reading_words_per_s"]


@dataclass
class Cue:
    start: float   # speech onset, seconds
    end: float     # speech end, seconds
    text: str


def visible_spans(cues, film_end=None):
    """Seconds each cue is fully visible: from 2 frames before speech to 6 frames after (longer, up to
    MAX_LINGER, when its reading time needs it), and through any gap to the next cue of BRIDGE seconds or
    less (the pill stays on and the text swaps). Never into the next cue's lead."""
    spans = []
    for i, c in enumerate(cues):
        nxt = cues[i + 1].start if i + 1 < len(cues) else (film_end if film_end is not None else c.end + FALLBACK_TAIL_S)
        start = c.start - LEAD
        need = reading_need(c.text)
        linger = min(MAX_LINGER, max(LINGER, need - (c.end - c.start) - LEAD))
        if nxt - c.end <= BRIDGE:
            end = nxt - LEAD if i + 1 < len(cues) else nxt
        else:
            end = min(c.end + linger, nxt - LEAD)
        spans.append((round(start, ROUND_DIGITS), round(end, ROUND_DIGITS)))
    return spans


def reading_need(text):
    words = len(text.split())
    return READING_BASE_S + words / READING_WORDS_PER_S


def check(cues, film_end=None):
    """List of (severity, cue index, message). Severity 'error' fails a render."""
    out = []
    spans = visible_spans(cues, film_end)
    for i, (c, (a, b)) in enumerate(zip(cues, spans)):
        lines = wrap_balanced(c.text, MAX_CHARS)
        if len(lines) > MAX_LINES or any(len(x) > MAX_CHARS for x in lines):
            out.append(("error", i, f"does not fit {MAX_LINES} lines of {MAX_CHARS} characters"))
        dur = c.end - c.start
        if dur < T["min_cue_s"]:
            out.append(("error", i, f"{dur:.2f} s is shorter than {T['min_cue_s']} s"))
        if dur > T["max_cue_s"]:
            out.append(("warning", i, f"{dur:.2f} s is longer than {T['max_cue_s']} s"))
        cps = len(c.text) / dur if dur > 0 else float("inf")
        if cps > T["max_cps"]:
            out.append(("warning", i, f"{cps:.1f} characters a second (max {T['max_cps']})"))
        need = reading_need(c.text)
        if b - a + FLOAT_TOL < need:
            out.append(("error", i, f"visible {b - a:.2f} s, reading needs {need:.2f} s"))
        if i and c.start < cues[i - 1].end:
            out.append(("error", i, "overlaps the previous cue"))
    return out
