"""Extended checks for an encoded video, beyond the eight post-encode checks of the video and motion pack.

Caption sidecars (WebVTT and SRT lint, sidecar parity, timing against measured speech), picture and sound
rows from FFmpeg analysis logs (blank and frozen frames, cut cadence, loudness, silence, clipping), an MP4
box reader for the delivery spec, and layout checks (a legibility proxy, contrast, reading time and safe
areas). Standard library only. Nothing here runs FFmpeg, decodes media, calls a model, opens a network
connection or writes inside the seed-pack library.
"""

from __future__ import annotations

from .captions import lint, parity, parse_srt, parse_webvtt, speech_sync
from .checks import check_blank, check_cadence, check_clipping, check_frozen, check_loudness, check_silence
from .layout import check_boxes, check_reading, contrast_ratio, legibility, reading_time_s
from .mp4 import check_spec, probe
from .report import compile_report, verdict

__all__ = [
    "check_blank",
    "check_boxes",
    "check_cadence",
    "check_clipping",
    "check_frozen",
    "check_loudness",
    "check_reading",
    "check_silence",
    "check_spec",
    "compile_report",
    "contrast_ratio",
    "legibility",
    "lint",
    "parity",
    "parse_srt",
    "parse_webvtt",
    "probe",
    "reading_time_s",
    "speech_sync",
    "verdict",
]
