"""Deterministic checks for a narrated explainer video: its frame clock, captions and release manifest.

Standard library only. Nothing here renders, encodes, calls a model, opens a network connection or
writes inside the seed-pack library. Times are kept as whole milliseconds and frames, so every
result is exact and any language can reproduce it.
"""

from __future__ import annotations

from .captions import build_cues, check_cues, to_srt, to_webvtt, wrap
from .clock import beat_spans, check_cut, check_narration, clip_spans, frame_sheet_times, total_frames
from .release import check_ledger, file_entry, verify_manifest

__all__ = [
    "beat_spans",
    "build_cues",
    "check_cues",
    "check_cut",
    "check_ledger",
    "check_narration",
    "clip_spans",
    "frame_sheet_times",
    "file_entry",
    "to_srt",
    "to_webvtt",
    "total_frames",
    "verify_manifest",
    "wrap",
]
