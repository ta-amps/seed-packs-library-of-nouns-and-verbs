"""Find FFmpeg, read a video's stream facts, hash its bytes and decode its frames through a pipe."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterator

import numpy as np

FFMPEG_ENV = "FRAME_QA_FFMPEG"


class MediaError(RuntimeError):
    """FFmpeg is missing or a file cannot be read as video."""


def find_ffmpeg(explicit: str | None = None) -> str:
    """An explicit path, then FRAME_QA_FFMPEG, then imageio-ffmpeg's bundled build, then PATH."""
    for candidate in (explicit, os.environ.get(FFMPEG_ENV)):
        if candidate:
            if Path(candidate).is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
            raise MediaError(f"FFmpeg path is not an executable file: {candidate}")
    try:
        import imageio_ffmpeg

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:  # noqa: BLE001 - any failure falls through to PATH
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise MediaError(f"FFmpeg not found: set {FFMPEG_ENV}, install imageio-ffmpeg or put ffmpeg on PATH")


def ffmpeg_version(ffmpeg: str) -> str:
    out = subprocess.run([ffmpeg, "-hide_banner", "-version"], capture_output=True, text=True, check=False)
    first = (out.stdout or out.stderr).splitlines()
    return first[0].strip() if first else "unknown"


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


@dataclass(frozen=True)
class VideoInfo:
    path: str
    sha256: str
    bytes: int
    codec: str
    width: int
    height: int
    fps_num: int
    fps_den: int
    duration_s: float
    frames_estimated: int

    @property
    def fps(self) -> float:
        return self.fps_num / self.fps_den

    def to_json(self) -> dict:
        data = asdict(self)
        data["path"] = Path(self.path).name
        data["fps"] = round(self.fps, 6)
        return data


_STREAM = re.compile(r"Stream #\d+:\d+(?:\[[^\]]*\])?(?:\([^)]*\))?: Video: (?P<codec>[^\s,]+)(?P<rest>.*)")
_SIZE = re.compile(r"(?<![\d.])(\d{2,5})x(\d{2,5})(?![\d.])")
_FPS = re.compile(r"(\d+(?:\.\d+)?)(k?) (?:fps|tbr)")
_DURATION = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")


def _rate(text: str) -> Fraction:
    match = _FPS.search(text)
    if not match:
        raise MediaError("no frame rate in the stream line")
    value = float(match.group(1)) * (1000 if match.group(2) else 1)
    for num, den in ((24000, 1001), (30000, 1001), (60000, 1001)):
        if abs(value - num / den) < 0.005:
            return Fraction(num, den)
    return Fraction(value).limit_denominator(1001)


def probe(path: str | Path, ffmpeg: str) -> VideoInfo:
    """Stream facts from FFmpeg's own description of the first video stream, plus the file's SHA-256."""
    path = Path(path)
    if not path.is_file():
        raise MediaError(f"not a file: {path}")
    result = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-i", str(path)], capture_output=True, text=True, check=False)
    text = result.stderr
    stream = next((m for m in map(_STREAM.search, text.splitlines()) if m), None)
    if stream is None:
        raise MediaError(f"no video stream in {path.name}")
    size = _SIZE.search(stream.group("rest"))
    if size is None:
        raise MediaError(f"no frame size in {path.name}")
    rate = _rate(stream.group("rest"))
    duration = _DURATION.search(text)
    seconds = 0.0
    if duration:
        seconds = int(duration.group(1)) * 3600 + int(duration.group(2)) * 60 + float(duration.group(3))
    digest, size_bytes = sha256_file(path)
    return VideoInfo(
        path=str(path),
        sha256=digest,
        bytes=size_bytes,
        codec=stream.group("codec"),
        width=int(size.group(1)),
        height=int(size.group(2)),
        fps_num=rate.numerator,
        fps_den=rate.denominator,
        duration_s=round(seconds, 6),
        frames_estimated=int(round(seconds * rate.numerator / rate.denominator)),
    )


def frames(
    path: str | Path,
    ffmpeg: str,
    width: int,
    height: int,
    *,
    fps: float,
    start: int = 0,
    count: int | None = None,
    scale: tuple[int, int] | None = None,
    gray: bool = False,
) -> Iterator[np.ndarray]:
    """Decode frames start .. start+count-1 in display order, without dropping or duplicating any.

    A start after 0 seeks to half a frame before it, so FFmpeg's accurate seek returns that frame first.
    """
    out_w, out_h = scale or (width, height)
    channels = 1 if gray else 3
    cmd = [ffmpeg, "-v", "error", "-nostdin"]
    if start > 0:
        cmd += ["-ss", f"{(start - 0.5) / fps:.6f}"]
    cmd += ["-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn", "-fps_mode", "passthrough"]
    if count is not None:
        cmd += ["-frames:v", str(count)]
    if scale:
        cmd += ["-vf", f"scale={out_w}:{out_h}:flags=area"]
    cmd += ["-f", "rawvideo", "-pix_fmt", "gray" if gray else "bgr24", "-"]
    size = out_w * out_h * channels
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            frame = np.frombuffer(bytearray(buf), np.uint8)
            yield frame.reshape(out_h, out_w) if gray else frame.reshape(out_h, out_w, 3)
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()


def frame_at(path: str | Path, ffmpeg: str, info: VideoInfo, index: int) -> np.ndarray:
    """One full-size BGR frame by index."""
    for frame in frames(path, ffmpeg, info.width, info.height, fps=info.fps, start=index, count=1):
        return frame.copy()
    raise MediaError(f"frame {index} could not be decoded from {Path(path).name}")
