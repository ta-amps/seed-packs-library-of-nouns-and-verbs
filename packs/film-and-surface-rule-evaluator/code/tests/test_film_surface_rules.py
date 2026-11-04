"""Unit tests and mechanical AST gate checks for film_surface_rules."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from film_surface_rules import (
    ZeroHardcodedValuesAstGate,
    evaluate_declarative_rule_nouns,
    load_default_grid_cell,
    rewrite_dead_repo_links_to_source_mirror,
    run_worked_example,
    scan_forbidden_stamps_and_chips,
    score_caption_plate_and_cognitive_load,
    verify_llms_txt_and_mcp_parity,
)


class FilmSurfaceRulesTests(unittest.TestCase):
    def test_package_itself_passes_zero_hardcoded_values_ast_gate(self) -> None:
        pkg_dir = Path(__file__).resolve().parents[1] / "film_surface_rules"
        py_files = sorted(pkg_dir.glob("*.py"))
        self.assertGreaterEqual(len(py_files), 4)
        res = ZeroHardcodedValuesAstGate.scan_paths(py_files)
        self.assertTrue(res["passed"], f"AST magic literal violations: {res['violations']}")

    def test_all_eight_rule_operators_and_unknown_honesty(self) -> None:
        rules = [
            {"id": "audio-clipping", "metric": "audio.true_peak_dbtp", "op": "<", "threshold": 0.0, "severity": "block", "hook": ["post"]},
            {"id": "audio-silence", "metric": "audio.max_silence_s", "op": "<=", "threshold": 2.0, "severity": "warn", "hook": ["post"]},
            {"id": "audio-music-bed", "metric": "audio.speech_over_bed_lu", "op": ">=", "threshold": 8.0, "severity": "warn", "hook": ["post"]},
            {"id": "cap-center-x", "metric": "caption.center_offset_px", "op": "abs<=", "threshold": 2, "severity": "block", "hook": ["post"]},
            {"id": "audio-loudness", "metric": "audio.integrated_lufs", "op": "in_range", "threshold": [-18, -13], "severity": "warn", "hook": ["post"]},
            {"id": "forbid-stamps", "metric": "ocr.forbidden_hits", "op": "empty", "threshold": None, "severity": "block", "hook": ["post"]},
            {"id": "auth-address-bar", "metric": "browser.address_bar_visible", "op": "is_true", "threshold": None, "severity": "block", "hook": ["post"]},
            {"id": "cap-gap-flicker", "metric": "caption.gap_flicker", "op": "is_false", "threshold": None, "severity": "warn", "hook": ["post"]},
            {"id": "design-note", "metric": None, "op": None, "threshold": None, "severity": "info", "hook": ["pre"]},
        ]
        measurements = {
            "audio": {
                "true_peak_dbtp": -1.2,
                "max_silence_s": 1.4,
                "speech_over_bed_lu": 10.5,
                "integrated_lufs": -15.8,
            },
            "caption": {"center_offset_px": -1.5, "gap_flicker": False},
            "ocr": {"forbidden_hits": []},
            "browser": {"address_bar_visible": True},
        }
        res = evaluate_declarative_rule_nouns(rules, measurements, hook_stage="post")
        self.assertEqual(res["verdict"], "pass")
        self.assertEqual(res["passed_count"], 8)

        # Missing measurement returns 'unknown', never fabricated zero
        partial = dict(measurements)
        partial["browser"] = {"address_bar_visible": None}
        res_unknown = evaluate_declarative_rule_nouns(rules, partial, hook_stage="post")
        self.assertEqual(res_unknown["verdict"], "unknown")
        self.assertEqual(res_unknown["unknown_count"], 1)

    def test_forbidden_stamps_captions_mirror_rewrite_and_mcp_parity(self) -> None:
        cell = load_default_grid_cell()
        dirty = scan_forbidden_stamps_and_chips(
            [{"t_s": 12.5, "text": "MADE-UP EXAMPLE - typed into the live box"}, {"t_s": 40.0, "text": "AI-generated voice"}],
            ["building", "live"],
            cell,
        )
        self.assertFalse(dirty["clean"])
        self.assertEqual(len(dirty["stamp_hits"]), 2)
        self.assertEqual(dirty["chip_hits"], ["building"])

        # Competing dual-channel cognitive load fails when rapid caption + unrelated rapid OST collide
        bad_load = score_caption_plate_and_cognitive_load(
            [{"start_s": 0.0, "end_s": 2.0, "text": "Workers claim tasks over standard streamable HTTP transport.", "plate_center_x_px": 960.0}],
            [{"start_s": 0.0, "end_s": 2.0, "text": "Quarterly municipal shelter budget allocation breakdown table"}],
            cell,
        )
        self.assertFalse(bad_load["passed"])
        self.assertEqual(bad_load["competing_attention_collisions"], 1)

        # Dead repo link rewrite to /source/ mirror + live intake door for /issues/new
        manifest = {
            "repositories": [
                {
                    "slug": "seed-packs",
                    "repo_name": "seed-packs-library-of-nouns-and-verbs",
                    "archive": "seed-packs-library-of-nouns-and-verbs.tar.gz",
                    "readme": "seed-packs-README.md",
                    "commit": "cdb6aa2fdee9e79cd183672a03e8f4006d49d89b",
                    "tar_sha256": "548ef1209ab8c45678901234567890abcdef1234567890abcdef1234567890ab",
                },
                {
                    "slug": "public-marketplace",
                    "repo_name": "public-good-marketplace",
                    "archive": "public-good-marketplace.tar.gz",
                    "readme": "public-marketplace-README.md",
                    "commit": "4f11d90aa11bb22cc33dd44ee55ff6677889900a",
                    "tar_sha256": "99887766554433221100ffeeddccbbaa99887766554433221100ffeeddccbbaa",
                },
            ]
        }
        rw = rewrite_dead_repo_links_to_source_mirror(
            [
                "https://repo.invalid/org",
                "https://repo.invalid/org/seed-packs-library-of-nouns-and-verbs/tree/main/packs/checks-of-checks",
                "https://repo.invalid/org/public-good-marketplace/issues/new?template=request.yml",
            ],
            manifest,
            grid_cell=cell,
        )
        self.assertTrue(rw["all_resolved"])
        self.assertEqual(rw["rewritten"][0]["mirror_url"], "/source/")
        self.assertEqual(
            rw["rewritten"][1]["mirror_url"],
            "/source/#seed-packs:packs/checks-of-checks@cdb6aa2fdee9",
        )
        self.assertEqual(rw["rewritten"][2]["mirror_url"], "/nonprofits")

        # llms.txt vs MCP tools/list parity + simulated fallback rejection
        llms = "# Service\nExposes 3 tools total:\n- `claim`\n- `complete`\n- `put_record`\n"
        parity_ok = verify_llms_txt_and_mcp_parity(llms, ["claim", "complete", "put_record"], has_simulated_fallback=False)
        self.assertTrue(parity_ok["passed"])
        parity_sim = verify_llms_txt_and_mcp_parity(llms, ["claim", "complete", "put_record"], has_simulated_fallback=True)
        self.assertFalse(parity_sim["passed"])

    def test_worked_example_recomputes_exact_receipt(self) -> None:
        src_path = Path(__file__).resolve().parents[2] / "source.json"
        if not src_path.exists():
            self.skipTest("source.json not yet written")
        src = json.loads(src_path.read_text(encoding="utf-8"))
        bundle = next(n["value"]["bundle"] for n in src["nouns"] if n["slug"] == "example.film-surface-rules-bundle")
        expected = next(n["value"]["instance"] for n in src["nouns"] if n["slug"] == "example.film-surface-rules-receipt")
        actual = run_worked_example(bundle, load_default_grid_cell())
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
