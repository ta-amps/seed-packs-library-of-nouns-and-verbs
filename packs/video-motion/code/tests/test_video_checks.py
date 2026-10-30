"""Post-encode QA decisions, ffmpeg output parsers, tool cards and command lines (all pure)."""

from __future__ import annotations

from typing import Any

from video_motion.ffmpeg_graph import (
    ComposeInputs,
    compose_command,
    mix_command,
    spot_frame_command,
)
from video_motion.sequence import load_bundled_sequence, plan_sequence, sequence_srt, static_windows
from video_motion.toolcards import (
    REQUIRED_FFMPEG,
    chromium_license,
    ffmpeg_capabilities,
    ffmpeg_license,
    parse_ffmpeg_components,
    parse_ffmpeg_version,
)
from video_motion.video_checks import (
    Loudness,
    Segment,
    SpotCheck,
    StreamInfo,
    VideoMeasurements,
    evaluate_video,
    parse_black_segments,
    parse_ebur128,
    parse_ffmetadata,
    parse_freeze_segments,
    parse_loudnorm_json,
    parse_silence_segments,
    parse_ssim,
    parse_stream_info,
    speech_segments,
)

# Real ffmpeg 7.0.2 output captured while building this pipeline.
PROBE = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'probe.mp4':
  Metadata:
    major_brand     : isom
    title           : probe
    comment         : Synthetic visuals: test
  Duration: 00:00:04.00, start: 0.000000, bitrate: 162 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709, progressive), 1920x1080 [SAR 1:1 DAR 16:9], 1361 kb/s, 30 fps, 30 tbr, 15360 tbn (default)
      Metadata:
        handler_name    : VideoHandler
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 191 kb/s (default)
At least one output file must be specified
"""
DETECT = """[silencedetect @ 0x7c47b8003d80] silence_start: 1.999979
[blackdetect @ 0x7c47b40038c0] black_start:1.08 black_end:2.08 black_duration:1
[freezedetect @ 0x7c47b4003c80] lavfi.freezedetect.freeze_start: 1.08
[freezedetect @ 0x7c47b4003c80] lavfi.freezedetect.freeze_duration: 1
[freezedetect @ 0x7c47b4003c80] lavfi.freezedetect.freeze_end: 2.08
[freezedetect @ 0x7c47b4003c80] lavfi.freezedetect.freeze_start: 2.08
[Parsed_ebur128_0 @ 0x7c47b8003780] Summary:
  Integrated loudness:
    I:         -33.4 LUFS
    Threshold: -43.4 LUFS
    LRA:         2.8 LU
    Threshold: -56.1 LUFS
    LRA low:   -37.9 LUFS
    LRA high:  -35.1 LUFS
  True peak:
    Peak:      -32.6 dBFS
[silencedetect @ 0x7c47b8003d80] silence_end: 4.010667 | silence_duration: 2.010687
"""
SSIM = "[Parsed_ssim_4 @ 0x741a4c013100] SSIM Y:0.998578 (28.471495) U:0.990302 (20.133375) V:0.997384 (25.823224) All:0.997000 (25.228508)"
LOUDNORM = """[Parsed_loudnorm_0 @ 0x1]
{
	"input_i" : "-16.05",
	"input_tp" : "-13.20",
	"input_lra" : "16.80",
	"input_thresh" : "-30.89",
	"output_i" : "-13.95",
	"normalization_type" : "dynamic",
	"target_offset" : "-0.05"
}
"""
VERSION = """ffmpeg version 7.0.2-static https://johnvansickle.com/ffmpeg/  Copyright (c) 2000-2024 the FFmpeg developers
built with gcc 8 (Debian 8.3.0-6)
configuration: --enable-gpl --enable-version3 --enable-static --enable-libx264
"""
LICENSE_V3 = """ffmpeg is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version."""
ENCODERS = """Encoders:
 V..... = Video
 ------
 V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
 A....D aac                  AAC (Advanced Audio Coding)
"""
MUXERS = """ Formats:
 D.. = Demuxing supported
 .E. = Muxing supported
 ---
  E  mp4             MP4 (MPEG-4 Part 14)
 DE  wav             WAV / WAVE (Waveform Audio)
"""
FILTERS = """Filters:
  T.. = Timeline support
  A = Audio input/output
 TSC overlay           VV->V      Overlay a video source on top of the input.
 .S. xfade             VV->V      Cross fade one video with another video.
 ... anullsink         A->|       Do absolutely nothing with the input audio.
"""


def test_parsers_read_real_ffmpeg_output() -> None:
    info = parse_stream_info(PROBE)
    assert (info.video_codec, info.pix_fmt, info.width, info.height, info.fps) == (
        "h264",
        "yuv420p",
        1920,
        1080,
        30.0,
    )
    assert (info.audio_codec, info.sample_rate_hz, info.channels) == ("aac", 48000, "stereo")
    assert (
        info.duration_s == 4.0 and info.title == "probe" and info.color == "tv, bt709, progressive"
    )
    assert parse_black_segments(DETECT) == [Segment(start_s=1.08, end_s=2.08)]
    assert parse_freeze_segments(DETECT, 4.0) == [
        Segment(start_s=1.08, end_s=2.08),
        Segment(start_s=2.08, end_s=4.0),
    ]
    assert parse_silence_segments(DETECT, 4.0) == [Segment(start_s=1.999979, end_s=4.010667)]
    assert parse_ebur128(DETECT) == Loudness(
        integrated_lufs=-33.4, lra_lu=2.8, true_peak_dbfs=-32.6
    )
    assert parse_ssim(SSIM) == 0.997
    assert parse_loudnorm_json(LOUDNORM)["input_i"] == "-16.05"
    assert parse_ffmetadata(";FFMETADATA1\ntitle=a\\=b\ncomment=x\\;y\n[CHAPTER]\ntitle=z\n") == {
        "title": "a=b",
        "comment": "x;y",
    }
    assert speech_segments([Segment(start_s=1.0, end_s=2.0)], 3.0) == [
        Segment(start_s=0.0, end_s=1.0),
        Segment(start_s=2.0, end_s=3.0),
    ]


def test_tool_cards_read_version_license_and_capabilities() -> None:
    version, flags = parse_ffmpeg_version(VERSION)
    assert version == "7.0.2-static" and "--enable-libx264" in flags
    assert ffmpeg_license(LICENSE_V3, flags)[0] == "GPL-3.0-or-later"
    assert (
        ffmpeg_license(LICENSE_V3.replace("version 3", "version 2"), ["--enable-gpl"])[0]
        == "GPL-2.0-or-later"
    )
    assert ffmpeg_license(LICENSE_V3, [])[0] == "LicenseRef-FFmpeg-unknown"
    assert (
        ffmpeg_license(LICENSE_V3, [*flags, "--enable-nonfree"])[0] == "LicenseRef-FFmpeg-nonfree"
    )
    lgpl = LICENSE_V3.replace("General Public", "Lesser General Public").replace(
        "version 3", "version 2.1"
    )
    assert ffmpeg_license(lgpl, [])[0] == "LGPL-2.1-or-later"
    assert ffmpeg_license(lgpl, ["--enable-gpl"])[0] == "LicenseRef-FFmpeg-unknown"
    encoders = parse_ffmpeg_components(ENCODERS, "encoders")
    muxers = parse_ffmpeg_components(MUXERS, "muxers")
    filters = parse_ffmpeg_components(FILTERS, "filters")
    assert encoders == {"libx264", "aac"} and muxers == {"mp4", "wav"}
    assert filters == {"overlay", "xfade", "anullsink"}
    have, missing = ffmpeg_capabilities(encoders, muxers, filters)
    assert "filter:xfade" in have and "filter:ebur128" in missing
    assert set(have) | set(missing) == set(REQUIRED_FFMPEG)
    chromium = "// Copyright 2015 The Chromium Authors\n// Redistribution and use in source and binary forms, with or without"
    assert chromium_license(chromium)[0] == "BSD-3-Clause"
    assert chromium_license("")[0] == "LicenseRef-Chromium-unknown"


def _good(aspect: str) -> tuple[Any, Any, VideoMeasurements]:
    sequence, _ = load_bundled_sequence("hackathon-demo")
    plan = plan_sequence(sequence)
    speech = [(w.start_frame / 30 + 0.1, w.end_frame / 30 - 0.1) for w in plan.captions]
    silences, cursor = [], 0.0
    for start, end in speech:
        silences.append(Segment(start_s=cursor, end_s=start))
        cursor = end
    silences.append(Segment(start_s=cursor, end_s=plan.duration_s))
    width, height = (1920, 1080) if aspect == "landscape_16x9" else (1080, 1920)
    spot = SpotCheck(
        output_frame=60,
        clip_id="title",
        local_frame=60,
        captions=["cap-01"],
        manifest_frame_hash="a" * 64,
        evaluated_frame_hash="a" * 64,
        manifest_png_sha256="b" * 64,
        actual_png_sha256="b" * 64,
        ssim=0.9995,
        neighbor_frame=40,
        neighbor_ssim=0.995,
    )
    measurements = VideoMeasurements(
        info=StreamInfo(
            duration_s=21.4,
            video_codec="h264",
            pix_fmt="yuv420p",
            width=width,
            height=height,
            fps=30.0,
            audio_codec="aac",
            sample_rate_hz=48000,
            channels="stereo",
            title=sequence.title,
            comment="disclosed",
        ),
        decoded_frames=642,
        black=[],
        frozen=[Segment(start_s=18.7, end_s=21.0)],
        loudness=Loudness(integrated_lufs=-14.0, lra_lu=15.0, true_peak_dbfs=-11.0),
        narration_duration_s=21.4,
        narration_silences=silences,
        spots=[spot],
        srt=sequence_srt(sequence),
        expected_disclosure="disclosed",
    )
    return sequence, plan, measurements


def _evaluate(aspect: str, measurements: VideoMeasurements) -> dict[str, bool]:
    sequence, plan, _ = _good(aspect)
    report = evaluate_video(
        sequence,
        plan,
        aspect,  # type: ignore[arg-type]
        measurements,
        mp4_sha256="c" * 64,
        render_manifest_sha256="d" * 64,
        holds=static_windows(sequence, plan, aspect),  # type: ignore[arg-type]
    )
    assert len(report.receipt_sha256) == 64
    return {check.check: check.passed for check in report.checks}


def test_evaluation_passes_good_measurements_and_flags_each_failure() -> None:
    for aspect in ("landscape_16x9", "reels_9x16"):
        _, _, good = _good(aspect)
        assert all(_evaluate(aspect, good).values())
    _, _, good = _good("landscape_16x9")
    spot = good.spots[0]
    failures: dict[str, VideoMeasurements] = {
        "container_and_streams": good.model_copy(
            update={"info": good.info.model_copy(update={"width": 1280})}
        ),
        "duration_and_frames": good.model_copy(update={"decoded_frames": 641}),
        "black_frames": good.model_copy(update={"black": [Segment(start_s=3.0, end_s=4.0)]}),
        "frozen_frames": good.model_copy(update={"frozen": [Segment(start_s=8.0, end_s=10.5)]}),
        "integrated_loudness": good.model_copy(
            update={"loudness": Loudness(integrated_lufs=-20.0, lra_lu=1.0, true_peak_dbfs=-11.0)}
        ),
        "caption_timing_coverage": good.model_copy(update={"narration_silences": []}),
        "synthetic_disclosure": good.model_copy(
            update={"info": good.info.model_copy(update={"comment": "other"})}
        ),
    }
    for check, bad in failures.items():
        results = _evaluate("landscape_16x9", bad)
        assert not results[check], check
        assert all(passed for name, passed in results.items() if name != check), (check, results)
    for change in (
        {"ssim": 0.90},
        {"neighbor_ssim": 0.9996},
        {"evaluated_frame_hash": "e" * 64},
        {"actual_png_sha256": "f" * 64},
    ):
        bad_spot = good.model_copy(update={"spots": [spot.model_copy(update=change)]})
        assert not _evaluate("landscape_16x9", bad_spot)["frame_hash_spot_checks"], change
    hot = good.model_copy(
        update={"loudness": good.loudness.model_copy(update={"true_peak_dbfs": -0.5})}
    )
    assert not _evaluate("landscape_16x9", hot)["integrated_loudness"]
    missing_cue = good.model_copy(update={"srt": good.srt.split("\n\n", 1)[1]})
    assert not _evaluate("landscape_16x9", missing_cue)["caption_timing_coverage"]


def test_compose_and_mix_commands_follow_the_plan() -> None:
    sequence, _ = load_bundled_sequence("hackathon-demo")
    plan = plan_sequence(sequence)
    inputs = ComposeInputs(
        scene_frames={
            c: f"landscape_16x9/frames/{c}/%05d.png" for c in ("title", "diagram", "outro")
        },
        media_files={
            "outro-screen-capture": "media/card.png",
            "narration": "media/n.wav",
            "music-bed": "media/m.wav",
        },
        caption_images={w.ref_id: f"landscape_16x9/captions/{w.ref_id}.png" for w in plan.captions},
        master_audio="audio/master.wav",
    )
    args = compose_command(
        sequence, plan, "landscape_16x9", inputs, "out.mp4", title="T", comment="C"
    )
    graph = args[args.index("-filter_complex") + 1]
    assert "xfade=transition=fade:duration=0.600000:offset=5.400000" in graph
    assert "concat=n=2:v=1:a=0" in graph
    for window in plan.captions:
        assert f"between(n,{window.start_frame},{window.end_frame - 1})" in graph
    assert "overlay=x=1060:y=340:enable='between(n,24,173)'" in graph
    assert args[args.index("-frames:v") + 1] == "642"
    assert {"+bitexact", "comment=C", "title=T", "libx264", "aac", "out.mp4"} <= set(args)
    assert not [a for a in args if a.startswith("/")]
    mix = mix_command(sequence, plan, inputs.media_files, "audio/mix.wav", "audio/narration.wav")
    mix_graph = mix[mix.index("-filter_complex") + 1]
    assert "sidechaincompress=threshold=0.02:ratio=4" in mix_graph
    assert "apad=whole_dur=21.400000,atrim=end=21.400000" in mix_graph
    assert mix[-1] == "audio/narration.wav" and "audio/mix.wav" in mix
    silent = sequence.model_copy(update={"narration": [], "music_bed": None})
    quiet = mix_command(silent, plan, {}, "audio/mix.wav", "audio/narration.wav")
    assert quiet[quiet.index("-f") + 1] == "lavfi" and "[0:a]anull[narr]" in "".join(quiet)
    assert "sidechaincompress" not in "".join(quiet)
    spot = spot_frame_command("out.mp4", 300, 30, "ref.png", ["cap.png"], "dec.png")
    assert spot[spot.index("-ss") + 1] == f"{269.5 / 30:.6f}"
    assert "select=eq(n\\,30)" in spot[spot.index("-filter_complex") + 1]
    assert "-ss" not in spot_frame_command("out.mp4", 10, 30, "ref.png", [], "dec.png")
