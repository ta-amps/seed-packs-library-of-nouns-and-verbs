"""The pack's nouns agree with this code: the detector spec, the questions, the tool card's commands, the findings
schema, the review rules and the worked example, which the code recomputes from the pack source."""

from __future__ import annotations

import json
import re
import sys
import unittest

from frame_qa.cluster import cluster_hits
from frame_qa.detectors import DETECTOR_FUNCTIONS, Context, run_all, shots
from frame_qa.report import QUESTION, build_findings
from frame_qa.review import draw_sample, precision
from frame_qa.spec import DEFAULT_SPEC, DETECTORS, PRIORITY

from helpers import PACKS, pack_nouns

sys.path.insert(0, str(PACKS.parent / "scripts"))
import build_packs  # noqa: E402

OWN = pack_nouns("frame-by-frame-video-qa")


def example_context() -> tuple[Context, dict]:
    import numpy as np

    example = OWN["example.measurements"]
    n = example["frames"]
    T = {k: np.array(v, float) for k, v in example["temporal"].items()}
    T["small"] = np.zeros((n, 9, 16), np.uint8)
    records = {r["i"]: r for r in example["records"]}
    full = [records.get(i, {"i": i, "edges": [0.02, 0.03, 0.04], "grad_p999": 40.0, "border": example["quiet_border"]}) for i in range(n)]
    ctx = Context(example["width"], example["height"], example["fps"], n, DEFAULT_SPEC, T, full, [])
    return ctx, example


class PackAgreesWithCode(unittest.TestCase):
    def test_the_spec_noun_is_the_codes_default_spec(self) -> None:
        self.assertEqual(OWN["spec.detectors"]["spec"], json.loads(json.dumps(DEFAULT_SPEC)))

    def test_every_detector_has_its_questions_and_severities(self) -> None:
        for name in DETECTORS:
            spec = DEFAULT_SPEC["detectors"][name]
            self.assertGreaterEqual(len(spec["questions"]), 2, name)
            self.assertTrue(all(q.endswith("?") for q in spec["questions"]), name)
            self.assertTrue(spec["severity"], name)
        for (detector, kind), index in QUESTION.items():
            self.assertLess(index, len(DEFAULT_SPEC["detectors"][detector]["questions"]), (detector, kind))
        self.assertEqual(set(DETECTOR_FUNCTIONS), set(DETECTORS))
        series = OWN["questions"]["series"]
        self.assertEqual([s["detector"] for s in series], list(DETECTORS))
        for row in series:
            self.assertEqual(row["questions"], DEFAULT_SPEC["detectors"][row["detector"]]["questions"])

    def test_severities_map_onto_findings_to_fixes_like_the_video_review_guide(self) -> None:
        guide = pack_nouns("video-review")["severity-guide"]["levels"]
        for level, priority in PRIORITY.items():
            self.assertIn(priority or "none", guide[level]["findings_to_fixes"])

    def test_safe_areas_match_the_rules_noun(self) -> None:
        rules = OWN["rules.safe-areas"]
        self.assertEqual(rules["title_safe_share"], DEFAULT_SPEC["safe_areas"]["title_safe_share"])
        self.assertEqual(rules["action_safe_share"], DEFAULT_SPEC["safe_areas"]["action_safe_share"])
        self.assertEqual(rules["caption_band_share"], DEFAULT_SPEC["detectors"]["caption_collisions"]["thresholds"]["band_share"])
        self.assertEqual(rules["phone_width_px"], DEFAULT_SPEC["detectors"]["small_text"]["thresholds"]["phone_width_px"])

    def test_the_tool_card_names_this_code_and_its_commands(self) -> None:
        card = OWN["tool.frame-qa"]
        self.assertEqual(card["code"], {"$code": "frame-by-frame-video-qa"})
        for command in card["commands"]:
            self.assertTrue(re.match(r"python -m frame_qa (film|run|sample|detect|cluster|review-sample|precision|spec|synth) ", command + " "), command)

    def test_the_findings_schema_is_a_library_schema(self) -> None:
        schema = OWN["template.findings"]["schema"]
        build_packs.check_schema(schema, "template.findings")
        finding = schema["properties"]["cuts"]["items"]["properties"]["findings"]["items"]
        self.assertEqual(set(finding["properties"]["detector"]["enum"]), set(DETECTORS))
        self.assertEqual(finding["properties"]["severity"]["enum"], ["blocker", "major", "minor", "note"])

    def test_the_review_template_counts_precision_like_the_code(self) -> None:
        schema = OWN["template.review-labels"]["schema"]
        example = OWN["example.review-labels"]["instance"]
        self.assertEqual(build_packs.schema_errors(schema, example), [])
        self.assertEqual(json.loads(json.dumps(precision(example["rows"]))), OWN["example.review-labels"]["precision"])

    def test_the_worked_example_is_recomputed_exactly(self) -> None:
        ctx, example = example_context()
        hits = run_all(ctx)
        clusters = cluster_hits(hits, DEFAULT_SPEC, ctx.fps)
        findings = build_findings(clusters, "demo", ctx.fps, ctx.width, ctx.height, ctx.frames, shots(ctx), [], "demo.mp4", "2026-10-30")
        computed = [{k: f[k] for k in ("id", "detector", "kind", "severity", "t_start", "t_end", "summary")} for f in findings]
        self.assertEqual(computed, OWN["example.findings"]["findings"])
        rows = draw_sample(findings, 3, 1)
        self.assertEqual([r["id"] for r in rows], OWN["example.findings"]["sample_ids"])


if __name__ == "__main__":
    unittest.main()
