"""One frame clock for picture, voice and captions: clip spans, beat spans and narration placement.

A clip starts where the previous clip ends minus its crossfade frames. A beat runs from the middle of
the crossfade into its first clip to the middle of the crossfade into the next beat. Frames are
integers and times are whole milliseconds, rounded half up, so the arithmetic is exact.
"""

from __future__ import annotations

from typing import Any

NARRATION_GAP_MS = 200
END_GUARD_MS = 100
BEAT_START_TOLERANCE_MS = 10


def to_ms(seconds: float) -> int:
    """Whole milliseconds from a time in seconds given with at most millisecond precision."""
    return int(round(seconds * 1000))


def half_frames_to_ms(half_frames: int, fps: int) -> int:
    """Milliseconds at a point counted in half frames, rounded half up."""
    return (half_frames * 1000 + fps) // (2 * fps)


def frames_to_ms(frames: int, fps: int) -> int:
    """Milliseconds at a frame boundary, rounded half up."""
    return half_frames_to_ms(2 * frames, fps)


def ms_to_frame(ms: int, fps: int) -> int:
    """The nearest frame to a time in milliseconds, halves rounding up."""
    return (ms * fps * 2 + 1000) // 2000


def clip_spans(cut: dict[str, Any], fps: int) -> list[dict[str, Any]]:
    """Start and end frame of every clip; a clip starts at the previous end minus its crossfade."""
    out: list[dict[str, Any]] = []
    end = 0
    for i, clip in enumerate(cut["clips"]):
        overlap = clip["xfade_frames"] if i else 0
        start = end - overlap
        end = start + clip["frames"]
        out.append({"clip_id": clip["clip_id"], "beat_id": clip["beat_id"], "start_frame": start, "end_frame": end,
                    "xfade_frames": overlap})
    return out


def total_frames(cut: dict[str, Any], fps: int) -> int:
    spans = clip_spans(cut, fps)
    return spans[-1]["end_frame"] if spans else 0


def beat_spans(cut: dict[str, Any], fps: int) -> list[dict[str, Any]]:
    """Each beat in milliseconds, from mid-crossfade into its first clip to mid-crossfade into the next beat."""
    spans = clip_spans(cut, fps)
    marks: list[tuple[str, int]] = []
    for span in spans:
        if marks and marks[-1][0] == span["beat_id"]:
            continue
        start_half = 2 * span["start_frame"] + span["xfade_frames"] if marks else 0
        marks.append((span["beat_id"], start_half))
    end_half = 2 * spans[-1]["end_frame"] if spans else 0
    out = []
    for i, (beat_id, start_half) in enumerate(marks):
        stop_half = marks[i + 1][1] if i + 1 < len(marks) else end_half
        out.append({"beat_id": beat_id, "start_ms": half_frames_to_ms(start_half, fps),
                    "end_ms": half_frames_to_ms(stop_half, fps)})
    return out


def check_cut(cut: dict[str, Any], fps: int, beat_ids: set[str] | None = None) -> list[str]:
    """Problems with one cut's clips, crossfades, length and references; an empty list means none."""
    problems: list[str] = []
    clips = cut["clips"]
    if not clips:
        return [f"{cut['cut_id']}: no clips"]
    seen: set[str] = set()
    for i, clip in enumerate(clips):
        if clip["clip_id"] in seen:
            problems.append(f"{clip['clip_id']}: clip id used twice")
        seen.add(clip["clip_id"])
        if clip["frames"] < 1:
            problems.append(f"{clip['clip_id']}: a clip has at least one frame")
        if i == 0 and clip["xfade_frames"]:
            problems.append(f"{clip['clip_id']}: the first clip has no crossfade in")
        if i and clip["xfade_frames"] > min(clip["frames"], clips[i - 1]["frames"]):
            problems.append(f"{clip['clip_id']}: the crossfade is longer than a clip it joins")
        if beat_ids is not None and clip["beat_id"] not in beat_ids:
            problems.append(f"{clip['clip_id']}: beat {clip['beat_id']} is not in the cut plan's beats")
    expected = to_ms(cut["duration_s"]) * fps
    frames = total_frames(cut, fps)
    if expected % 1000 or expected // 1000 != frames:
        problems.append(f"{cut['cut_id']}: the clips lay out {frames} frames, not {cut['duration_s']} s at {fps} fps")
    runs = [span["beat_id"] for span in clip_spans(cut, fps)]
    order = [beat for i, beat in enumerate(runs) if i == 0 or runs[i - 1] != beat]
    for beat in sorted({b for b in order if order.count(b) > 1}):
        problems.append(f"beat {beat} returns after another beat; a beat is one run of clips")
    beats = {b["beat_id"] for b in beat_spans(cut, fps)}
    for item in cut.get("narration", []):
        if item["beat_id"] not in beats:
            problems.append(f"{item['line']}: beat {item['beat_id']} has no clip in this cut")
    for claim in cut.get("claims", []):
        if claim["beat_id"] not in beats:
            problems.append(f"{claim['claim_id']}: beat {claim['beat_id']} has no clip in this cut")
    return problems


def check_narration(cut: dict[str, Any], fps: int, placements: list[dict[str, Any]]) -> list[str]:
    """Problems with placed narration: gaps, lines past the end, lines outside their beat, plan mismatches."""
    problems: list[str] = []
    planned = {(item["line"], to_ms(item["start_s"]), item["beat_id"]) for item in cut["narration"]}
    placed = {(item["line"], to_ms(item["start_s"]), item["beat_id"]) for item in placements}
    for line, start, beat in sorted(planned - placed):
        problems.append(f"{line}: planned at {start} ms in beat {beat} but not placed there")
    for line, start, beat in sorted(placed - planned):
        problems.append(f"{line}: placed at {start} ms in beat {beat}, which the cut plan does not say")
    beats = {b["beat_id"]: b for b in beat_spans(cut, fps)}
    total_ms = frames_to_ms(total_frames(cut, fps), fps)
    last_end, last_line = None, None
    for item in sorted(placements, key=lambda p: (to_ms(p["start_s"]), p["line"])):
        start, end = to_ms(item["start_s"]), to_ms(item["end_s"])
        if end <= start:
            problems.append(f"{item['line']}: ends before it starts")
        if last_end is not None and start < last_end + NARRATION_GAP_MS:
            problems.append(f"{item['line']} starts at {start} ms, under {NARRATION_GAP_MS} ms after "
                            f"{last_line} ends at {last_end} ms")
        if end > total_ms - END_GUARD_MS:
            problems.append(f"{item['line']} ends at {end} ms, within {END_GUARD_MS} ms of the cut's end at {total_ms} ms")
        beat = beats.get(item["beat_id"])
        if beat is None:
            problems.append(f"{item['line']}: beat {item['beat_id']} has no clip in this cut")
        elif not beat["start_ms"] - BEAT_START_TOLERANCE_MS <= start < beat["end_ms"]:
            problems.append(f"{item['line']} starts at {start} ms, outside beat {item['beat_id']} "
                            f"({beat['start_ms']} to {beat['end_ms']} ms)")
        last_end, last_line = end, item["line"]
    return problems


def frame_sheet_times(cut: dict[str, Any], fps: int) -> list[dict[str, Any]]:
    """One time per clip for a frame sheet: the middle of the span where the clip plays alone."""
    spans = clip_spans(cut, fps)
    out = []
    for i, span in enumerate(spans):
        solo_start = span["start_frame"] + span["xfade_frames"]
        solo_end = spans[i + 1]["start_frame"] if i + 1 < len(spans) else span["end_frame"]
        out.append({"clip_id": span["clip_id"], "time_ms": half_frames_to_ms(solo_start + solo_end, fps)})
    return out
