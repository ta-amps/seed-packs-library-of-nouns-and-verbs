"""Post-encode video QA: parse ffmpeg measurements and judge them against the sequence plan.

Pure. `video_motion.video_worker` runs ffmpeg and hands the text output here; `evaluate_video()` turns
measurements into a receipt-hashed report with one result per check:

- container_and_streams: H.264 yuv420p at the aspect's exact size and the plan's frame rate, AAC
  48 kHz stereo audio.
- duration_and_frames: decoded frame count equals the plan; container duration within one frame
  (plus AAC priming).
- frame_hash_spot_checks: sampled output frames come from the scene evaluation they should: the
  render manifest's frame hash equals a fresh `evaluate_frame()`, the reference PNG digest
  matches, and the decoded frame's SSIM against that reference is high (and higher than against a
  visibly different frame of the same clip, when one exists).
- black_frames / frozen_frames: blackdetect and freezedetect, with freezes allowed only inside
  planned holds.
- integrated_loudness: EBU R128 integrated loudness near the target, true peak under the limit.
- caption_timing_coverage: readable cues, sidecar timings equal the track, and narration speech
  (measured with silencedetect on the narration stem) covered by captions.
- ai_generated_disclosure: the file metadata states what is made-up or generated.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from video_motion.nouns import value_sha256
from video_motion.schemas import ASPECT_PROFILES, AspectId
from video_motion.sequence import FrameWindow, SequencePlan, VideoSequence

VideoCheck = Literal[
    "container_and_streams",
    "duration_and_frames",
    "frame_hash_spot_checks",
    "black_frames",
    "frozen_frames",
    "integrated_loudness",
    "caption_timing_coverage",
    "ai_generated_disclosure",
]
VIDEO_CHECKS: tuple[VideoCheck, ...] = (
    "container_and_streams",
    "duration_and_frames",
    "frame_hash_spot_checks",
    "black_frames",
    "frozen_frames",
    "integrated_loudness",
    "caption_timing_coverage",
    "ai_generated_disclosure",
)
SSIM_MIN = 0.95
BLACK_MIN_S = 0.5
FREEZE_MIN_S = 2.0
LOUDNESS_TOLERANCE_LU = 1.0
CAPTION_COVERAGE_MIN = 0.95
AAC_SLACK_S = 0.05


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


class StreamInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    duration_s: float | None = None
    video_codec: str | None = None
    pix_fmt: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    color: str | None = None
    audio_codec: str | None = None
    sample_rate_hz: int | None = None
    channels: str | None = None
    title: str | None = None
    comment: str | None = None


class Loudness(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    integrated_lufs: float | None = None
    lra_lu: float | None = None
    true_peak_dbfs: float | None = None


class SpotCheck(BaseModel):
    """One sampled output frame compared with the scene frame it should show."""

    model_config = ConfigDict(extra="forbid", strict=True)

    output_frame: int
    clip_id: str
    local_frame: int
    captions: list[str]
    manifest_frame_hash: str
    evaluated_frame_hash: str
    manifest_png_sha256: str
    actual_png_sha256: str
    ssim: float | None
    neighbor_frame: int | None = None
    neighbor_ssim: float | None = None


class VideoMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    info: StreamInfo
    decoded_frames: int
    black: list[Segment]
    frozen: list[Segment]
    loudness: Loudness
    narration_duration_s: float
    narration_silences: list[Segment]
    spots: list[SpotCheck]
    srt: str
    expected_disclosure: str


class VideoCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    check: VideoCheck
    passed: bool
    measured: dict[str, Any]
    limits: dict[str, Any]
    detail: str


class VideoQAReport(BaseModel):
    """Post-encode QA of one rendered video file, with a canonical receipt digest."""

    model_config = ConfigDict(extra="forbid", strict=True)

    format: Literal["video_motion.video-qa.v1"] = "video_motion.video-qa.v1"
    sequence_id: str
    aspect: AspectId
    mp4_sha256: str
    render_manifest_sha256: str
    plan_sha256: str
    passed: bool
    checks: list[VideoCheckResult]
    receipt_sha256: str = Field(default="")


# ---------------------------------------------------------------------------------------------
# Parsers for ffmpeg 7 text output
# ---------------------------------------------------------------------------------------------

_DURATION = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO = re.compile(r"Stream #\d+:\d+.*?: Video: (\w+)[^,]*, (\w+)(\(([^)]*)\))?.*?, (\d+)x(\d+)")
_FPS = re.compile(r"(\d+(?:\.\d+)?) fps")
_AUDIO = re.compile(r"Stream #\d+:\d+.*?: Audio: (\w+)[^,]*, (\d+) Hz, ([\w.()]+)")
_TOP_METADATA = re.compile(r"^ {4}(title|comment)\s*: (.*)$", re.MULTILINE)
_BLACK = re.compile(r"black_start:(-?[\d.]+) black_end:(-?[\d.]+)")
_FREEZE_START = re.compile(r"freeze_start: (-?[\d.]+)")
_FREEZE_END = re.compile(r"freeze_end: (-?[\d.]+)")
_SILENCE_START = re.compile(r"silence_start: (-?[\d.]+)")
_SILENCE_END = re.compile(r"silence_end: (-?[\d.]+)")
_SSIM = re.compile(r"SSIM Y:[\d.]+ .*All:([\d.]+)")
_R128_I = re.compile(r"^\s+I:\s+(-?[\d.]+|-inf) LUFS", re.MULTILINE)
_R128_LRA = re.compile(r"^\s+LRA:\s+(-?[\d.]+) LU$", re.MULTILINE)
_R128_PEAK = re.compile(r"^\s+Peak:\s+(-?[\d.]+|-inf) dBFS", re.MULTILINE)


def parse_stream_info(text: str) -> StreamInfo:
    """Container, stream and top-level metadata facts from `ffmpeg -i FILE` stderr."""
    info: dict[str, Any] = {}
    if duration := _DURATION.search(text):
        hours, minutes, seconds = duration.groups()
        info["duration_s"] = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    for line in text.splitlines():
        if "Video:" in line and "video_codec" not in info and (video := _VIDEO.search(line)):
            info |= {
                "video_codec": video.group(1),
                "pix_fmt": video.group(2),
                "color": video.group(4),
                "width": int(video.group(5)),
                "height": int(video.group(6)),
            }
            if fps := _FPS.search(line):
                info["fps"] = float(fps.group(1))
        if "Audio:" in line and "audio_codec" not in info and (audio := _AUDIO.search(line)):
            info |= {
                "audio_codec": audio.group(1),
                "sample_rate_hz": int(audio.group(2)),
                "channels": audio.group(3),
            }
    for key, value in _TOP_METADATA.findall(text.split("Duration:")[0]):
        info.setdefault(key, value.strip())
    return StreamInfo.model_validate(info)


def parse_ffmetadata(text: str) -> dict[str, str]:
    """Global tags from `-f ffmetadata` output, undoing its backslash escapes."""
    tags: dict[str, str] = {}
    for line in text.split("\n[")[0].splitlines():
        if not line or line.startswith((";", "#")) or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        value, escaped = [], False
        for char in raw:
            if escaped:
                value.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            else:
                value.append(char)
        tags[key] = "".join(value)
    return tags


def parse_black_segments(text: str) -> list[Segment]:
    return [Segment(start_s=float(a), end_s=float(b)) for a, b in _BLACK.findall(text)]


def _paired(starts: list[str], ends: list[str], end_of_media: float) -> list[Segment]:
    segments = []
    for index, start in enumerate(starts):
        end = float(ends[index]) if index < len(ends) else end_of_media
        segments.append(Segment(start_s=float(start), end_s=end))
    return segments


def parse_freeze_segments(text: str, end_of_media: float) -> list[Segment]:
    """freezedetect segments; a freeze still open at the end runs to `end_of_media`."""
    return _paired(_FREEZE_START.findall(text), _FREEZE_END.findall(text), end_of_media)


def parse_silence_segments(text: str, end_of_media: float) -> list[Segment]:
    return _paired(_SILENCE_START.findall(text), _SILENCE_END.findall(text), end_of_media)


def _float(value: str) -> float | None:
    return None if value == "-inf" else float(value)


def parse_ebur128(text: str) -> Loudness:
    """Integrated loudness, loudness range and true peak from the ebur128 summary."""
    summary = text[text.rfind("Summary:") :] if "Summary:" in text else ""
    integrated = _R128_I.search(summary)
    lra = _R128_LRA.search(summary)
    peak = _R128_PEAK.search(summary)
    return Loudness(
        integrated_lufs=_float(integrated.group(1)) if integrated else None,
        lra_lu=float(lra.group(1)) if lra else None,
        true_peak_dbfs=_float(peak.group(1)) if peak else None,
    )


def parse_ssim(text: str) -> float | None:
    found = _SSIM.findall(text)
    return float(found[-1]) if found else None


def parse_loudnorm_json(text: str) -> dict[str, str]:
    """The JSON block loudnorm prints with print_format=json."""
    start, end = text.rfind("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("loudnorm printed no JSON summary")
    data = json.loads(text[start : end + 1])
    return {key: str(value) for key, value in data.items()}


def count_framemd5(text: str) -> int:
    return sum(1 for line in text.splitlines() if line and not line.startswith("#"))


_SRT_TIME = re.compile(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)")


def parse_srt_windows(text: str) -> list[tuple[float, float]]:
    def seconds(h: str, m: str, s: str, ms: str) -> float:
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    return [
        (seconds(*match.groups()[:4]), seconds(*match.groups()[4:]))
        for match in _SRT_TIME.finditer(text)
    ]


# ---------------------------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------------------------


def _overlap(a: Segment, b: Segment) -> float:
    return max(0.0, min(a.end_s, b.end_s) - max(a.start_s, b.start_s))


def speech_segments(silences: Sequence[Segment], duration_s: float) -> list[Segment]:
    """Complement of the silences within [0, duration_s]."""
    out = []
    cursor = 0.0
    for silence in sorted(silences, key=lambda s: s.start_s):
        if silence.start_s > cursor:
            out.append(Segment(start_s=cursor, end_s=min(silence.start_s, duration_s)))
        cursor = max(cursor, silence.end_s)
    if cursor < duration_s:
        out.append(Segment(start_s=cursor, end_s=duration_s))
    return [s for s in out if s.duration_s > 0.0]


def _result(
    check: VideoCheck, passed: bool, measured: dict[str, Any], limits: dict[str, Any], detail: str
) -> VideoCheckResult:
    return VideoCheckResult(
        check=check, passed=passed, measured=measured, limits=limits, detail=detail
    )


def evaluate_video(
    sequence: VideoSequence,
    plan: SequencePlan,
    aspect: AspectId,
    m: VideoMeasurements,
    *,
    mp4_sha256: str,
    render_manifest_sha256: str,
    holds: Sequence[FrameWindow],
) -> VideoQAReport:
    """Judge one encoded file's measurements against its plan; every check must pass."""
    profile = ASPECT_PROFILES[aspect]
    fps = plan.fps
    info = m.info
    results: list[VideoCheckResult] = []

    streams_ok = (
        info.video_codec == "h264"
        and info.pix_fmt == "yuv420p"
        and info.width == profile.width
        and info.height == profile.height
        and info.fps == float(fps)
        and info.audio_codec == "aac"
        and info.sample_rate_hz == 48000
        and info.channels == "stereo"
    )
    results.append(
        _result(
            "container_and_streams",
            streams_ok,
            info.model_dump(exclude={"title", "comment"}),
            {
                "video": f"h264 yuv420p {profile.width}x{profile.height} {fps} fps",
                "audio": "aac 48000 Hz stereo",
            },
            "Streams match the output contract."
            if streams_ok
            else "A stream property differs from the output contract.",
        )
    )

    duration_ok = (
        m.decoded_frames == plan.total_frames
        and info.duration_s is not None
        and abs(info.duration_s - plan.duration_s) <= 1.0 / fps + AAC_SLACK_S
    )
    results.append(
        _result(
            "duration_and_frames",
            duration_ok,
            {"decoded_frames": m.decoded_frames, "container_duration_s": info.duration_s},
            {
                "frames": plan.total_frames,
                "duration_s": plan.duration_s,
                "tolerance_s": round(1.0 / fps + AAC_SLACK_S, 6),
            },
            f"{m.decoded_frames} of {plan.total_frames} planned frames decoded.",
        )
    )

    bad_spots = []
    for spot in m.spots:
        reasons = []
        if spot.manifest_frame_hash != spot.evaluated_frame_hash:
            reasons.append("frame hash differs from a fresh scene evaluation")
        if spot.manifest_png_sha256 != spot.actual_png_sha256:
            reasons.append("reference PNG changed after rendering")
        if spot.ssim is None or spot.ssim < SSIM_MIN:
            reasons.append(f"SSIM {spot.ssim} below {SSIM_MIN}")
        if (
            spot.neighbor_ssim is not None
            and spot.ssim is not None
            and spot.neighbor_ssim >= spot.ssim
        ):
            reasons.append(
                f"a different frame ({spot.neighbor_frame}) matches as well ({spot.neighbor_ssim})"
            )
        if reasons:
            bad_spots.append({"output_frame": spot.output_frame, "reasons": reasons})
    spots_ok = bool(m.spots) and not bad_spots
    ssims = [s.ssim for s in m.spots if s.ssim is not None]
    results.append(
        _result(
            "frame_hash_spot_checks",
            spots_ok,
            {
                "spots": len(m.spots),
                "min_ssim": min(ssims) if ssims else None,
                "discriminating_spots": sum(1 for s in m.spots if s.neighbor_ssim is not None),
                "failures": bad_spots,
            },
            {"min_ssim": SSIM_MIN, "frame_hash": "equal", "png_sha256": "equal"},
            f"{len(m.spots) - len(bad_spots)} of {len(m.spots)} sampled frames match their scene evaluation.",
        )
    )

    results.append(
        _result(
            "black_frames",
            not m.black,
            {"segments": [s.model_dump() for s in m.black]},
            {"max_black_run_s": BLACK_MIN_S},
            "No black run." if not m.black else f"{len(m.black)} black run(s) detected.",
        )
    )

    tolerance = 2.0 / fps
    unexplained = [
        segment
        for segment in m.frozen
        if not any(
            segment.start_s >= hold.start_frame / fps - tolerance
            and segment.end_s <= hold.end_frame / fps + tolerance
            for hold in holds
        )
    ]
    results.append(
        _result(
            "frozen_frames",
            not unexplained,
            {
                "segments": [s.model_dump() for s in m.frozen],
                "unexplained": [s.model_dump() for s in unexplained],
            },
            {"min_freeze_s": FREEZE_MIN_S, "allowed": "inside planned holds"},
            "Every freeze is a planned hold."
            if not unexplained
            else f"{len(unexplained)} freeze(s) outside planned holds.",
        )
    )

    loud = m.loudness
    loud_ok = (
        loud.integrated_lufs is not None
        and abs(loud.integrated_lufs - sequence.loudness_target_lufs) <= LOUDNESS_TOLERANCE_LU
        and loud.true_peak_dbfs is not None
        and loud.true_peak_dbfs <= sequence.true_peak_limit_dbtp
    )
    results.append(
        _result(
            "integrated_loudness",
            loud_ok,
            loud.model_dump(),
            {
                "target_lufs": sequence.loudness_target_lufs,
                "tolerance_lu": LOUDNESS_TOLERANCE_LU,
                "true_peak_max_dbtp": sequence.true_peak_limit_dbtp,
            },
            f"Integrated {loud.integrated_lufs} LUFS, true peak {loud.true_peak_dbfs} dBTP.",
        )
    )

    captions = [
        Segment(start_s=w.start_frame / fps, end_s=w.end_frame / fps) for w in plan.captions
    ]
    sidecar = parse_srt_windows(m.srt)
    expected = [
        (cue.start_s, cue.end_s)
        for cue in sorted(sequence.captions, key=lambda c: (c.start_s, c.end_s, c.cue_id))
    ]
    sidecar_ok = len(sidecar) == len(expected) and all(
        abs(a[0] - b[0]) <= 0.001 and abs(a[1] - b[1]) <= 0.001
        for a, b in zip(sidecar, expected, strict=False)
    )
    speech = (
        speech_segments(m.narration_silences, m.narration_duration_s) if sequence.narration else []
    )
    speech_s = sum(s.duration_s for s in speech)
    covered = sum(_overlap(s, c) for s in speech for c in captions)
    coverage = (covered / speech_s) if speech_s > 0 else (1.0 if not sequence.narration else 0.0)
    unspoken = [
        index
        for index, cue in enumerate(captions)
        if speech and sum(_overlap(cue, s) for s in speech) < 0.5 * cue.duration_s
    ]
    coverage_ok = sidecar_ok and coverage >= CAPTION_COVERAGE_MIN and not unspoken
    results.append(
        _result(
            "caption_timing_coverage",
            coverage_ok,
            {
                "cues": len(captions),
                "sidecar_cues": len(sidecar),
                "speech_s": round(speech_s, 3),
                "covered_s": round(covered, 3),
                "coverage": round(coverage, 4),
                "cues_without_speech": [plan.captions[i].ref_id for i in unspoken],
            },
            {"min_coverage": CAPTION_COVERAGE_MIN, "sidecar": "equal to the caption track"},
            "No narration track; sidecar timing checked."
            if not sequence.narration
            else f"Captions cover {coverage:.1%} of measured narration speech.",
        )
    )

    comment = info.comment or ""
    disclosure_ok = comment == m.expected_disclosure and info.title == sequence.title
    results.append(
        _result(
            "ai_generated_disclosure",
            disclosure_ok,
            {"title": info.title, "comment": comment},
            {"comment": m.expected_disclosure},
            "File metadata states what is made-up or generated."
            if disclosure_ok
            else "File metadata does not carry the expected disclosure.",
        )
    )

    passed = all(r.passed for r in results)
    report = VideoQAReport(
        sequence_id=sequence.sequence_id,
        aspect=aspect,
        mp4_sha256=mp4_sha256,
        render_manifest_sha256=render_manifest_sha256,
        plan_sha256=value_sha256(plan.model_dump(mode="json")),
        passed=passed,
        checks=results,
    )
    receipt = value_sha256(report.model_dump(mode="json", exclude={"receipt_sha256"}))
    return report.model_copy(update={"receipt_sha256": receipt})
