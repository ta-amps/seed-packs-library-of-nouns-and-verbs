"""Pinned media nouns, media elements and deterministic placeholder media generators.

A media noun describes one recording, image or audio file: what it is, the SHA-256 of its bytes,
where the bytes live, who made it, its SPDX license and whether it is generated. A `MediaElement`
binds that noun into a sequence by exact version and value digest (`NounPin`) plus the bytes'
digest, with trim in/out, crop, placement and caption keep-out boxes.

The generators produce placeholder narration tones, a music pad and a test-card image with only
the standard library and basic IEEE-754 arithmetic, so the same parameters give the same bytes on
any machine. Everything here is pure; nothing runs a subprocess or opens a network connection.
"""

from __future__ import annotations

import hashlib
import io
import json
import struct
import wave
import zlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from video_motion.errors import VideoMotionError
from video_motion.nouns import (
    DEFAULT_SEED_STORE,
    NAME_PATTERN,
    SHA256_PATTERN,
    NounPin,
    dimensions,
    json_value,
    pack_labels,
    pin_for,
    value_sha256,
)
from video_motion.schemas import (
    ACCEPTED_LICENSE_INPUTS,
    AspectId,
    Box2D,
    LicenseKind,
    normalize_license_id,
)

MediaKind = Literal["recording", "image", "audio"]
MediaProvenance = Literal["captured", "generated", "licensed"]
MediaMime = Literal[
    "video/mp4", "video/quicktime", "video/webm", "image/png", "image/jpeg", "audio/wav"
]
GeneratorTool = Literal[
    "video_motion.media:tone_bursts_wav",
    "video_motion.media:pad_wav",
    "video_motion.media:placeholder_card_png",
]
MIME_KIND: dict[str, MediaKind] = {
    "video/mp4": "recording",
    "video/quicktime": "recording",
    "video/webm": "recording",
    "image/png": "image",
    "image/jpeg": "image",
    "audio/wav": "audio",
}
MIME_SUFFIX: dict[str, str] = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "audio/wav": ".wav",
}
MEDIA_ROLE = "media_asset"


class MediaPinError(VideoMotionError):
    """Raised when a media noun, its value digest or its bytes do not match the pin."""

    def __init__(self, element_id: str, reason: str) -> None:
        super().__init__(
            409,
            "media_pin_mismatch",
            "Pinned Media Does Not Match",
            f"Media element {element_id!r}: {reason}",
        )


class ObjectPin(BaseModel):
    """A Tessera bucket object version holding media bytes."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    bucket: str = Field(pattern=NAME_PATTERN)
    key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_./:-]{0,511}$")
    version: int = Field(ge=1)
    sha256: str = Field(pattern=SHA256_PATTERN)


class MediaGenerator(BaseModel):
    """A deterministic generator in this package and the parameters that reproduce the media bytes exactly."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    tool: GeneratorTool
    params: dict[str, Any] = Field(default_factory=dict)


class MediaAsset(BaseModel):
    """What one media file is, the digest of its bytes, its rights and whether it is generated."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    media_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,95}$")
    kind: MediaKind
    mime_type: MediaMime
    title: str = Field(min_length=1)
    blob_sha256: str = Field(pattern=SHA256_PATTERN)
    byte_size: int = Field(ge=1)
    width: int | None = Field(default=None, ge=1, le=8192)
    height: int | None = Field(default=None, ge=1, le=8192)
    duration_s: float | None = Field(default=None, gt=0.0, le=3600.0)
    fps: float | None = Field(default=None, gt=0.0, le=240.0)
    sample_rate_hz: int | None = Field(default=None, ge=8000, le=192000)
    channels: int | None = Field(default=None, ge=1, le=8)
    license: Annotated[
        LicenseKind, WithJsonSchema({"type": "string", "enum": list(ACCEPTED_LICENSE_INPUTS)})
    ]
    creator: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    provenance: MediaProvenance
    made_up: bool
    disclosure: str = Field(min_length=1)
    generator: MediaGenerator | None = None
    object_ref: ObjectPin | None = None

    @field_validator("license", mode="before")
    @classmethod
    def _normalize_license(cls, value: object) -> object:
        return normalize_license_id(value)

    @model_validator(mode="after")
    def _check_consistency(self) -> MediaAsset:
        if MIME_KIND[self.mime_type] != self.kind:
            raise ValueError(f"mime_type {self.mime_type} does not describe a {self.kind}")
        if (self.provenance == "generated") != (self.generator is not None):
            raise ValueError("generated media needs a generator; captured/licensed media has none")
        if self.provenance == "generated" and not self.made_up:
            raise ValueError("generated media must be labeled made-up")
        if self.kind in ("recording", "image") and (self.width is None or self.height is None):
            raise ValueError("visual media needs width and height")
        if self.kind in ("recording", "audio") and self.duration_s is None:
            raise ValueError("timed media needs duration_s")
        if self.kind == "audio" and (self.sample_rate_hz is None or self.channels is None):
            raise ValueError("audio needs sample_rate_hz and channels")
        if self.object_ref is not None and self.object_ref.sha256 != self.blob_sha256:
            raise ValueError("object_ref.sha256 must equal blob_sha256")
        return self


class MediaPlacement(BaseModel):
    """Where a visual media element appears on one output aspect."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    box: Box2D
    crop: Box2D | None = None
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    keep_out: list[Box2D] = Field(default_factory=list)


class MediaElement(BaseModel):
    """A media noun bound into a sequence by exact version, value digest and bytes digest.

    `start_s` is relative to the container: the clip for overlays, the sequence for audio tracks.
    `crop` is in source pixels; `box` and `keep_out` are in output pixels. Captions must not cover
    a `keep_out` box while the element is visible.
    """

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    element_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,95}$")
    media: NounPin
    blob_sha256: str = Field(pattern=SHA256_PATTERN)
    kind: MediaKind
    trim_in_s: float = Field(default=0.0, ge=0.0)
    trim_out_s: float | None = Field(default=None, gt=0.0)
    start_s: float = Field(default=0.0, ge=0.0)
    duration_s: float | None = Field(default=None, gt=0.0)
    placements: dict[AspectId, MediaPlacement] = Field(default_factory=dict)
    gain_db: float = Field(default=0.0, ge=-60.0, le=12.0)

    @model_validator(mode="after")
    def _check_element(self) -> MediaElement:
        if self.trim_out_s is not None and self.trim_out_s <= self.trim_in_s:
            raise ValueError(f"{self.element_id}: trim_out_s must exceed trim_in_s")
        if self.kind == "audio" and self.placements:
            raise ValueError(f"{self.element_id}: audio elements have no visual placement")
        if self.kind == "image" and self.duration_s is None:
            raise ValueError(f"{self.element_id}: an image element needs duration_s")
        if self.kind != "image" and self.duration_s is None and self.trim_out_s is None:
            raise ValueError(f"{self.element_id}: set duration_s or trim_out_s")
        return self

    @property
    def span_s(self) -> float:
        """How long the element plays or stays visible."""
        if self.duration_s is not None:
            return self.duration_s
        assert self.trim_out_s is not None
        return self.trim_out_s - self.trim_in_s


def media_noun_value(asset: MediaAsset) -> dict[str, Any]:
    """The Tessera noun value for one media asset (category `noun.scene_recipe`, role media_asset).

    Tessera has no separate media category; media are asset bindings of scenes. The value carries
    the required dimensions and is what a `NounPin.value_sha256` covers.
    """
    basis = {
        "evidence_grounding": (
            "Generated placeholder media; rights and content are declared by this repository."
            if asset.made_up
            else "Declared capture or license metadata; rights are not independently attested."
        ),
        "verification_tier": "Bytes are checked against blob_sha256 when a worker reads them; writing this value reads no media.",
    }
    value: dict[str, Any] = json_value(
        {
            "category_id": "noun.scene_recipe",
            "role": MEDIA_ROLE,
            **pack_labels(),
            "made-up": asset.made_up,
            "relations": [],
            "title": asset.title,
            "asset": asset.model_dump(mode="json"),
            "fabric_admission": "pending",
            **dimensions(basis, made_up=asset.made_up, checked=False),
        }
    )
    return value


def media_pin(asset: MediaAsset, store: str = DEFAULT_SEED_STORE) -> NounPin:
    """The version-1 pin of `asset`'s media noun in `store`."""
    return pin_for(MEDIA_ROLE, media_noun_value(asset), store)


def asset_from_noun_value(value: dict[str, Any]) -> MediaAsset:
    """Read a media asset from a noun value: this package's wrapper (`asset`) or a bare asset value."""
    raw = value.get("asset", value)
    return MediaAsset.model_validate(raw)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MediaLibraryEntry(BaseModel):
    """One locally available media noun: its pin, its noun value and where its bytes are."""

    model_config = ConfigDict(extra="forbid", strict=True)

    pin: NounPin
    value: dict[str, Any]
    path: str = Field(min_length=1)


class LocalMediaLibrary:
    """Resolve pinned media elements to verified local files.

    A worker fills this from permitted Tessera reads (record value + bucket object) or, for
    generated media, by regenerating the bytes. Every resolution re-checks the value digest, the
    asset kind and the SHA-256 of the file bytes.
    """

    def __init__(self, root: Path, entries: Sequence[MediaLibraryEntry]) -> None:
        self.root = root
        self._entries = {(e.pin.store, e.pin.key, e.pin.version): e for e in entries}

    @classmethod
    def load(cls, index_path: Path) -> LocalMediaLibrary:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
        entries = [MediaLibraryEntry.model_validate(item) for item in raw["entries"]]
        return cls(index_path.parent, entries)

    def entries(self) -> list[MediaLibraryEntry]:
        return [self._entries[key] for key in sorted(self._entries)]

    def write_index(self, index_path: Path) -> None:
        payload = {
            "format": "video_motion.media-library.v1",
            "entries": [entry.model_dump(mode="json") for entry in self.entries()],
        }
        index_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")

    def resolve(self, element: MediaElement) -> tuple[MediaAsset, Path]:
        pin = element.media
        entry = self._entries.get((pin.store, pin.key, pin.version))
        if entry is None:
            raise MediaPinError(
                element.element_id, f"noun {pin.store}/{pin.key}@{pin.version} is not available"
            )
        if value_sha256(entry.value) != pin.value_sha256:
            raise MediaPinError(element.element_id, "noun value digest differs from the pin")
        asset = asset_from_noun_value(entry.value)
        if asset.kind != element.kind:
            raise MediaPinError(
                element.element_id, f"pinned noun is {asset.kind}, not {element.kind}"
            )
        if asset.blob_sha256 != element.blob_sha256:
            raise MediaPinError(element.element_id, "element blob_sha256 differs from the noun")
        path = (self.root / entry.path).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            raise MediaPinError(element.element_id, "media bytes are missing")
        if file_sha256(path) != asset.blob_sha256:
            raise MediaPinError(element.element_id, "media bytes do not match blob_sha256")
        return asset, path


# ---------------------------------------------------------------------------------------------
# Deterministic generators (standard library and basic IEEE-754 arithmetic only)
# ---------------------------------------------------------------------------------------------

# Taylor coefficients for sin(t) on [0, pi/2]; Horner evaluation uses only + and *.
_SIN_COEFFS = (
    1.0,
    -1.0 / 6.0,
    1.0 / 120.0,
    -1.0 / 5040.0,
    1.0 / 362880.0,
    -1.0 / 39916800.0,
    1.0 / 6227020800.0,
)
_TWO_PI = 6.283185307179586


def deterministic_sin_turns(turns: float) -> float:
    """sin(2*pi*turns) without libm, so every IEEE-754 platform returns the same bits."""
    u = turns - float(int(turns)) if turns >= 0.0 else turns - float(int(turns)) + 1.0
    sign = 1.0
    if u >= 0.5:
        u -= 0.5
        sign = -1.0
    if u > 0.25:
        u = 0.5 - u
    t = _TWO_PI * u
    t2 = t * t
    acc = 0.0
    for coeff in reversed(_SIN_COEFFS):
        acc = acc * t2 + coeff
    return sign * t * acc


def _sine_table(sample_rate_hz: int) -> list[float]:
    return [deterministic_sin_turns(i / sample_rate_hz) for i in range(sample_rate_hz)]


def _envelope(n: int, start: int, end: int, fade: int) -> float:
    if n < start or n >= end:
        return 0.0
    if fade <= 0:
        return 1.0
    return min(1.0, (n - start) / fade, (end - 1 - n) / fade)


def _wav_bytes(samples: Sequence[float], sample_rate_hz: int) -> bytes:
    pcm = bytearray()
    for value in samples:
        clipped = max(-1.0, min(1.0, value))
        pcm += struct.pack("<h", round(clipped * 32767.0))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate_hz)
        out.writeframes(bytes(pcm))
    return buffer.getvalue()


def tone_bursts_wav(
    *,
    duration_s: float,
    windows: Sequence[Sequence[float]],
    sample_rate_hz: int = 24000,
    freq_hz: int = 220,
    amplitude: float = 0.3,
    fade_s: float = 0.04,
) -> bytes:
    """Mono 16-bit WAV with a soft sine tone inside each [start, end] window, silence elsewhere.

    Used as a clearly labeled narration placeholder: the bursts mark where speech would be.
    """
    total = round(duration_s * sample_rate_hz)
    table = _sine_table(sample_rate_hz)
    fade = round(fade_s * sample_rate_hz)
    spans = [(round(w[0] * sample_rate_hz), round(w[1] * sample_rate_hz)) for w in windows]
    out = [0.0] * total
    for start, end in spans:
        for n in range(max(0, start), min(total, end)):
            # 4 Hz amplitude wobble keeps the placeholder from sounding like a test alarm.
            wobble = 0.85 + 0.15 * table[(n * 4) % sample_rate_hz]
            out[n] = (
                amplitude
                * wobble
                * _envelope(n, start, end, fade)
                * table[(n * freq_hz) % sample_rate_hz]
            )
    return _wav_bytes(out, sample_rate_hz)


def pad_wav(
    *,
    duration_s: float,
    sample_rate_hz: int = 24000,
    freqs_hz: Sequence[int] = (110, 165, 220),
    amplitude: float = 0.08,
    fade_s: float = 1.5,
) -> bytes:
    """Mono 16-bit WAV with a quiet sustained chord: a placeholder music bed."""
    total = round(duration_s * sample_rate_hz)
    table = _sine_table(sample_rate_hz)
    fade = round(fade_s * sample_rate_hz)
    scale = amplitude / max(1, len(freqs_hz))
    out = []
    for n in range(total):
        acc = 0.0
        for freq in freqs_hz:
            acc += table[(n * freq) % sample_rate_hz]
        out.append(scale * acc * _envelope(n, 0, total, fade))
    return _wav_bytes(out, sample_rate_hz)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def _zlib_stored(data: bytes) -> bytes:
    """A zlib stream of uncompressed deflate blocks: identical bytes with any zlib version."""
    out = bytearray(b"\x78\x01")
    if not data:
        out += b"\x01\x00\x00\xff\xff"
    for offset in range(0, len(data), 65535):
        block = data[offset : offset + 65535]
        final = 1 if offset + 65535 >= len(data) else 0
        out += bytes([final]) + struct.pack("<HH", len(block), len(block) ^ 0xFFFF) + block
    out += struct.pack(">I", zlib.adler32(data) & 0xFFFFFFFF)
    return bytes(out)


def placeholder_card_png(*, width: int = 960, height: int = 540) -> bytes:
    """RGB placeholder card (color bars, gray ramp, border, crosshair) for a screen-capture placeholder."""
    bars = [
        (191, 191, 191),
        (191, 191, 0),
        (0, 191, 191),
        (0, 191, 0),
        (191, 0, 191),
        (191, 0, 0),
        (0, 0, 191),
    ]
    rows = bytearray()
    bar_bottom = (height * 2) // 3
    for y in range(height):
        rows.append(0)  # PNG filter type 0 for this scanline
        for x in range(width):
            if x < 6 or y < 6 or x >= width - 6 or y >= height - 6:
                pixel = (248, 250, 252)
            elif abs(x - width // 2) < 2 or abs(y - height // 2) < 2:
                pixel = (15, 23, 42)
            elif y < bar_bottom:
                pixel = bars[(x * len(bars)) // width]
            else:
                level = (x * 255) // max(1, width - 1)
                pixel = (level, level, level)
            rows += bytes(pixel)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", _zlib_stored(bytes(rows)))
        + _png_chunk(b"IEND", b"")
    )


GENERATORS: dict[str, Callable[..., bytes]] = {
    "video_motion.media:tone_bursts_wav": tone_bursts_wav,
    "video_motion.media:pad_wav": pad_wav,
    "video_motion.media:placeholder_card_png": placeholder_card_png,
}


def generate_media_bytes(generator: MediaGenerator) -> bytes:
    """Run a generator with its recorded parameters."""
    return GENERATORS[generator.tool](**generator.params)


def describe_generated(
    *,
    media_id: str,
    title: str,
    generator: MediaGenerator,
    disclosure: str,
    payload: bytes,
) -> MediaAsset:
    """Build the media asset for freshly generated bytes, reading size and format from them."""
    tool = generator.tool
    fields: dict[str, Any] = {
        "media_id": media_id,
        "title": title,
        "blob_sha256": hashlib.sha256(payload).hexdigest(),
        "byte_size": len(payload),
        "license": "LicenseRef-Video-Motion-Procedural",
        "creator": "video-motion media generators",
        "source_uri": f"urn:video-motion:generated:{tool.partition(':')[2]}",
        "provenance": "generated",
        "made-up": True,
        "disclosure": disclosure,
        "generator": generator,
    }
    if tool == "video_motion.media:placeholder_card_png":
        width, height = struct.unpack(">II", payload[16:24])
        fields |= {"kind": "image", "mime_type": "image/png", "width": width, "height": height}
    else:
        with wave.open(io.BytesIO(payload), "rb") as audio:
            rate = audio.getframerate()
            fields |= {
                "kind": "audio",
                "mime_type": "audio/wav",
                "sample_rate_hz": rate,
                "channels": audio.getnchannels(),
                "duration_s": audio.getnframes() / rate,
            }
    return MediaAsset.model_validate(fields)


def materialize_generated(
    assets: Sequence[MediaAsset], root: Path, store: str = DEFAULT_SEED_STORE
) -> LocalMediaLibrary:
    """Regenerate generated media into `root`, verify every digest, and index them for resolution.

    Only `generated` media can be rebuilt from their recorded generator; captured or licensed
    media must come from their stored bytes.
    """
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for asset in assets:
        if asset.generator is None:
            raise MediaPinError(asset.media_id, "only generated media can be rebuilt locally")
        payload = generate_media_bytes(asset.generator)
        if hashlib.sha256(payload).hexdigest() != asset.blob_sha256:
            raise MediaPinError(asset.media_id, "regenerated bytes differ from blob_sha256")
        relative = f"{asset.blob_sha256}{MIME_SUFFIX[asset.mime_type]}"
        (root / relative).write_bytes(payload)
        value = media_noun_value(asset)
        entries.append(
            MediaLibraryEntry(pin=pin_for(MEDIA_ROLE, value, store), value=value, path=relative)
        )
    return LocalMediaLibrary(root, entries)
