"""Balanced caption line wrapping and deterministic SubRip (SRT) / WebVTT exporters."""

from __future__ import annotations

from collections.abc import Sequence

from video_motion.schemas import AspectId, CaptionAnchor, CaptionCue, SceneRecipe


def wrap_balanced_lines(text: str, max_chars_per_line: int = 26) -> list[str]:
    """Wrap caption text into balanced lines using minimum-raggedness dynamic programming.

    Explicit newline breaks (`\\n`) in `text` are preserved verbatim so deterministic QA
    can inspect author-forced line breaks for orphan words or overflow.
    """
    cleaned = text.strip()
    if not cleaned:
        return [""]
    if "\n" in cleaned:
        return [segment.strip() for segment in cleaned.splitlines() if segment.strip()]

    words = cleaned.split()
    if len(words) <= 1 or len(cleaned) <= max_chars_per_line:
        return [cleaned]

    n = len(words)
    inf = 10**9
    dp: list[int] = [inf] * (n + 1)
    breaks: list[int] = [n] * (n + 1)
    dp[n] = 0

    for i in range(n - 1, -1, -1):
        line_len = -1
        for j in range(i, n):
            line_len += len(words[j]) + 1
            if line_len > max_chars_per_line and j > i:
                break
            slack = max(0, max_chars_per_line - line_len)
            overflow = max(0, line_len - max_chars_per_line)
            # Penalize all lines equally (including the last line) so two-line captions split evenly.
            cost = (slack * slack) + (overflow * 500) + 40 + dp[j + 1]
            if cost < dp[i]:
                dp[i] = cost
                breaks[i] = j + 1

    lines: list[str] = []
    idx = 0
    while idx < n:
        nxt = breaks[idx]
        lines.append(" ".join(words[idx:nxt]))
        idx = nxt
    return lines


def format_srt_timestamp(seconds: float) -> str:
    """Format non-negative seconds as SubRip `HH:MM:SS,mmm`."""
    total_ms = max(0, round(seconds * 1000.0))
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, millis = divmod(rem_ms, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_webvtt_timestamp(seconds: float) -> str:
    """Format non-negative seconds as WebVTT `HH:MM:SS.mmm`."""
    total_ms = max(0, round(seconds * 1000.0))
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, millis = divmod(rem_ms, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _ordered_cues(cues: Sequence[CaptionCue]) -> list[CaptionCue]:
    return sorted(cues, key=lambda c: (c.start_s, c.end_s, c.cue_id))


_LANDSCAPE_VTT_SETTINGS: dict[str, str] = {
    "top_banner": "line:10% position:50% align:center",
    "upper_left": "line:10% position:7% align:start",
    "center_stage": "line:46% position:50% align:center",
    "reclaimed_lower_right": "line:82% position:93% align:end",
    "lower_third": "line:82% position:50% align:center",
}


def _vtt_settings_for_anchor(anchor: CaptionAnchor, aspect: AspectId) -> str:
    if aspect == "landscape_16x9":
        return _LANDSCAPE_VTT_SETTINGS[anchor]
    if anchor == "top_banner":
        return (
            "line:12% position:45% align:center"
            if aspect == "reels_9x16"
            else "line:10% position:50% align:center"
        )
    if anchor == "upper_left":
        return "line:16% position:12% align:start"
    if anchor == "center_stage":
        return "line:48% position:46% align:center"
    if anchor == "reclaimed_lower_right":
        return (
            "line:76% position:76% align:end"
            if aspect == "feed_4x5"
            else "line:72% position:44% align:center"
        )
    return (
        "line:72% position:44% align:center"
        if aspect == "reels_9x16"
        else "line:80% position:50% align:center"
    )


def export_srt(recipe: SceneRecipe) -> str:
    """Export all recipe captions to deterministic SubRip (.srt) text."""
    return srt_from_cues(recipe.captions)


def srt_from_cues(cues: Sequence[CaptionCue]) -> str:
    """Deterministic SubRip (.srt) text for any caption cue list (scene or sequence track)."""
    blocks: list[str] = []
    for index, cue in enumerate(_ordered_cues(cues), start=1):
        lines = wrap_balanced_lines(cue.text, cue.max_chars_per_line)
        prefix = ""
        if cue.role_label and cue.speaker:
            prefix = f"[{cue.role_label}] {cue.speaker}: "
        elif cue.speaker:
            prefix = f"{cue.speaker}: "
        elif cue.role_label:
            prefix = f"[{cue.role_label}] "
        rendered_lines = list(lines)
        if prefix and rendered_lines:
            rendered_lines[0] = prefix + rendered_lines[0]
        blocks.append(
            f"{index}\n"
            f"{format_srt_timestamp(cue.start_s)} --> {format_srt_timestamp(cue.end_s)}\n"
            + "\n".join(rendered_lines)
        )
    return ("\n\n".join(blocks) + "\n") if blocks else ""


def export_webvtt(recipe: SceneRecipe, aspect: AspectId = "reels_9x16") -> str:
    """Export all recipe captions to deterministic WebVTT (.vtt) text with safe-zone cue positioning."""
    return webvtt_from_cues(
        recipe.captions, aspect, note=f"recipe={recipe.recipe_id} aspect={aspect}"
    )


def webvtt_from_cues(cues: Sequence[CaptionCue], aspect: AspectId, *, note: str) -> str:
    """Deterministic WebVTT (.vtt) text for any caption cue list, positioned for `aspect`."""
    blocks: list[str] = ["WEBVTT", f"NOTE {note}"]
    for cue in _ordered_cues(cues):
        lines = wrap_balanced_lines(cue.text, cue.max_chars_per_line)
        settings = _vtt_settings_for_anchor(cue.anchor, aspect)
        body = "\n".join(lines)
        if cue.speaker:
            body = f"<v {cue.speaker}>{body}"
        blocks.append(
            f"{cue.cue_id}\n"
            f"{format_webvtt_timestamp(cue.start_s)} --> {format_webvtt_timestamp(cue.end_s)} {settings}\n"
            f"{body}"
        )
    return "\n\n".join(blocks) + "\n"
