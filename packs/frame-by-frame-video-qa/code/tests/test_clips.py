"""End to end on made-up clips FFmpeg draws in the test: a layout clip (clean, text off an edge, text in the
action margin, small and tiny text, faint text, overlapping text and a chip, proof text under a caption, a
panel cut by the frame) and a time clip (a crossfade between text slides, a white frame, black frames, a freeze,
fast-moving text and a jump). FRAME_QA_REQUIRE_FFMPEG=1 and FRAME_QA_REQUIRE_OCR=1 turn a missing tool into a
failure instead of a skip; CI sets both."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from frame_qa.media import MediaError, find_ffmpeg, frames, probe
from frame_qa.pipeline import run_film
from frame_qa.text import ocr_available

from helpers import PACKS, pack_nouns

sys.path.insert(0, str(PACKS.parent / "scripts"))
import build_packs  # noqa: E402

NOTICED = "2026-10-30"


def _ffmpeg() -> str | None:
    try:
        return find_ffmpeg()
    except MediaError:
        if os.environ.get("FRAME_QA_REQUIRE_FFMPEG") == "1":
            raise
        return None


FFMPEG = _ffmpeg()


def found(doc: dict, cut: str) -> list[tuple[str, str, float, float]]:
    rows = next(c for c in doc["cuts"] if c["label"] == cut)["findings"]
    return [(f["kind"], f["severity"], f["t_start"], f["t_end"]) for f in rows]


def has(rows, kind: str, start: float, end: float, severity: str | None = None) -> bool:
    return any(k == kind and (severity is None or s == severity) and a < end and b > start for k, s, a, b in rows)


@unittest.skipIf(FFMPEG is None, "FFmpeg is not available")
class Clips(unittest.TestCase):
    tmp: Path
    clips: dict

    @classmethod
    def setUpClass(cls) -> None:
        from frame_qa.synth import make_clips

        cls.tmp = Path(tempfile.mkdtemp(prefix="frame-qa-test-"))
        cls.clips = make_clips(FFMPEG, cls.tmp / "clips")
        for name in ("layout", "time"):
            pixels = np.stack(list(frames(cls.clips[name], FFMPEG, 1280, 720, fps=30.0, scale=(160, 90), gray=True)))
            if float(pixels.std()) < 5:
                raise AssertionError(f"FFmpeg drew nothing into the {name} clip")
        cls.cv = run_film(cls._pairs(), cls.tmp / "cv", engine="cv", workers=2, noticed_at=NOTICED, log=lambda m: None)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def _pairs(cls):
        return [(cls.clips["layout"], cls.clips["layout_vtt"]), (cls.clips["time"], None)]

    def test_a_seek_returns_the_same_frame_as_decoding_from_the_start(self) -> None:
        clip = self.clips["time"]
        info = probe(clip, FFMPEG)
        sequential = list(frames(clip, FFMPEG, info.width, info.height, fps=info.fps, scale=(160, 90), gray=True))
        self.assertEqual(len(sequential), 226)
        for start in (1, 44, 45, 60, 61, 120, 225):
            first = next(iter(frames(clip, FFMPEG, info.width, info.height, fps=info.fps, start=start, count=1, scale=(160, 90), gray=True)))
            self.assertTrue(np.array_equal(first, sequential[start]), f"frame {start}")

    def test_layout_findings_with_the_model_free_engine(self) -> None:
        rows = found(self.cv, "layout")
        self.assertFalse([r for r in rows if r[2] < 0.95 and r[1] != "note"], "the clean opening second has no problems")
        self.assertTrue(has(rows, "text_in_action_margin", 2.0, 3.0, "minor"))
        self.assertTrue(has(rows, "under_16_px", 3.0, 4.0, "major"))
        self.assertTrue(has(rows, "under_24_px", 3.0, 4.0))
        self.assertTrue(has(rows, "under_caption_box", 6.0, 7.0, "major"))
        self.assertTrue(has(rows, "panel_at_edge", 7.0, 8.0))
        self.assertFalse(has(rows, "blank_frames", 0.0, 8.0), "faint text is not a blank frame")

    def test_time_findings(self) -> None:
        rows = found(self.cv, "time")
        cut = next(c for c in self.cv["cuts"] if c["label"] == "time")
        self.assertEqual([e["type"] for e in cut["transitions"]["events"] if e["type"] == "dissolve"], ["dissolve"])
        self.assertTrue(has(rows, "double_exposure", 0.45, 1.1, "major"))
        self.assertTrue(has(rows, "flash_frame", 1.99, 2.04, "major"))
        self.assertFalse(has(rows, "blank_frames", 1.9, 2.1), "the white frame is reported once, as a flash")
        self.assertTrue(has(rows, "black_frames", 2.5, 3.2, "major"))
        self.assertTrue(has(rows, "freeze", 3.2, 5.5, "minor"))
        self.assertTrue(has(rows, "text_motion", 5.5, 6.3, "major"))
        jumps = [f for f in cut["findings"] if f["kind"] == "jump_cut" and f["detail"]["jump"] == "reframe"]
        self.assertEqual(len(jumps), 1)
        self.assertAlmostEqual(jumps[0]["t_start"], 208 / 30, places=2)

    def test_every_finding_has_its_annotated_image_and_record(self) -> None:
        schema = pack_nouns("findings-to-fixes")["template.finding"]["schema"]
        for cut in self.cv["cuts"]:
            for f in cut["findings"]:
                path = self.tmp / "cv" / f["image_path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), f["image_sha256"], f["id"])
                if f["severity"] == "note":
                    self.assertIsNone(f["record"])
                else:
                    self.assertEqual(build_packs.schema_errors(schema, f["record"]), [], f["id"])
                    self.assertEqual(f["record"]["severity"], {"blocker": "P1", "major": "P2", "minor": "P3"}[f["severity"]])
        report = (self.tmp / "cv" / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("## Counts per detector", report)
        self.assertIn("Not reviewed yet", report)
        self.assertTrue((self.tmp / "cv" / "timeline-layout.png").is_file())

    def test_findings_match_the_packs_findings_schema(self) -> None:
        schema = pack_nouns("frame-by-frame-video-qa")["template.findings"]["schema"]
        self.assertEqual(build_packs.schema_errors(schema, self.cv), [])

    def test_two_runs_from_fresh_measurements_are_byte_identical(self) -> None:
        again = self.tmp / "cv-again"
        run_film(self._pairs(), again, engine="cv", workers=1, noticed_at=NOTICED, log=lambda m: None)
        self.assertEqual((self.tmp / "cv" / "findings.json").read_bytes(), (again / "findings.json").read_bytes())
        for label in ("layout", "time"):
            with gzip.open(self.tmp / "cv" / "cache" / label / "frames.jsonl.gz", "rb") as a, \
                    gzip.open(again / "cache" / label / "frames.jsonl.gz", "rb") as b:
                self.assertEqual(a.read(), b.read(), label)

    def test_layout_findings_with_the_text_detector_model(self) -> None:
        if not ocr_available():
            if os.environ.get("FRAME_QA_REQUIRE_OCR") == "1":
                self.fail("rapidocr-onnxruntime is required but not installed")
            self.skipTest("rapidocr-onnxruntime is not installed")
        doc = run_film([(self.clips["layout"], self.clips["layout_vtt"])], self.tmp / "ocr", engine="ocr", workers=2,
                       noticed_at=NOTICED, log=lambda m: None)
        rows = found(doc, "layout")
        self.assertFalse([r for r in rows if r[2] < 0.95 and r[1] != "note"], "the clean opening second has no problems")
        self.assertTrue(has(rows, "text_at_edge", 1.0, 2.0, "major"))
        self.assertTrue(has(rows, "text_in_action_margin", 2.0, 3.0))
        self.assertTrue(has(rows, "under_24_px", 3.0, 4.0))
        self.assertTrue(has(rows, "under_caption_box", 6.0, 7.0, "major"))
        self.assertTrue(has(rows, "panel_at_edge", 7.0, 8.0))
        edge = next(f for f in doc["cuts"][0]["findings"] if f["kind"] == "text_at_edge")
        self.assertTrue(any(t.startswith("EDGE TEXT") for t in edge["text"]), edge["text"])
        record = json.loads((self.tmp / "ocr" / "findings.json").read_text(encoding="utf-8"))
        self.assertEqual(record["cuts"][0]["engine"]["engine"], "ocr")


if __name__ == "__main__":
    unittest.main()
