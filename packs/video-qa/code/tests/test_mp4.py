"""The box reader on MP4 files built byte by byte here, so every value it reports is known in advance."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from video_qa_checks.mp4 import boxes, check_spec, probe


def box(kind: str, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind.encode("latin-1")) + payload


def full(kind: str, payload: bytes, version: int = 0) -> bytes:
    return box(kind, bytes([version, 0, 0, 0]) + payload)


def video_trak(fps: int = 30, frames: int = 60, width: int = 1280, height: int = 720, profile: int = 100,
               edit_list: bool = True) -> bytes:
    timescale = fps * 512
    tkhd = full("tkhd", struct.pack(">IIIII", 0, 0, 1, 0, frames * 1000 // fps) + bytes(52)
                + struct.pack(">II", width << 16, height << 16))
    mdhd = full("mdhd", struct.pack(">IIIIHH", 0, 0, timescale, frames * 512, 0x55C4, 0))
    hdlr = full("hdlr", struct.pack(">I4s", 0, b"vide") + bytes(12) + b"Video\x00")
    avcc = box("avcC", bytes([1, profile, 0, 40, 0xFF, 0xE1, 0, 0, 1, 0, 0]))
    colr = box("colr", b"nclx" + struct.pack(">HHH", 1, 1, 1) + bytes([0]))
    entry = bytes(6) + struct.pack(">H", 1) + bytes(16) + struct.pack(">HH", width, height) + bytes(50) + avcc + colr
    stsd = full("stsd", struct.pack(">I", 1) + box("avc1", entry))
    stts = full("stts", struct.pack(">III", 1, frames, 512))
    stbl = box("stbl", stsd + stts)
    minf = box("minf", stbl)
    mdia = box("mdia", mdhd + hdlr + minf)
    edts = box("edts", full("elst", struct.pack(">IIIi", 1, frames * 1000 // fps, 0, 1 << 16))) if edit_list else b""
    return box("trak", tkhd + edts + mdia)


def audio_trak(rate: int = 48000, channels: int = 2, object_type: int = 2) -> bytes:
    mdhd = full("mdhd", struct.pack(">IIIIHH", 0, 0, rate, rate * 2, 0x55C4, 0))
    hdlr = full("hdlr", struct.pack(">I4s", 0, b"soun") + bytes(12) + b"Sound\x00")
    asc = bytes([(object_type << 3) | 0x01, 0x90])
    dsi = bytes([0x05, 0x80, 0x80, 0x80, len(asc)]) + asc
    dcd_body = bytes([0x40, 0x15]) + bytes(3) + struct.pack(">II", 128000, 128000) + dsi
    dcd = bytes([0x04, 0x80, 0x80, 0x80, len(dcd_body)]) + dcd_body
    es_body = struct.pack(">HB", 1, 0) + dcd + bytes([0x06, 0x80, 0x80, 0x80, 1, 0x02])
    esds = full("esds", bytes([0x03, 0x80, 0x80, 0x80, len(es_body)]) + es_body)
    entry = bytes(6) + struct.pack(">H", 1) + bytes(8) + struct.pack(">HHHHI", channels, 16, 0, 0, rate << 16) + esds
    stsd = full("stsd", struct.pack(">I", 1) + box("mp4a", entry))
    stts = full("stts", struct.pack(">IIIII", 2, 90, 1024, 4, 960))
    mdia = box("mdia", mdhd + hdlr + box("minf", box("stbl", stsd + stts)))
    tkhd = full("tkhd", bytes(20) + bytes(52) + bytes(8))
    return box("trak", tkhd + mdia)


def movie(moov_first: bool, seconds: int = 2, **video: object) -> bytes:
    ftyp = box("ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2avc1mp41")
    mvhd = full("mvhd", struct.pack(">IIII", 0, 0, 1000, seconds * 1000) + bytes(80))
    moov = box("moov", mvhd + video_trak(**video) + audio_trak())  # type: ignore[arg-type]
    mdat = box("mdat", bytes(4000))
    return ftyp + (moov + mdat if moov_first else mdat + moov)


SPEC = {"container": {"faststart": True, "fragmented": False},
        "video": {"codec": "avc1", "profiles": ["High"], "chroma": "4:2:0", "width": 1280, "height": 720,
                  "frame_rate": 30.0, "constant_rate": True, "color_primaries": 1, "even_dimensions": True},
        "audio": {"codec": "mp4a", "audio_object_type": 2, "sample_rate": 48000, "channels": 2},
        "duration_s": 2.0, "max_bytes": 100_000, "max_bitrate_kbps": 400, "edit_lists": False}


class Probe(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, data: bytes) -> Path:
        path = self.dir / name
        path.write_bytes(data)
        return path

    def test_fast_start_tracks_and_codecs(self) -> None:
        facts = probe(self.write("fast.mp4", movie(True)))
        self.assertTrue(facts["faststart"])
        self.assertFalse(facts["fragmented"])
        self.assertEqual([k for k, _ in facts["top_level"]], ["ftyp", "moov", "mdat"])
        self.assertEqual(facts["brands"]["compatible"], ["isom", "iso2", "avc1", "mp41"])
        self.assertEqual(facts["duration_s"], 2.0)
        video, audio = facts["tracks"]
        self.assertEqual((video["handler"], video["codec"], video["profile"], video["level"]), ("vide", "avc1", "High", 4.0))
        self.assertEqual((video["width"], video["height"], video["coded_width"]), (1280.0, 720.0, 1280))
        self.assertEqual((video["frame_rate"], video["samples"], video["constant_rate"]), (30.0, 60, True))
        self.assertEqual(video["color"], {"primaries": 1, "transfer": 1, "matrix": 1, "full_range": False})
        self.assertTrue(video["edit_list"])
        self.assertEqual((audio["handler"], audio["codec"], audio["profile"]), ("soun", "mp4a", "AAC-LC"))
        self.assertEqual((audio["sample_rate"], audio["channels"], audio["constant_rate"]), (48000, 2, False))

    def test_moov_after_mdat_is_not_fast_start(self) -> None:
        self.assertFalse(probe(self.write("slow.mp4", movie(False)))["faststart"])

    def test_spec_rows_pass_fail_and_not_run(self) -> None:
        facts = probe(self.write("fast.mp4", movie(True)))
        rows = {r["check"]: r for r in check_spec(facts, SPEC)}
        self.assertEqual(rows["faststart"]["result"], "pass")
        self.assertEqual(rows["video.profiles"]["result"], "pass")
        self.assertEqual(rows["audio.audio_object_type"]["result"], "pass")
        self.assertEqual(rows["edit_lists"], {"check": "edit_lists", "result": "fail", "measured": ["vide"], "limit": []})
        main = probe(self.write("main.mp4", movie(True, profile=77, edit_list=False)))
        rows = {r["check"]: r for r in check_spec(main, SPEC)}
        self.assertEqual(rows["video.profiles"]["result"], "fail")
        self.assertEqual(rows["edit_lists"]["result"], "pass")
        no_colr = dict(main, tracks=[{k: v for k, v in main["tracks"][0].items() if k != "color"}, main["tracks"][1]])
        rows = {r["check"]: r for r in check_spec(no_colr, SPEC)}
        self.assertEqual(rows["video.color_primaries"]["result"], "not_run")

    def test_a_25_fps_odd_sized_file(self) -> None:
        facts = probe(self.write("odd.mp4", movie(True, fps=25, frames=50, width=1279)))
        rows = {r["check"]: r for r in check_spec(facts, SPEC)}
        self.assertEqual(facts["tracks"][0]["frame_rate"], 25.0)
        self.assertEqual(rows["video.frame_rate"]["result"], "fail")
        self.assertEqual(rows["video.even_dimensions"]["result"], "fail")

    def test_large_size_boxes_and_bad_sizes(self) -> None:
        large = struct.pack(">I4sQ", 1, b"free", 24) + bytes(8)
        self.assertEqual(boxes(large), [("free", 0, 16, 24)])
        with self.assertRaises(ValueError):
            boxes(struct.pack(">I4s", 64, b"free") + bytes(8))


if __name__ == "__main__":
    unittest.main()
