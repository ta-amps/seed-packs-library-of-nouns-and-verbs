"""Recompute this pack's worked example from the pack source, and keep its numbers tied to the code."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from video_qa_checks import captions, checks, layout, report, rows

PACKS = Path(__file__).resolve().parents[3]


def nouns(pack: str) -> dict[str, dict]:
    source = json.loads((PACKS / pack / "source.json").read_text(encoding="utf-8"))
    return {noun["slug"]: noun["value"] for noun in source["nouns"]}


OWN = nouns("video-qa")
SHOWCASE = nouns("video-showcase")
MOTION = nouns("video-motion")
INPUTS = OWN["example.qa-inputs"]
PLAN = OWN["example.qa-plan"]["instance"]
REPORT = OWN["example.extended-qa-report"]["instance"]


def recompute() -> list[dict]:
    ymin = [(t, lo) for t, lo, _ in INPUTS["luma_range"]]
    ymax = [(t, hi) for t, _, hi in INPUTS["luma_range"]]
    scores = [(t, s) for t, s in INPUTS["scene_scores"]]
    return [rows.captions_row(INPUTS["vtt"], INPUTS["srt"], INPUTS["speech_ms"], None, round(PLAN["duration_s"] * 1000)),
            *rows.picture_rows(PLAN, INPUTS["picture_log"], ymin, ymax, scores),
            *rows.sound_rows(PLAN, INPUTS["sound_log"], INPUTS["silence_log"], INPUTS["astats_log"], {"target_lufs": -16.0}),
            rows.filespec_row(INPUTS["mp4_facts"], INPUTS["export_spec"]), rows.legibility_row(INPUTS["text_items"])]


class WorkedExample(unittest.TestCase):
    def test_the_report_is_recomputed_exactly(self) -> None:
        computed = report.compile_report(REPORT["media"], PLAN, recompute(), REPORT["inputs"])
        self.assertEqual(json.loads(json.dumps(computed)), REPORT)

    def test_the_example_shows_each_kind_of_finding(self) -> None:
        results = {row["check"]: row["result"] for row in REPORT["checks"]}
        self.assertEqual(REPORT["verdict"], "fail")
        self.assertEqual(results["clipping"], "pass")
        self.assertEqual({results[k] for k in ("captions", "blank_frames", "file_spec", "legibility")}, {"fail"})
        self.assertEqual({results[k] for k in ("frozen_stretches", "cut_cadence", "loudness", "silence_gaps")}, {"warn"})
        held = [r for r in REPORT["checks"] if r["check"] == "frozen_stretches"][0]["findings"]
        self.assertEqual([f["start_s"] for f in held], [1.0], "the freeze inside the end-card hold is not reported")

    def test_caption_limits_match_the_video_showcase_style_guide(self) -> None:
        rules = " ".join(SHOWCASE["style-guide"]["caption_rules"])
        lim = captions.DEFAULT_LIMITS
        self.assertIn(f"At most {lim['max_lines']} lines per cue and {lim['max_chars_per_line']} characters per line", rules)
        self.assertIn(f"{lim['min_cue_ms'] // 1000} to {lim['max_cue_ms'] // 1000} seconds", rules)
        self.assertIn(f"At most {int(lim['max_cps'])} characters per second", rules)

    def test_keep_outs_match_the_video_and_motion_aspect_rules(self) -> None:
        reels = MOTION["rules.aspects"]["tool_facts"]["aspects"]["reels_9x16"]
        keep = {k["label"]: k for k in INPUTS["text_items"]["keep_outs"]}
        for zone in reels["ui_keep_outs"]:
            self.assertEqual({k: keep[zone["label"]][k] for k in ("x", "y", "width", "height")},
                             {k: zone[k] for k in ("x", "y", "width", "height")})
        self.assertEqual(INPUTS["text_items"]["safe"], {k: reels["safe_canvas"][k] for k in ("x", "y", "width", "height")})

    def test_the_check_list_names_every_required_check_and_default(self) -> None:
        listed = {c["id"]: c["threshold"] for c in OWN["checks.extended"]["checks"]}
        self.assertEqual(set(listed), set(report.REQUIRED))
        self.assertEqual(OWN["checks.extended"]["required"], list(report.REQUIRED))
        self.assertIn(f"{checks.DEFAULTS['freeze_warn_s']} s warns, {checks.DEFAULTS['freeze_fail_s']} s fails", listed["frozen_stretches"])
        self.assertIn(f"{checks.DEFAULTS['still_warn_s']:g} s or more", listed["cut_cadence"])
        self.assertIn(f"{checks.DEFAULTS['short_term_floor_lufs']:g} LUFS", listed["loudness"])
        floors = ", ".join(f"{role.replace('_', ' ')} {share * 100:g}%" for role, share in layout.ROLE_FLOORS.items())
        self.assertIn(floors, listed["legibility"])
        self.assertIn(f"{layout.DEFAULT_MIN_CSS_PX:g} CSS px", listed["legibility"])

    def test_the_tool_card_names_this_code(self) -> None:
        card = OWN["tool.video-qa-checks"]
        self.assertEqual(card["code"], {"$code": "video-qa"})
        for command in card["commands"]:
            self.assertTrue(re.match(r"python -m video_qa_checks (captions|picture|sound|filespec|legibility|report) ", command))


if __name__ == "__main__":
    unittest.main()
