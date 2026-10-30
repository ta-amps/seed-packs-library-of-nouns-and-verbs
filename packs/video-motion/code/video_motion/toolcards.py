"""External tool cards: the exact binaries a video worker used, as nouns.

A card records the tool's name, version, SPDX license (and where that was read), the SHA-256 and
size of the binary that ran, where it came from, and the capabilities it was probed for. Cards
carry no local paths. This module only parses probe output; `video_motion.video_worker` runs the probes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from video_motion.nouns import SHA256_PATTERN, dimensions, json_value, pack_labels, value_sha256

ToolId = Literal["ffmpeg", "chromium", "playwright"]

# Every ffmpeg component the render and QA verbs use.
REQUIRED_FFMPEG: tuple[str, ...] = (
    "encoder:libx264",
    "encoder:aac",
    "encoder:pcm_s16le",
    "encoder:pcm_f32le",
    "encoder:png",
    "muxer:mp4",
    "muxer:wav",
    "muxer:framemd5",
    "muxer:null",
    "muxer:image2",
    "filter:overlay",
    "filter:xfade",
    "filter:concat",
    "filter:amix",
    "filter:asplit",
    "filter:sidechaincompress",
    "filter:adelay",
    "filter:apad",
    "filter:atrim",
    "filter:aresample",
    "filter:aformat",
    "filter:volume",
    "filter:loudnorm",
    "filter:ebur128",
    "filter:silencedetect",
    "filter:blackdetect",
    "filter:freezedetect",
    "filter:ssim",
    "filter:select",
    "filter:scale",
    "filter:pad",
    "filter:crop",
    "filter:fps",
    "filter:format",
    "filter:setsar",
    "filter:settb",
    "filter:setpts",
    "filter:trim",
    "filter:colorchannelmixer",
)


class ExternalToolCard(BaseModel):
    """One external tool binary used by a worker verb."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool_id: ToolId
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    license_spdx: str = Field(min_length=1)
    license_basis: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256_PATTERN)
    byte_size: int = Field(ge=1)
    distribution: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    build_configuration: list[str] = Field(default_factory=list)


def tool_noun_value(card: ExternalToolCard) -> dict[str, Any]:
    """The Tessera noun value for a tool card (category `noun.code_node`, role external_tool)."""
    value: dict[str, Any] = json_value(
        {
            "category_id": "noun.code_node",
            "role": "external_tool",
            **pack_labels(),
            "synthetic": False,
            "relations": [],
            "title": f"{card.name} {card.version}",
            "tool": card.model_dump(mode="json"),
            "fabric_admission": "pending",
            **dimensions(
                {
                    "determinism": "Pinned by binary SHA-256; repeat renders with this build are tested byte-identical.",
                    "evidence_grounding": "Version, license and capabilities were read from the binary by a worker probe.",
                    "verification_tier": "A recorded probe; this card was not re-probed when this value was written.",
                },
                synthetic=False,
                checked=False,
            ),
        }
    )
    return value


def card_sha256(card: ExternalToolCard) -> str:
    return value_sha256(card.model_dump(mode="json"))


_VERSION_RE = re.compile(r"^ffmpeg version (\S+)", re.MULTILINE)
_CONFIG_RE = re.compile(r"^configuration: (.*)$", re.MULTILINE)


def parse_ffmpeg_version(text: str) -> tuple[str, list[str]]:
    """Version string and configure flags from `ffmpeg -version`."""
    version = _VERSION_RE.search(text)
    config = _CONFIG_RE.search(text)
    flags = config.group(1).split() if config else []
    return (version.group(1) if version else "unknown"), flags


_ENCODER_LINE = re.compile(r"^ [VAS][.F][.S][.X][.B][.D] (?!=)(\S+)")
_FILTER_LINE = re.compile(r"^ [T.][S.][C.] (\S+)\s+\S*->\S*")
_FLAG_TOKEN = re.compile(r"^[DEd.]+$")


def parse_ffmpeg_components(text: str, kind: Literal["encoders", "muxers", "filters"]) -> set[str]:
    """Component names from `ffmpeg -encoders`, `-muxers` or `-filters` output."""
    names: set[str] = set()
    if kind == "encoders":
        return {m.group(1) for line in text.splitlines() if (m := _ENCODER_LINE.match(line))}
    if kind == "filters":
        return {m.group(1) for line in text.splitlines() if (m := _FILTER_LINE.match(line))}
    started = False
    for line in text.splitlines():
        if line.strip().startswith("--"):
            started = True
            continue
        if started:
            tokens = line.split()
            name = next((t for t in tokens if not _FLAG_TOKEN.match(t)), None)
            if name is not None:
                names.add(name)
    return names


def ffmpeg_license(license_text: str, flags: Iterable[str]) -> tuple[str, str]:
    """SPDX id for an ffmpeg build from its configure flags, cross-checked against `-L`."""
    flag_set = set(flags)
    if "--enable-nonfree" in flag_set or "nonfree" in license_text.lower():
        return "LicenseRef-FFmpeg-nonfree", "configure --enable-nonfree: not redistributable"
    gpl = "--enable-gpl" in flag_set
    v3 = "--enable-version3" in flag_set
    text = " ".join(license_text.split())
    if gpl:
        spdx = "GPL-3.0-or-later" if v3 else "GPL-2.0-or-later"
        expected = "GNU General Public License"
    else:
        spdx = "LGPL-3.0-or-later" if v3 else "LGPL-2.1-or-later"
        expected = "GNU Lesser General Public License"
    if expected not in text:
        return "LicenseRef-FFmpeg-unknown", "ffmpeg -L text did not match the configure flags"
    version_phrase = "either version 3" if v3 else "either version 2"
    if version_phrase not in text:
        return "LicenseRef-FFmpeg-unknown", "ffmpeg -L version wording did not match the flags"
    return spdx, "ffmpeg -L text and configure flags (--enable-gpl/--enable-version3)"


def ffmpeg_capabilities(
    encoders: set[str], muxers: set[str], filters: set[str]
) -> tuple[list[str], list[str]]:
    available = (
        {f"encoder:{name}" for name in encoders}
        | {f"muxer:{name}" for name in muxers}
        | {f"filter:{name}" for name in filters}
    )
    have = sorted(name for name in REQUIRED_FFMPEG if name in available)
    missing = sorted(name for name in REQUIRED_FFMPEG if name not in available)
    return have, missing


def chromium_license(license_text: str) -> tuple[str, str]:
    """SPDX id for a Chromium build from its bundled license file."""
    text = " ".join(license_text.split())
    if (
        "The Chromium Authors" in text
        and "Redistribution and use in source and binary forms" in text
    ):
        return (
            "BSD-3-Clause",
            "Chromium license file shipped with the binary; bundled third-party components keep their own licenses",
        )
    return "LicenseRef-Chromium-unknown", "no recognizable Chromium license file next to the binary"
