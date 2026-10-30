"""The command line on the worked example, in a temporary folder; it refuses to write inside the library."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from explainer_checks.__main__ import library_root, main

PACKS = Path(__file__).resolve().parents[3]


def instance(pack: str, slug: str) -> dict:
    source = json.loads((PACKS / pack / "source.json").read_text(encoding="utf-8"))
    return next(n for n in source["nouns"] if n["slug"] == slug)["value"]["instance"]


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


class CommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.plan = self.dir / "plan.json"
        self.track = self.dir / "track.json"
        self.plan.write_text(json.dumps(instance("narrated-explainer-video", "example.cut-plan")), encoding="utf-8")
        self.track.write_text(json.dumps(instance("voice-narration", "example.narration-track")), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_clock_reports_spans_and_no_problem(self) -> None:
        code, out = run("clock", "--cut-plan", str(self.plan), "--cut", "20s", "--track", str(self.track))
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["problems"], [])
        self.assertEqual(len(result["clips"]), 4)

    def test_captions_write_the_example_sidecars(self) -> None:
        code, _ = run("captions", "--cut-plan", str(self.plan), "--cut", "20s", "--track", str(self.track),
                      "--out", str(self.dir / "out"))
        self.assertEqual(code, 0)
        expected = instance("narrated-explainer-video", "example.caption-cues")
        self.assertEqual((self.dir / "out" / "captions-20s.vtt").read_text(encoding="utf-8"), expected["webvtt"]["text"])
        record = json.loads((self.dir / "out" / "captions-20s.json").read_text(encoding="utf-8"))
        self.assertEqual(record["cues"], expected["cues"])
        self.assertEqual(record["srt"]["sha256"], expected["srt"]["sha256"])

    def test_manifest_then_verify_then_tamper(self) -> None:
        (self.dir / "a.vtt").write_text("WEBVTT\n", encoding="utf-8")
        manifest = self.dir / "manifest.json"
        code, _ = run("manifest", "--root", str(self.dir), "--cut", "20s", "--title", "t", "--out", str(manifest),
                      "--entry", "a.vtt", "webvtt", "text/vtt", "--disclosure", "AI-generated voice.")
        self.assertEqual(code, 0)
        self.assertIs(json.loads(manifest.read_text(encoding="utf-8"))["released"], False)
        self.assertEqual(run("verify", "--manifest", str(manifest), "--root", str(self.dir))[0], 0)
        (self.dir / "a.vtt").write_text("WEBVTT\n\nchanged\n", encoding="utf-8")
        self.assertEqual(run("verify", "--manifest", str(manifest), "--root", str(self.dir))[0], 1)

    def test_ledger_names_missing_steps(self) -> None:
        ledger = self.dir / "ledger.json"
        ledger.write_text(json.dumps({"steps": [{"step": "plan-cut", "ready_outcome": "cut_planned",
                                                 "outcome": "cut_planned", "receipt": "c" * 64}],
                                      "every_step_has_receipt": True}), encoding="utf-8")
        self.assertEqual(run("ledger", "--ledger", str(ledger))[0], 0)
        code, out = run("ledger", "--ledger", str(ledger), "--steps", "plan-cut,render")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["problems"], ["render: no receipt"])

    def test_writing_inside_the_library_is_refused(self) -> None:
        root = library_root()
        self.assertIsNotNone(root)
        target = root / "packs" / "narrated-explainer-video" / "code" / "out"
        with self.assertRaises(SystemExit):
            run("captions", "--cut-plan", str(self.plan), "--cut", "20s", "--track", str(self.track),
                "--out", str(target))
        self.assertFalse(target.exists())

    def test_an_unknown_cut_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            run("clock", "--cut-plan", str(self.plan), "--cut", "90s")


if __name__ == "__main__":
    unittest.main()
