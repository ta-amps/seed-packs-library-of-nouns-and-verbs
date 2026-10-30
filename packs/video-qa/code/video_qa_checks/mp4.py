"""Read an MP4's boxes with the standard library and check them against a delivery spec.

probe() reads only box headers and the small boxes inside moov: brands, the order of moov and mdat
(moov first is what "fast start" means), fragments, edit lists, and per track the handler, codec,
size, timing, frame rate, H.264 profile and level, colour description, and AAC object type, channels
and sample rate. It never decodes media. check_spec() compares a probe with a spec and reports every
item as pass, fail or not_run with the measured value, so a missing fact is never a pass.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, BinaryIO

CONTAINERS = {"moov", "trak", "mdia", "minf", "stbl", "edts", "dinf", "udta"}
H264_PROFILES = {66: "Baseline", 77: "Main", 88: "Extended", 100: "High", 110: "High 10", 122: "High 4:2:2",
                 244: "High 4:4:4"}
EIGHT_BIT_420 = {66, 77, 88, 100}
AAC_TYPES = {1: "AAC Main", 2: "AAC-LC", 3: "AAC SSR", 4: "AAC LTP", 5: "HE-AAC", 29: "HE-AAC v2"}
VISUAL_CODECS = {"avc1", "avc3", "hvc1", "hev1", "av01", "vp09", "mp4v"}


def _header(data: bytes, offset: int, end: int) -> tuple[str, int, int] | None:
    """(type, header length, box size) of the box at offset, or None when no full header fits."""
    if offset + 8 > end:
        return None
    size, kind = struct.unpack(">I4s", data[offset:offset + 8])
    head = 8
    if size == 1:
        if offset + 16 > end:
            return None
        size = struct.unpack(">Q", data[offset + 8:offset + 16])[0]
        head = 16
    elif size == 0:
        size = end - offset
    if size < head or offset + size > end:
        raise ValueError(f"box {kind!r} at {offset} has size {size}, past its parent's end {end}")
    return kind.decode("latin-1"), head, size


def boxes(data: bytes, start: int = 0, end: int | None = None) -> list[tuple[str, int, int, int]]:
    """Child boxes of a byte range as (type, start, header length, size)."""
    end = len(data) if end is None else end
    out = []
    offset = start
    while True:
        found = _header(data, offset, end)
        if found is None:
            break
        kind, head, size = found
        out.append((kind, offset, head, size))
        offset += size
    return out


def top_level(handle: BinaryIO) -> list[tuple[str, int, int]]:
    """Top-level boxes of an open file as (type, offset, size), reading only their headers."""
    handle.seek(0, 2)
    length = handle.tell()
    out = []
    offset = 0
    while offset + 8 <= length:
        handle.seek(offset)
        head = handle.read(16)
        size, kind = struct.unpack(">I4s", head[:8])
        if size == 1:
            size = struct.unpack(">Q", head[8:16])[0]
        elif size == 0:
            size = length - offset
        if size < 8:
            raise ValueError(f"top-level box at {offset} has size {size}")
        out.append((kind.decode("latin-1"), offset, size))
        offset += size
    return out


def _full(data: bytes, offset: int) -> tuple[int, int]:
    """Version and the position just after a full box's version and flags."""
    return data[offset], offset + 4


def _mvhd(data: bytes, body: int) -> tuple[int, int]:
    version, at = _full(data, body)
    if version == 1:
        timescale, duration = struct.unpack(">IQ", data[at + 16:at + 28])
    else:
        timescale, duration = struct.unpack(">II", data[at + 8:at + 16])
    return timescale, duration


def _tkhd(data: bytes, body: int) -> tuple[float, float]:
    version, at = _full(data, body)
    at += 32 if version == 1 else 20
    at += 8 + 2 + 2 + 2 + 2 + 36
    width, height = struct.unpack(">II", data[at:at + 8])
    return width / 65536, height / 65536


def _descriptor(data: bytes, offset: int) -> tuple[int, int, int]:
    """(tag, payload start, payload size) of an MPEG-4 descriptor with its variable-length size."""
    tag = data[offset]
    size = 0
    at = offset + 1
    for _ in range(4):
        byte = data[at]
        at += 1
        size = (size << 7) | (byte & 0x7F)
        if not byte & 0x80:
            break
    return tag, at, size


def _audio_object_type(data: bytes, body: int, end: int) -> int | None:
    """The audioObjectType in an esds box's AudioSpecificConfig, or None when it is absent."""
    at = body + 4
    while at < end:
        tag, payload, size = _descriptor(data, at)
        if tag == 0x03:
            flags = data[payload + 2]
            at = payload + 3
            if flags & 0x80:
                at += 2
            if flags & 0x40:
                at += 1 + data[at]
            if flags & 0x20:
                at += 2
        elif tag == 0x04:
            at = payload + 13
        elif tag == 0x05:
            first = data[payload] >> 3
            if first == 31:
                return 32 + (((data[payload] & 0x07) << 3) | (data[payload + 1] >> 5))
            return first
        else:
            at = payload + size
    return None


def _sample_entry(data: bytes, start: int, head: int, size: int, track: dict[str, Any]) -> None:
    end = start + size
    kind = data[start + 4:start + 8].decode("latin-1")
    track["codec"] = kind
    if kind in VISUAL_CODECS:
        width, height = struct.unpack(">HH", data[start + 32:start + 36])
        track["coded_width"], track["coded_height"] = width, height
        for child, at, chead, csize in boxes(data, start + 86, end):
            body = at + chead
            if child == "avcC":
                idc = data[body + 1]
                track["profile_idc"] = idc
                track["profile"] = H264_PROFILES.get(idc, f"profile {idc}")
                track["level"] = data[body + 3] / 10
                if idc in EIGHT_BIT_420:
                    track["chroma"], track["bit_depth"] = "4:2:0", 8
            elif child == "colr" and data[body:body + 4] in (b"nclx", b"nclc"):
                primaries, transfer, matrix = struct.unpack(">HHH", data[body + 4:body + 10])
                full = bool(data[body + 10] & 0x80) if data[body:body + 4] == b"nclx" else None
                track["color"] = {"primaries": primaries, "transfer": transfer, "matrix": matrix,
                                  "full_range": full}
    elif kind == "mp4a":
        version = struct.unpack(">H", data[start + 16:start + 18])[0]
        track["channels"] = struct.unpack(">H", data[start + 24:start + 26])[0]
        track["sample_rate"] = struct.unpack(">I", data[start + 32:start + 36])[0] >> 16
        children = start + {0: 36, 1: 52, 2: 72}.get(version, 36)
        for child, at, chead, csize in boxes(data, children, end):
            if child == "esds":
                aot = _audio_object_type(data, at + chead, at + csize)
                track["audio_object_type"] = aot
                track["profile"] = AAC_TYPES.get(aot, f"object type {aot}") if aot is not None else None


def _walk(data: bytes, start: int, end: int, track: dict[str, Any]) -> None:
    for kind, at, head, size in boxes(data, start, end):
        body = at + head
        if kind in CONTAINERS:
            _walk(data, body, at + size, track)
        elif kind == "tkhd":
            track["width"], track["height"] = _tkhd(data, body)
        elif kind == "mdhd":
            track["timescale"], track["media_duration"] = _mvhd(data, body)
        elif kind == "hdlr":
            track["handler"] = data[body + 8:body + 12].decode("latin-1")
        elif kind == "elst":
            track["edit_list"] = True
            track["edit_entries"] = struct.unpack(">I", data[body + 4:body + 8])[0]
        elif kind == "stsd":
            for entry, eat, ehead, esize in boxes(data, body + 8, at + size):
                _sample_entry(data, eat, ehead, esize, track)
                break
        elif kind == "stts":
            count = struct.unpack(">I", data[body + 4:body + 8])[0]
            pairs = [struct.unpack(">II", data[body + 8 + 8 * i:body + 16 + 8 * i]) for i in range(count)]
            track["samples"] = sum(n for n, _ in pairs)
            deltas = {d for n, d in pairs if n}
            track["constant_rate"] = len(deltas) == 1
            track["sample_delta"] = deltas.pop() if len(deltas) == 1 else None


def probe(path: str | Path) -> dict[str, Any]:
    """Facts about an MP4 file from its boxes; nothing is decoded."""
    path = Path(path)
    with path.open("rb") as handle:
        top = top_level(handle)
        size_bytes = handle.seek(0, 2)
        kinds = [kind for kind, _, _ in top]
        moov = next(((offset, size) for kind, offset, size in top if kind == "moov"), None)
        ftyp = next(((offset, size) for kind, offset, size in top if kind == "ftyp"), None)
        brands: dict[str, Any] | None = None
        if ftyp:
            handle.seek(ftyp[0] + 8)
            raw = handle.read(ftyp[1] - 8)
            brands = {"major": raw[:4].decode("latin-1"), "minor": struct.unpack(">I", raw[4:8])[0],
                      "compatible": [raw[i:i + 4].decode("latin-1") for i in range(8, len(raw) - 3, 4)]}
        data = b""
        if moov:
            handle.seek(moov[0])
            data = handle.read(moov[1])
    result: dict[str, Any] = {
        "file": path.name, "size_bytes": size_bytes, "top_level": [[k, s] for k, _, s in top], "brands": brands,
        "faststart": None, "fragmented": "moof" in kinds, "duration_s": None, "bitrate_kbps": None, "tracks": [],
    }
    if "moov" in kinds and "mdat" in kinds:
        result["faststart"] = kinds.index("moov") < kinds.index("mdat")
    if not data:
        return result
    for kind, at, head, size in boxes(data, 8, len(data)):
        if kind == "mvhd":
            timescale, duration = _mvhd(data, at + head)
            result["duration_s"] = round(duration / timescale, 6) if timescale else None
        elif kind == "trak":
            track: dict[str, Any] = {"edit_list": False}
            _walk(data, at + head, at + size, track)
            if track.get("timescale"):
                track["duration_s"] = round(track["media_duration"] / track["timescale"], 6)
                if track.get("handler") == "vide" and track.get("sample_delta"):
                    track["frame_rate"] = round(track["timescale"] / track["sample_delta"], 3)
            result["tracks"].append(track)
    if result["duration_s"]:
        result["bitrate_kbps"] = round(size_bytes * 8 / result["duration_s"] / 1000, 1)
    return result


def _row(check: str, measured: Any, limit: Any, ok: bool | None, reason: str = "") -> dict[str, Any]:
    result = "not_run" if ok is None else ("pass" if ok else "fail")
    row = {"check": check, "result": result, "measured": measured, "limit": limit}
    if ok is None:
        row["reason"] = reason or "the file does not record this"
    return row


def check_spec(facts: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Each item of a delivery spec as a row: pass, fail or not_run, with what the file says."""
    rows = []
    container = spec.get("container", {})
    if "faststart" in container:
        got = facts["faststart"]
        rows.append(_row("faststart", got, container["faststart"], None if got is None else got == container["faststart"],
                         "no moov or no mdat box at the top level"))
    if "fragmented" in container:
        rows.append(_row("fragmented", facts["fragmented"], container["fragmented"],
                         facts["fragmented"] == container["fragmented"]))
    tracks = facts["tracks"]
    for kind, handler in (("video", "vide"), ("audio", "soun")):
        want = spec.get(kind)
        if not want:
            continue
        track = next((t for t in tracks if t.get("handler") == handler), None)
        if track is None:
            rows.append(_row(f"{kind}.present", None, True, False))
            continue
        for key, limit in want.items():
            got = track.get(key)
            if key == "profiles":
                got = track.get("profile")
                ok = None if got is None else got in limit
            elif key == "color_primaries":
                got = (track.get("color") or {}).get("primaries")
                ok = None if got is None else got == limit
            elif key == "even_dimensions":
                dims = (track.get("width"), track.get("height"))
                got = None if None in dims else all(int(v) % 2 == 0 for v in dims)
                ok = None if got is None else got == limit
            else:
                ok = None if got is None else (abs(got - limit) < 0.01 if isinstance(limit, float) else got == limit)
            rows.append(_row(f"{kind}.{key}", got, limit, ok))
    if "duration_s" in spec:
        got = facts["duration_s"]
        tolerance = spec.get("duration_tolerance_s", 0.05)
        rows.append(_row("duration_s", got, [spec["duration_s"], tolerance],
                         None if got is None else abs(got - spec["duration_s"]) <= tolerance))
    if "max_bytes" in spec:
        rows.append(_row("size_bytes", facts["size_bytes"], spec["max_bytes"], facts["size_bytes"] <= spec["max_bytes"]))
    if "max_bitrate_kbps" in spec:
        got = facts["bitrate_kbps"]
        rows.append(_row("bitrate_kbps", got, spec["max_bitrate_kbps"], None if got is None else got <= spec["max_bitrate_kbps"]))
    if spec.get("edit_lists") is False:
        with_lists = [t.get("handler") for t in tracks if t.get("edit_list")]
        rows.append(_row("edit_lists", with_lists, [], not with_lists))
    return rows
