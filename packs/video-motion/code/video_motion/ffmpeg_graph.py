"""Deterministic ffmpeg command lines for sequence rendering and post-encode measurement.

Pure: these functions only build argument lists. Paths are relative to the worker's render
directory, so recorded commands carry no local paths. All frames pass through one explicit
BT.709 conversion; overlays and transitions are composited in 4:4:4 and encoded once to H.264
4:2:0 with AAC audio. `video_motion.video_worker` runs the commands.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from video_motion.media import MediaElement, MediaPlacement
from video_motion.schemas import ASPECT_PROFILES, AspectId, Box2D
from video_motion.sequence import MediaClip, SceneClip, SequencePlan, VideoSequence

BASE = ["-hide_banner", "-nostdin", "-y"]
TO_YUV444 = "scale=out_color_matrix=bt709:out_range=tv,format=yuv444p"
TO_YUVA444 = "format=rgba,scale=out_color_matrix=bt709:out_range=tv,format=yuva444p"
SAMPLE_RATE = 48000
LOUDNORM_LRA = 20.0


class ComposeInputs(BaseModel):
    """Render-directory-relative files the compose step reads."""

    model_config = ConfigDict(extra="forbid", strict=True)

    scene_frames: dict[str, str]
    media_files: dict[str, str]
    caption_images: dict[str, str]
    master_audio: str


def _seconds(frames: int, fps: int) -> str:
    return f"{frames / fps:.6f}"


def _num(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))


def _crop(placement: MediaPlacement | None) -> str:
    if placement is None or placement.crop is None:
        return ""
    c = placement.crop
    return f"crop={_num(c.width)}:{_num(c.height)}:{_num(c.x)}:{_num(c.y)},"


def _fit(box: Box2D, pad_color: str) -> str:
    """Scale to fit inside `box` keeping aspect, then pad (centered) to exactly the box size."""
    w, h = round(box.width), round(box.height)
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=bicubic,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={pad_color}"
    )


def _media_input(element: MediaElement, path: str, fps: int) -> list[str]:
    if element.kind == "image":
        return ["-i", path]
    return ["-ss", _num(element.trim_in_s), "-t", _num(element.span_s), "-i", path]


def _clip_frames_filter(index: int, frames: int, fps: int, element: MediaElement, kind: str) -> str:
    """Normalize a media input to exactly `frames` constant-rate frames."""
    if kind == "image":
        return f"[{index}:v]loop=loop={frames - 1}:size=1:start=0,"
    return f"[{index}:v]fps={fps},trim=end_frame={frames},"


def compose_command(
    sequence: VideoSequence,
    plan: SequencePlan,
    aspect: AspectId,
    inputs: ComposeInputs,
    output: str,
    *,
    title: str,
    comment: str,
    crf: int = 18,
) -> list[str]:
    """One ffmpeg invocation that composites every clip, overlay and caption and encodes MP4."""
    profile = ASPECT_PROFILES[aspect]
    width, height, fps = profile.width, profile.height, plan.fps
    args = [*BASE, "-loglevel", "warning"]
    graph: list[str] = []
    next_input = 0

    def add_input(extra: list[str]) -> int:
        nonlocal next_input
        args.extend(extra)
        next_input += 1
        return next_input - 1

    clips = {clip.clip_id: clip for clip in sequence.clips}
    for position, clip_plan in enumerate(plan.clips):
        clip = clips[clip_plan.clip_id]
        label = f"c{position}"
        if isinstance(clip, SceneClip):
            index = add_input(
                [
                    "-framerate",
                    str(fps),
                    "-start_number",
                    "0",
                    "-i",
                    inputs.scene_frames[clip.clip_id],
                ]
            )
            graph.append(
                f"[{index}:v]{TO_YUV444},setsar=1,settb=AVTB,setpts=N/({fps}*TB),fps={fps}[{label}base]"
            )
            current = f"{label}base"
            for number, overlay in enumerate(clip.overlays):
                ov_window = next(w for w in plan.overlays if w.element_id == overlay.element_id)
                ov_placement = overlay.placements[aspect]
                start = ov_window.start_frame - clip_plan.start_frame
                end = ov_window.end_frame - clip_plan.start_frame
                ov_index = add_input(
                    _media_input(overlay, inputs.media_files[overlay.element_id], fps)
                )
                fade = (
                    f",colorchannelmixer=aa={_num(ov_placement.opacity)}"
                    if ov_placement.opacity < 1.0
                    else ""
                )
                timing = (
                    f"fps={fps},setpts=N/({fps}*TB)+{start}/({fps}*TB),"
                    if overlay.kind == "recording"
                    else ""
                )
                graph.append(
                    f"[{ov_index}:v]{timing}{_crop(ov_placement)}format=rgba,"
                    f"{_fit(ov_placement.box, 'black@0')}{fade},{TO_YUVA444},setsar=1"
                    f"[{label}ov{number}]"
                )
                graph.append(
                    f"[{current}][{label}ov{number}]overlay="
                    f"x={round(ov_placement.box.x)}:y={round(ov_placement.box.y)}"
                    f":enable='between(n,{start},{end - 1})':format=yuv444"
                    f"[{label}o{number}]"
                )
                current = f"{label}o{number}"
            graph.append(f"[{current}]null[{label}]")
        else:
            assert isinstance(clip, MediaClip)
            element = clip.element
            placement = element.placements.get(aspect)
            box = placement.box if placement else Box2D(x=0.0, y=0.0, width=width, height=height)
            index = add_input(_media_input(element, inputs.media_files[element.element_id], fps))
            graph.append(
                _clip_frames_filter(index, clip_plan.frame_count, fps, element, element.kind)
                + f"{_crop(placement)}{_fit(box, clip.background_hex)},"
                f"pad={width}:{height}:{round(box.x)}:{round(box.y)}:color={clip.background_hex},"
                f"{TO_YUV444},setsar=1,settb=AVTB,setpts=N/({fps}*TB),fps={fps}[{label}]"
            )
    current = "c0"
    for position, clip_plan in enumerate(plan.clips[1:], start=1):
        if clip_plan.transition_in == "crossfade":
            graph.append(
                f"[{current}][c{position}]xfade=transition=fade"
                f":duration={_seconds(clip_plan.transition_frames, fps)}"
                f":offset={_seconds(clip_plan.start_frame, fps)}[x{position}]"
            )
        else:
            graph.append(f"[{current}][c{position}]concat=n=2:v=1:a=0[x{position}]")
        current = f"x{position}"
    for number, cap_window in enumerate(plan.captions):
        index = add_input(["-i", inputs.caption_images[cap_window.ref_id]])
        graph.append(f"[{index}:v]{TO_YUVA444}[cap{number}]")
        graph.append(
            f"[{current}][cap{number}]overlay=x=0:y=0"
            f":enable='between(n,{cap_window.start_frame},{cap_window.end_frame - 1})':format=yuv444"
            f"[k{number}]"
        )
        current = f"k{number}"
    graph.append(f"[{current}]format=yuv420p[vout]")
    audio_index = add_input(["-i", inputs.master_audio])
    args += [
        "-filter_complex",
        ";".join(graph),
        "-map",
        "[vout]",
        "-map",
        f"{audio_index}:a",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(crf),
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-g",
        str(2 * fps),
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-color_range",
        "tv",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        str(SAMPLE_RATE),
        "-ac",
        "2",
        "-frames:v",
        str(plan.total_frames),
        "-movflags",
        "+faststart",
        "-map_metadata",
        "-1",
        "-fflags",
        "+bitexact",
        "-flags:v",
        "+bitexact",
        "-flags:a",
        "+bitexact",
        "-metadata",
        f"title={title}",
        "-metadata",
        f"comment={comment}",
        output,
    ]
    return args


def mix_command(
    sequence: VideoSequence,
    plan: SequencePlan,
    media_files: dict[str, str],
    mix_output: str,
    narration_output: str,
) -> list[str]:
    """Place narration, duck the music bed under it, and write the mix and the narration stem."""
    args = [*BASE, "-loglevel", "error"]
    graph: list[str] = []
    total = _seconds(plan.total_frames, plan.fps)
    stereo = f"aresample={SAMPLE_RATE},aformat=sample_fmts=fltp:channel_layouts=stereo"

    def place(index: int, element: MediaElement, label: str) -> str:
        delay_ms = round(element.start_s * 1000)
        return (
            f"[{index}:a]atrim=start={_num(element.trim_in_s)}:duration={_num(element.span_s)},"
            f"asetpts=PTS-STARTPTS,{stereo},volume={_num(element.gain_db)}dB,"
            f"adelay={delay_ms}:all=1[{label}]"
        )

    labels: list[str] = []
    for number, element in enumerate(sequence.narration):
        args += ["-i", media_files[element.element_id]]
        graph.append(place(len(labels), element, f"n{number}"))
        labels.append(f"[n{number}]")
    inputs = len(labels)
    if not labels:
        # ffmpeg 7.0 needs at least one input file, so silence comes from a lavfi input.
        args += [
            "-f",
            "lavfi",
            "-t",
            total,
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE}",
        ]
        graph.append("[0:a]anull[narr]")
        inputs = 1
    elif len(labels) == 1:
        graph.append(f"{labels[0]}anull[narr]")
    else:
        graph.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest[narr]"
        )
    graph.append(f"[narr]apad=whole_dur={total},atrim=end={total},asplit=3[nmix][nkey][nstem]")
    if sequence.music_bed is not None:
        args += ["-i", media_files[sequence.music_bed.element_id]]
        graph.append(place(inputs, sequence.music_bed, "mus"))
        ratio = 1.0 + sequence.music_duck_db / 3.0
        graph.append(
            f"[mus][nkey]sidechaincompress=threshold=0.02:ratio={_num(ratio)}"
            ":attack=15:release=350[duck]"
        )
        graph.append("[nmix][duck]amix=inputs=2:normalize=0:duration=longest[mixed]")
    else:
        graph.append("[nkey]anullsink")
        graph.append("[nmix]anull[mixed]")
    graph.append(f"[mixed]apad=whole_dur={total},atrim=end={total}[aout]")
    return [
        *args,
        "-filter_complex",
        ";".join(graph),
        "-map",
        "[aout]",
        "-c:a",
        "pcm_f32le",
        "-ar",
        str(SAMPLE_RATE),
        mix_output,
        "-map",
        "[nstem]",
        "-c:a",
        "pcm_s16le",
        "-ar",
        str(SAMPLE_RATE),
        narration_output,
    ]


def _loudnorm(target_lufs: float, true_peak_dbtp: float) -> str:
    return f"loudnorm=I={_num(target_lufs)}:TP={_num(true_peak_dbtp)}:LRA={_num(LOUDNORM_LRA)}"


def loudness_measure_command(mix: str, target_lufs: float, true_peak_dbtp: float) -> list[str]:
    """First loudnorm pass: measure the mix and print the JSON summary."""
    return [
        *BASE,
        "-nostats",
        "-i",
        mix,
        "-af",
        f"{_loudnorm(target_lufs, true_peak_dbtp)}:print_format=json",
        "-f",
        "null",
        "-",
    ]


def loudness_apply_command(
    mix: str,
    output: str,
    measured: dict[str, str],
    target_lufs: float,
    true_peak_dbtp: float,
) -> list[str]:
    """Second loudnorm pass: one linear gain from the measurement (dynamic only if peaks force it)."""
    measured_args = (
        f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true:print_format=json"
    )
    return [
        *BASE,
        "-nostats",
        "-i",
        mix,
        "-af",
        f"{_loudnorm(target_lufs, true_peak_dbtp)}{measured_args},aresample={SAMPLE_RATE}",
        "-c:a",
        "pcm_s16le",
        "-ar",
        str(SAMPLE_RATE),
        output,
    ]


def probe_command(path: str) -> list[str]:
    """`ffmpeg -i` header dump (ffmpeg exits 1 because no output is named)."""
    return ["-hide_banner", "-nostdin", "-i", path]


def metadata_command(path: str) -> list[str]:
    """Container metadata in ffmetadata form (full values; `-i` output truncates long tags)."""
    return ["-hide_banner", "-nostdin", "-loglevel", "error", "-i", path, "-f", "ffmetadata", "-"]


def framemd5_command(path: str) -> list[str]:
    return [
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-i",
        path,
        "-map",
        "0:v:0",
        "-f",
        "framemd5",
        "-",
    ]


def detect_command(path: str, *, black_min_s: float, freeze_min_s: float) -> list[str]:
    """One decode pass with blackdetect, freezedetect and EBU R128 loudness."""
    return [
        *BASE,
        "-nostats",
        "-i",
        path,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-vf",
        f"blackdetect=d={_num(black_min_s)}:pix_th=0.10,freezedetect=n=0.0005:d={_num(freeze_min_s)}",
        "-af",
        "ebur128=peak=true:framelog=quiet",
        "-f",
        "null",
        "-",
    ]


def silence_command(path: str, *, threshold_db: float = -45.0, min_s: float = 0.25) -> list[str]:
    return [
        *BASE,
        "-nostats",
        "-i",
        path,
        "-af",
        f"silencedetect=n={_num(threshold_db)}dB:d={_num(min_s)}",
        "-f",
        "null",
        "-",
    ]


def spot_frame_command(
    path: str,
    frame: int,
    fps: int,
    reference: str,
    overlays: Sequence[str],
    decoded_output: str,
) -> list[str]:
    """Decode output frame `frame` exactly and report its SSIM against the reference composite.

    The reference is the rendered scene PNG with any active caption overlays applied, converted
    with the same BT.709 matrix as the encode. Seeking lands one second early, then `select`
    picks the exact frame.
    """
    seek_frame = max(0, frame - fps)
    seek = ["-ss", f"{(seek_frame - 0.5) / fps:.6f}"] if seek_frame > 0 else []
    args = [*BASE, "-nostats", *seek, "-i", path, "-i", reference]
    for overlay in overlays:
        args += ["-i", overlay]
    graph = [
        f"[0:v]select=eq(n\\,{frame - seek_frame}),setpts=PTS-STARTPTS,settb=AVTB,split=2[dec][keep]"
    ]
    current = "1:v"
    for number in range(len(overlays)):
        graph.append(f"[{current}][{number + 2}:v]overlay=0:0:format=rgb[ref{number}]")
        current = f"ref{number}"
    graph.append(
        f"[{current}]scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,"
        "setpts=PTS-STARTPTS,settb=AVTB[refyuv]"
    )
    graph.append("[dec][refyuv]ssim[scored]")
    return [
        *args,
        "-filter_complex",
        ";".join(graph),
        "-map",
        "[keep]",
        "-frames:v",
        "1",
        "-update",
        "1",
        decoded_output,
        "-map",
        "[scored]",
        "-frames:v",
        "1",
        "-f",
        "null",
        "-",
    ]
