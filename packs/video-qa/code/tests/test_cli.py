"""The command line in a temporary folder: exit codes follow failures, and it refuses to write inside the library."""

from __future__ import annotations

import contextlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from video_qa_checks.__main__ import library_root, main

VTT = "WEBVTT\n\n00:00:00.400 --> 00:00:03.000\nEvery evening, volunteers check.\n\n" \
      "00:00:03.100 --> 00:00:05.800\nThey log what is low.\n"
SRT = "1\n00:00:00,400 --> 00:00:03,000\nEvery evening, volunteers check.\n\n" \
      "2\n00:00:03,100 --> 00:00:05,800\nThey log what is low.\n"
FAST = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nThis cue says far too much for one second.\n"
PICTURE = "[blackdetect @ 0x1] black_start:4 black_end:4.6 black_duration:0.6\n"
SOUND = """[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -16.2 LUFS
    Threshold: -26.3 LUFS

  Loudness range:
    LRA:         3.1 LU

  True peak:
    Peak:       -1.8 dBFS
"""


def run(*argv: str) -> tuple[int, object]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, json.loads(out.getvalue())


def box(kind: str, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind.encode()) + payload


class CommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for name, text in (("a.vtt", VTT), ("a.srt", SRT), ("fast.vtt", FAST), ("picture.log", PICTURE),
                           ("sound.log", SOUND)):
            (self.dir / name).write_text(text, encoding="utf-8")
        (self.dir / "speech.json").write_text(json.dumps({"speech_ms": [[420, 2900], [3150, 5700]]}), encoding="utf-8")
        (self.dir / "plan.json").write_text(json.dumps({"duration_s": 6.0, "fps": 30}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def path(self, name: str) -> str:
        return str(self.dir / name)

    def test_captions_pass_and_fail(self) -> None:
        code, row = run("captions", "--vtt", self.path("a.vtt"), "--srt", self.path("a.srt"), "--speech", self.path("speech.json"))
        self.assertEqual((code, row["result"]), (0, "pass"))
        self.assertEqual(row["measured"]["srt_differences"], 0)
        code, row = run("captions", "--vtt", self.path("fast.vtt"))
        self.assertEqual((code, row["result"]), (1, "fail"))

    def test_picture_and_sound_rows(self) -> None:
        code, rows = run("picture", "--plan", self.path("plan.json"), "--black", self.path("picture.log"),
                         "--freeze", self.path("picture.log"))
        self.assertEqual(code, 1)
        self.assertEqual([r["result"] for r in rows], ["fail", "pass", "not_run"])
        code, rows = run("sound", "--plan", self.path("plan.json"), "--ebur128", self.path("sound.log"))
        self.assertEqual(code, 0)
        self.assertEqual([(r["check"], r["result"]) for r in rows],
                         [("loudness", "pass"), ("silence_gaps", "not_run"), ("clipping", "not_run")])

    def test_filespec_on_a_file_whose_moov_comes_last(self) -> None:
        mvhd = box("mvhd", bytes(4) + struct.pack(">IIII", 0, 0, 1000, 6000) + bytes(80))
        (self.dir / "a.mp4").write_bytes(box("ftyp", b"isom" + bytes(4)) + box("mdat", bytes(64)) + box("moov", mvhd))
        (self.dir / "spec.json").write_text(json.dumps({"container": {"faststart": True}, "duration_s": 6.0}), encoding="utf-8")
        code, row = run("filespec", "--mp4", self.path("a.mp4"), "--spec", self.path("spec.json"))
        self.assertEqual((code, row["result"]), (1, "fail"))
        self.assertEqual([i["result"] for i in row["measured"]["items"]], ["fail", "pass"])

    def test_legibility_and_a_report_written_outside_the_library(self) -> None:
        items = {"frame": {"width": 1920, "height": 1080}, "displays": [{"name": "phone held sideways", "width_px": 844}],
                 "items": [{"id": "label", "role": "label", "px": 20, "box": [40, 1010, 300, 30]}]}
        (self.dir / "items.json").write_text(json.dumps(items), encoding="utf-8")
        code, row = run("legibility", "--items", self.path("items.json"), "--out", self.path("leg.json"))
        self.assertEqual((code, row["result"]), (0, "warn"))
        code, report = run("report", "--media", self.path("a.vtt"), "--plan", self.path("plan.json"),
                           "--part", self.path("leg.json"), "--out", self.path("report.json"))
        self.assertEqual(code, 0)
        self.assertEqual(report["verdict"], "incomplete")
        self.assertEqual(len(report["media"]["sha256"]), 64)
        self.assertTrue((self.dir / "report.json").exists())

    def test_output_inside_the_library_is_refused(self) -> None:
        root = library_root()
        self.assertIsNotNone(root)
        target = root / "packs" / "video-qa" / "code" / "out.json"
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
            main(["captions", "--vtt", self.path("a.vtt"), "--out", str(target)])
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
