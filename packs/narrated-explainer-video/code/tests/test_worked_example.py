"""Recompute this pack's worked example from the pack sources, and keep the caption numbers tied to the style guide."""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from explainer_checks.captions import (MAX_CPS, MAX_CUE_MS, MAX_LINE, MAX_LINES, MIN_CUE_MS, build_cues, check_cues,
                                       to_srt, to_webvtt)
from explainer_checks.clock import beat_spans, check_cut, check_narration, frame_sheet_times
from explainer_checks.release import file_entry

PACKS = Path(__file__).resolve().parents[3]


def nouns(pack: str) -> dict[str, dict]:
    source = json.loads((PACKS / pack / "source.json").read_text(encoding="utf-8"))
    return {noun["slug"]: noun["value"] for noun in source["nouns"]}


OWN = nouns("narrated-explainer-video")
VOICE = nouns("voice-narration")
SHOWCASE = nouns("video-showcase")
PLAN = OWN["example.cut-plan"]["instance"]
CUT = PLAN["cuts"][0]
TRACK = VOICE["example.narration-track"]["instance"]
CUES = OWN["example.caption-cues"]["instance"]


class WorkedExample(unittest.TestCase):
    def test_the_cut_plan_has_a_clean_clock(self) -> None:
        self.assertEqual(check_cut(CUT, PLAN["fps"], {b["beat_id"] for b in PLAN["beats"]}), [])
        computed = OWN["example.cut-plan"]["computed"]
        self.assertEqual([[b["beat_id"], b["start_ms"], b["end_ms"]] for b in beat_spans(CUT, PLAN["fps"])],
                         computed["beats_ms"])
        self.assertEqual([[t["clip_id"], t["time_ms"]] for t in frame_sheet_times(CUT, PLAN["fps"])],
                         computed["sheet_times_ms"])

    def test_the_voice_packs_placed_lines_fit_this_cut(self) -> None:
        self.assertEqual(TRACK["cut_id"], CUT["cut_id"])
        self.assertEqual(TRACK["duration_s"], CUT["duration_s"])
        self.assertEqual(check_narration(CUT, PLAN["fps"], TRACK["placements"]), [])

    def test_the_cues_are_recomputed_exactly(self) -> None:
        cues = build_cues(TRACK["placements"], CUT["duration_s"], PLAN["fps"])
        self.assertEqual(cues, CUES["cues"])
        self.assertEqual(check_cues(cues, PLAN["fps"]), [])
        self.assertEqual(CUES["rule_problems"], [])
        self.assertEqual(" ".join(c["text"] for c in cues), " ".join(p["text"] for p in TRACK["placements"]))

    def test_the_sidecars_and_their_digests_are_recomputed_exactly(self) -> None:
        vtt, srt = to_webvtt(CUES["cues"], PLAN["fps"]), to_srt(CUES["cues"], PLAN["fps"])
        self.assertEqual(CUES["webvtt"]["text"], vtt)
        self.assertEqual(CUES["srt"]["text"], srt)
        self.assertEqual({k: v for k, v in CUES["webvtt"].items() if k != "text"},
                         file_entry("captions-20s.vtt", vtt.encode("utf-8"), "webvtt", "text/vtt"))
        self.assertEqual({k: v for k, v in CUES["srt"].items() if k != "text"},
                         file_entry("captions-20s.srt", srt.encode("utf-8"), "srt", "application/x-subrip"))

    def test_the_release_manifest_digests_are_real(self) -> None:
        manifest = OWN["example.release-manifest"]["instance"]
        plan_bytes = (json.dumps(PLAN, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
        files = {f["path"]: f for f in manifest["files"]}
        self.assertEqual(files["cut-plan-20s.json"]["sha256"], hashlib.sha256(plan_bytes).hexdigest())
        self.assertEqual(files["captions-20s.vtt"]["sha256"], CUES["webvtt"]["sha256"])
        self.assertEqual(files["captions-20s.srt"]["sha256"], CUES["srt"]["sha256"])
        self.assertIs(manifest["released"], False)

    def test_the_example_shows_each_timing_rule(self) -> None:
        cues = CUES["cues"]
        self.assertEqual(len(cues), 4)
        self.assertEqual(cues[0]["end_frame"], 131, "the sentence split snaps to the sentence pause, not the comma")
        self.assertEqual(cues[2]["end_frame"], cues[3]["start_frame"], "a 2-frame gap is closed")
        self.assertEqual(len(cues[3]["lines"]), 2)

    def test_caption_numbers_match_the_video_showcase_style_guide(self) -> None:
        rules = " ".join(SHOWCASE["style-guide"]["caption_rules"])
        self.assertIn(f"At most {MAX_LINES} lines per cue and {MAX_LINE} characters per line", rules)
        self.assertIn(f"{MIN_CUE_MS // 1000} to {MAX_CUE_MS // 1000} seconds", rules)
        self.assertIn(f"At most {MAX_CPS} characters per second", rules)

    def test_the_tool_card_names_this_code(self) -> None:
        card = OWN["tool.explainer-checks"]
        self.assertEqual(card["code"], {"$code": "narrated-explainer-video"})
        for command in card["commands"]:
            self.assertTrue(re.match(r"python -m explainer_checks (clock|captions|manifest|verify|ledger) ", command))


if __name__ == "__main__":
    unittest.main()
