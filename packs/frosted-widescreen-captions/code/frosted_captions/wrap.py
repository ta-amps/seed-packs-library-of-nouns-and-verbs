"""Clause-aware, balanced caption line breaking (film-frame v6).

The same scoring is mirrored in JavaScript on the canvas boards FilmFrameV6 and FilmCaptionsV6.
"""
import re

from .geometry import DOUBLE_MULT, FRAME, GRID

MAX_CHARS = FRAME["caption_pill"]["lines"]["max_chars_per_line"]
MAX_LINES = FRAME["caption_pill"]["lines"]["max_lines"]
WRAP_SCORES = GRID["wrap_scores"]
SPLIT_SCORES = GRID["split_scores"]
BAD_END = frozenset("a an the of to and or but in on at for with by from as into your their its our is are".split())
PROTECTED = (("Muse", "Glimmer"), ("Muse", "Spark"), ("Muse", "Code"), ("Llama", "3.2"))
CONJ = re.compile(r"(and|but|so|or|because|which|that|while|then)", re.I)


def _score(l1, l2, prev, nxt):
    score = abs(len(l1) - len(l2))
    if re.search(r"[.;:!?]$", prev):
        score -= WRAP_SCORES["sentence_end"]
    elif prev.endswith(","):
        score -= WRAP_SCORES["comma"]
    elif CONJ.fullmatch(nxt):
        score -= WRAP_SCORES["conjunction"]
    if re.sub(r"[^a-z]", "", prev.lower()) in BAD_END:
        score += WRAP_SCORES["bad_end"]
    if any(prev == a and nxt.startswith(b) for a, b in PROTECTED):
        score += WRAP_SCORES["protected"]
    if min(len(l1), len(l2)) / max(len(l1), len(l2)) < WRAP_SCORES["orphan_ratio"]:
        score += WRAP_SCORES["orphan_penalty"]
    return score


def wrap_balanced(text, max_chars=MAX_CHARS):
    """Return one or two lines. One line when it fits; otherwise the lowest-scoring break where both
    lines fit. If no break fits, the text comes back as one over-long line for the checker to flag."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return [text]
    words = text.split(" ")
    best = None
    for i in range(1, len(words)):
        l1, l2 = " ".join(words[:i]), " ".join(words[i:])
        if len(l1) > max_chars or len(l2) > max_chars:
            continue
        s = _score(l1, l2, words[i - 1], words[i])
        if best is None or s < best[0]:
            best = (s, [l1, l2])
    return best[1] if best else [text]


def _fits(text, max_chars):
    lines = wrap_balanced(text, max_chars)
    return len(lines) <= MAX_LINES and all(len(x) <= max_chars for x in lines)


def split_cues(text, max_len=DOUBLE_MULT * MAX_CHARS, max_chars=MAX_CHARS):
    """Cut one narration line into caption cues that each fit two lines, at the strongest clause boundary."""
    text = " ".join(text.split())
    if len(text) <= max_len and _fits(text, max_chars):
        return [text]
    words = text.split(" ")
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        prev, nxt = words[i - 1], words[i]
        s = abs(len(a) - len(b))
        if re.search(r"[.;:!?…]$", prev):
            s -= SPLIT_SCORES["sentence_end"]
        elif prev.endswith(","):
            s -= SPLIT_SCORES["comma"]
        elif CONJ.fullmatch(nxt):
            s -= SPLIT_SCORES["conjunction"]
        if re.sub(r"[^a-z]", "", prev.lower()) in BAD_END:
            s += SPLIT_SCORES["bad_end"]
        if any(prev == x and nxt.startswith(y) for x, y in PROTECTED):
            s += SPLIT_SCORES["protected"]
        if best is None or s < best[0]:
            best = (s, a, b)
    if best is None:
        return [text]
    return split_cues(best[1], max_len, max_chars) + split_cues(best[1 + 1], max_len, max_chars)
