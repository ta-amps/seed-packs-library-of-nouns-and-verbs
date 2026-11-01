"""Unit tests for velocity_signal_radar: NodeGrid, wall-scrape refusal, SimHash dedup, hype filter and AST/naming gates."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import velocity_signal_radar as vsr
from velocity_signal_radar import (
    CuratorLensProfile,
    DomainAgnosticNamingGate,
    GridLedger,
    NodeGrid,
    OperationCostLedger,
    ParameterBounds,
    ZeroHardcodedValuesAstGate,
    canonicalize_repository_key,
    compute_shingle_simhash64,
    emit_bounded_verb_proposals,
    evaluate_radar_bundle,
    extract_quickstart_commands,
    match_capability_facets,
    match_curator_lenses,
    normalize_and_coalesce_signals,
    score_breakout_dossier,
    simhash_hamming_distance,
    validate_sanctioned_source_url,
)
from velocity_signal_radar.__main__ import main as cli_main

CODE_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = CODE_ROOT.parent


class VelocitySignalRadarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = NodeGrid()

    def test_01_grid_spec_loads_and_enumerates_constraints(self) -> None:
        cells = self.grid.enumerate_cells()
        self.assertGreater(len(cells["represented"]), len(cells["applicable"]))
        self.assertGreater(len(cells["applicable"]), 10)
        for cell in cells["applicable"]:
            if cell["radar_regime"] == "strict_substance_audit":
                self.assertTrue(cell["require_permissive_license"])
                self.assertGreaterEqual(cell["min_breakout_score_milli"], 650)

    def test_02_parameter_bounds_clamping_across_all_types(self) -> None:
        ib = ParameterBounds(param_type="integer_range", low=7, high=45, step=7)
        self.assertEqual(ib.clamp(2), 7)
        self.assertEqual(ib.clamp(99), 42)
        fb = ParameterBounds(param_type="float_range", low=0.1, high=0.9, step=0.2, float_round_digits=2)
        self.assertEqual(fb.clamp(-1.0), 0.1)
        self.assertEqual(fb.clamp(5.0), 0.9)
        cb = ParameterBounds(param_type="choice", choices=("alpha", "beta"))
        self.assertEqual(cb.clamp("unknown"), "alpha")
        bb = ParameterBounds(param_type="boolean")
        self.assertIs(bb.clamp(1), True)
        self.assertIs(bb.clamp(0), False)

    def test_03_boundary_auto_expansion_on_upper_and_lower_saturation(self) -> None:
        expanded_hi, axes_hi = self.grid.auto_expand_if_saturated({"lookback_window_days": 45})
        self.assertEqual(expanded_hi.generation, self.grid.generation + 1)
        self.assertIn("lookback_window_days:high->90", axes_hi)

        expanded_lo, axes_lo = self.grid.auto_expand_if_saturated({"simhash_hamming_dedup_max": 2})
        self.assertEqual(expanded_lo.generation, self.grid.generation + 1)
        self.assertIn("simhash_hamming_dedup_max:low->1", axes_lo)

    def test_04_grid_ledger_monotonic_lifecycle_and_distinct_verifier_gate(self) -> None:
        ledger = GridLedger(self.grid)
        cell = self.grid.clamp_cell({})
        self.assertTrue(ledger.transition(cell, "proposed", worker_id="w_prop", key_id="k_prop")["ok"])
        self.assertFalse(ledger.transition(cell, "verified", worker_id="w_ver", key_id="k_ver")["ok"])
        self.assertTrue(ledger.transition(cell, "dispatched")["ok"])
        self.assertTrue(ledger.transition(cell, "evaluated", metrics={"precision": 0.94})["ok"])
        same_principal = ledger.transition(cell, "verified", worker_id="w_prop", key_id="k_other")
        self.assertFalse(same_principal["ok"])
        self.assertEqual(same_principal["reason"], "distinct_verifier_required")
        distinct_principal = ledger.transition(cell, "verified", worker_id="w_ver", key_id="k_ver")
        self.assertTrue(distinct_principal["ok"])
        self.assertTrue(ledger.transition(cell, "promoted")["ok"])

    def test_05_operation_cost_ledger_contextual_regime_resolution(self) -> None:
        ledger = GridLedger(self.grid)
        cost_ledger = OperationCostLedger(self.grid, ledger)
        default_res = cost_ledger.resolve_for_regime("rapid_velocity_triage")
        self.assertEqual(default_res["source"], "regime_default")

        custom_cell = self.grid.clamp_cell({
            "radar_regime": "rapid_velocity_triage",
            "lookback_window_days": 21,
            "min_breakout_score_milli": 550,
        })
        for st, wid, kid in [
            ("proposed", "w_a", "k_a"),
            ("dispatched", "", ""),
            ("evaluated", "", ""),
            ("verified", "w_b", "k_b"),
        ]:
            self.assertTrue(ledger.transition(custom_cell, st, worker_id=wid, key_id=kid)["ok"])
        cost_ledger.record_observation(
            regime="rapid_velocity_triage",
            cell=custom_cell,
            quality_score=0.91,
            cost_units=1.4,
        )
        verified_res = cost_ledger.resolve_for_regime("rapid_velocity_triage", min_quality=0.85)
        self.assertEqual(verified_res["source"], "verified_ledger_optimum")
        self.assertEqual(verified_res["cell"]["lookback_window_days"], 21)

    def test_06_sanctioned_public_source_urls_accepted(self) -> None:
        for url in (
            "https://api.github.com/search/repositories?q=created:%3E2026-10-02",
            "https://github.com/synth-forge/mcp-preflight-guard",
            "https://hn.algolia.com/api/v1/search_by_date?query=github.com",
            "https://huggingface.co/api/daily_papers",
        ):
            host = validate_sanctioned_source_url(url, self.grid)
            self.assertTrue(host)

    def test_07_login_gated_social_walls_fail_closed_across_all_curator_urls(self) -> None:
        prohibited_urls = [
            "https://www.facebook.com/PHfreecoder",
            "https://www.facebook.com/profile.php?id=61557569443676",
            "https://www.facebook.com/profile.php?id=61590627770961",
            "https://www.facebook.com/profile.php?id=61590350949771",
            "https://www.facebook.com/chriiske",
            "https://www.facebook.com/fusin.automation/",
            "https://www.facebook.com/profile.php?id=61595079431278",
            "https://m.facebook.com/PHfreecoder",
            "https://www.instagram.com/some_account",
            "http://api.github.com/search/repositories",
        ]
        for url in prohibited_urls:
            with self.assertRaisesRegex(ValueError, "sanctioned_public_api_or_search_lens_only"):
                validate_sanctioned_source_url(url, self.grid)

    def test_08_curator_lens_profile_enforces_wall_scraping_prohibition(self) -> None:
        lens = CuratorLensProfile(
            lens_id="practical_dev_security_and_fullstack",
            reference_urls=("https://www.facebook.com/PHfreecoder",),
            keywords=("security", "checklist", "mcp"),
            authenticated_wall_scraping_prohibited=True,
        )
        lens.validate(self.grid)
        bad_lens = CuratorLensProfile(
            lens_id="bad_lens",
            reference_urls=("https://www.facebook.com/PHfreecoder",),
            keywords=("security",),
            authenticated_wall_scraping_prohibited=False,
        )
        with self.assertRaisesRegex(ValueError, "authenticated_wall_scraping_must_remain_prohibited"):
            bad_lens.validate(self.grid)

    def test_09_canonicalize_repository_key_normalizes_variants(self) -> None:
        key_a, url_a = canonicalize_repository_key("https://github.com/Synth-Forge/MCP-Preflight-Guard.git/")
        key_b, _ = canonicalize_repository_key("synth-forge/mcp-preflight-guard")
        self.assertEqual(key_a, "github:synth-forge/mcp-preflight-guard")
        self.assertEqual(key_a, key_b)
        self.assertEqual(url_a, "https://github.com/Synth-Forge/MCP-Preflight-Guard")

    def test_10_shingle_simhash64_and_lsh_bands_determinism(self) -> None:
        h1, bands1 = compute_shingle_simhash64(
            "Zero dependency Rust CLI MCP preflight security firewall for 4GB laptops",
            self.grid,
        )
        h2, bands2 = compute_shingle_simhash64(
            "Zero dependency Rust CLI MCP preflight security firewall for 4GB laptops!",
            self.grid,
        )
        h3, _ = compute_shingle_simhash64(
            "3D Gaussian splatting WebGL shader timeline renderer for interactive scenes",
            self.grid,
        )
        self.assertEqual(h1, h2)
        self.assertEqual(bands1, bands2)
        self.assertEqual(len(h1), 16)
        self.assertEqual(len(bands1), 4)
        self.assertEqual(simhash_hamming_distance(h1, h2, self.grid), 0)
        self.assertGreater(simhash_hamming_distance(h1, h3, self.grid), 10)

    def test_11_multi_source_coalescing_merges_github_hn_and_hf_sightings(self) -> None:
        res = normalize_and_coalesce_signals(
            [
                {
                    "signal_id": "s1",
                    "source_channel": "github_search_rest",
                    "source_url": "https://api.github.com/search/repositories",
                    "repository_url": "https://github.com/acme/fast-mcp",
                    "created_at_iso": "2026-10-20T00:00:00Z",
                    "stars": 410,
                    "forks": 32,
                    "hn_points": 0,
                    "hf_upvotes": 0,
                    "repo_size_kb": 290,
                    "spdx_license": "MIT",
                    "primary_language": "Rust",
                    "topics": ["mcp"],
                    "summary_text": "Fast MCP server",
                    "readme_excerpt": "`cargo install fast-mcp`",
                },
                {
                    "signal_id": "s2",
                    "source_channel": "hn_algolia_show_hn",
                    "source_url": "https://hn.algolia.com/api/v1/search_by_date",
                    "repository_url": "https://github.com/acme/fast-mcp.git",
                    "created_at_iso": "2026-10-20T00:00:00Z",
                    "stars": 430,
                    "forks": 35,
                    "hn_points": 175,
                    "hf_upvotes": 0,
                    "repo_size_kb": 290,
                    "spdx_license": "MIT",
                    "primary_language": "Rust",
                    "topics": ["cli"],
                    "summary_text": "Fast MCP server in Rust",
                    "readme_excerpt": "`cargo install fast-mcp`\n`npx fast-mcp --verify`",
                },
            ],
            self.grid,
            reference_utc_iso="2026-11-01T00:00:00Z",
        )
        self.assertEqual(len(res["coalesced"]), 1)
        merged = res["coalesced"][0]
        self.assertEqual(merged["stars"], 430)
        self.assertEqual(merged["hn_points"], 175)
        self.assertEqual(sorted(merged["channels"]), ["github_search_rest", "hn_algolia_show_hn"])

    def test_12_archive_cross_link_preserves_older_seed_candidates_without_duplication(self) -> None:
        res = normalize_and_coalesce_signals(
            [
                {
                    "signal_id": "s_arch",
                    "source_channel": "huggingface_daily_papers",
                    "source_url": "https://huggingface.co/api/daily_papers",
                    "repository_url": "https://github.com/firecrawl/anydoc",
                    "created_at_iso": "2026-08-15T00:00:00Z",
                    "stars": 1400,
                    "forks": 120,
                    "hn_points": 90,
                    "hf_upvotes": 75,
                    "repo_size_kb": 520,
                    "spdx_license": "MIT",
                    "primary_language": "Python",
                    "topics": ["ocr", "document"],
                    "summary_text": "Document layout parser",
                    "readme_excerpt": "`pip install anydoc`",
                }
            ],
            self.grid,
            reference_utc_iso="2026-11-01T00:00:00Z",
            known_archive_repos={"firecrawl/anydoc": "recent_public_source_experiment_seedpack_codex_20261101_v1"},
        )
        self.assertEqual(len(res["coalesced"]), 1)
        entry = res["coalesced"][0]
        self.assertTrue(entry["already_in_seed_archive"])
        self.assertEqual(entry["linked_archive_key"], "recent_public_source_experiment_seedpack_codex_20261101_v1")

    def test_13_hype_filter_penalizes_unlicensed_tiny_waitlist_repo(self) -> None:
        res = normalize_and_coalesce_signals(
            [
                {
                    "signal_id": "s_hype",
                    "source_channel": "github_search_rest",
                    "source_url": "https://api.github.com/search/repositories",
                    "repository_url": "https://github.com/hype-org/waitlist-shell",
                    "created_at_iso": "2026-10-30T00:00:00Z",
                    "stars": 2000,
                    "forks": 3,
                    "hn_points": 0,
                    "hf_upvotes": 0,
                    "repo_size_kb": 3,
                    "spdx_license": "NONE",
                    "primary_language": "Markdown",
                    "topics": ["ai"],
                    "summary_text": "Star to unlock coming soon waitlist 100x guaranteed",
                    "readme_excerpt": "Star this repo for early access!",
                }
            ],
            self.grid,
            reference_utc_iso="2026-11-01T00:00:00Z",
        )
        dossier = score_breakout_dossier(res["coalesced"][0], self.grid)
        self.assertGreaterEqual(dossier.hype_penalty_milli, 600)
        self.assertFalse(dossier.passes_breakout_gate)
        self.assertEqual(emit_bounded_verb_proposals(dossier, self.grid), [])

    def test_14_high_substance_repo_passes_breakout_gate_and_emits_bounded_proposals(self) -> None:
        res = normalize_and_coalesce_signals(
            [
                {
                    "signal_id": "s_good",
                    "source_channel": "github_search_rest",
                    "source_url": "https://api.github.com/search/repositories",
                    "repository_url": "https://github.com/open-tools/n8n-mcp-guard",
                    "created_at_iso": "2026-10-24T00:00:00Z",
                    "stars": 860,
                    "forks": 84,
                    "hn_points": 160,
                    "hf_upvotes": 48,
                    "repo_size_kb": 460,
                    "spdx_license": "Apache-2.0",
                    "primary_language": "Rust",
                    "topics": ["mcp", "n8n", "security", "workflow", "cli"],
                    "summary_text": "Self-hosted MCP security guardrail and n8n workflow companion in Rust.",
                    "readme_excerpt": "`cargo install n8n-mcp-guard`\n`docker run --rm n8n-mcp-guard --selftest`",
                }
            ],
            self.grid,
            reference_utc_iso="2026-11-01T00:00:00Z",
        )
        dossier = score_breakout_dossier(res["coalesced"][0], self.grid)
        self.assertTrue(dossier.passes_breakout_gate)
        self.assertEqual(dossier.hype_penalty_milli, 0)
        proposals = emit_bounded_verb_proposals(
            dossier,
            self.grid,
            parent_task_id="parent_01",
            source_task_id="root_00",
            generation_depth=1,
        )
        self.assertEqual(len(proposals), 4)
        for prop in proposals:
            self.assertFalse(prop.auto_enqueue_permitted)
            self.assertEqual(prop.generation_depth, 2)
            self.assertEqual(prop.parent_task_id, "parent_01")
            self.assertEqual(prop.source_task_id, "root_00")

    def test_15_strict_substance_regime_blocks_non_permissive_license(self) -> None:
        res = normalize_and_coalesce_signals(
            [
                {
                    "signal_id": "s_prop",
                    "source_channel": "github_search_rest",
                    "source_url": "https://api.github.com/search/repositories",
                    "repository_url": "https://github.com/open-tools/proprietary-agent",
                    "created_at_iso": "2026-10-25T00:00:00Z",
                    "stars": 1200,
                    "forks": 140,
                    "hn_points": 210,
                    "hf_upvotes": 80,
                    "repo_size_kb": 600,
                    "spdx_license": "BUSL-1.1",
                    "primary_language": "Python",
                    "topics": ["agent", "mcp"],
                    "summary_text": "Source-available agent router",
                    "readme_excerpt": "`pip install proprietary-agent`\n`python3 -m proprietary_agent --check`",
                }
            ],
            self.grid,
            reference_utc_iso="2026-11-01T00:00:00Z",
        )
        strict_cell = self.grid.regime_defaults["strict_substance_audit"]
        dossier = score_breakout_dossier(res["coalesced"][0], self.grid, active_cell=strict_cell)
        self.assertFalse(dossier.permissive_license)
        self.assertFalse(dossier.passes_breakout_gate)

    def test_16_quickstart_extraction_curator_lenses_and_capability_facets(self) -> None:
        readme = """
        # Interactive 3D Shader Map
        Install quickly:
        `uvx shader-geo-map --demo`
        `npx shader-geo-map serve`
        """
        cmds = extract_quickstart_commands(readme, self.grid)
        self.assertEqual(cmds, ("uvx shader-geo-map --demo", "npx shader-geo-map serve"))
        lenses = match_curator_lenses("3D WebGL geospatial interactive shader map", "", self.grid)
        self.assertIn("visual_geospatial_and_interactive_tooling", lenses)
        facets = match_capability_facets("3D WebGL geospatial shader CLI zero-dep", self.grid)
        self.assertIn("three_d_rendering_and_visual_motion", facets)
        self.assertIn("runs_on_small_4gb_laptop", facets)

    def test_17_worked_example_bundle_in_source_json_recomputes_byte_for_byte(self) -> None:
        source_path = PACK_ROOT / "source.json"
        self.assertTrue(source_path.exists(), f"missing {source_path}")
        source_doc = json.loads(source_path.read_text(encoding="utf-8"))
        nouns_by_slug = {n["slug"]: n for n in source_doc["nouns"]}
        bundle = nouns_by_slug["example.velocity-radar-bundle"]["value"]["bundle"]
        expected_receipt = nouns_by_slug["example.velocity-radar-receipt"]["value"]["instance"]
        recomputed = evaluate_radar_bundle(bundle, self.grid)
        self.assertEqual(recomputed, expected_receipt)

    def test_18_cli_self_test_and_bundle_entrypoints(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = cli_main(["--self-test"])
        self.assertEqual(rc, 0)
        parsed = json.loads(buf.getvalue())
        self.assertTrue(parsed["ast_passed"])
        self.assertTrue(parsed["naming_passed"])

        with tempfile.TemporaryDirectory() as tmpdir:
            bpath = Path(tmpdir) / "bundle.json"
            bpath.write_text(
                json.dumps({
                    "radar_regime": "balanced_breakout_radar",
                    "reference_utc_iso": "2026-11-01T00:00:00Z",
                    "signals": [],
                }),
                encoding="utf-8",
            )
            buf2 = io.StringIO()
            with patch("sys.stdout", buf2):
                rc2 = cli_main(["--bundle", str(bpath)])
            self.assertEqual(rc2, 0)
            self.assertIn("receipt_sha256", json.loads(buf2.getvalue()))

    def test_19_zero_hardcoded_values_ast_gate_passes_package_and_catches_magic_literals(self) -> None:
        pkg_scan = ZeroHardcodedValuesAstGate.scan_paths([CODE_ROOT / "velocity_signal_radar"])
        self.assertTrue(pkg_scan["passed"], f"AST violations: {pkg_scan['violations']}")

        bad_scan = ZeroHardcodedValuesAstGate.scan_source(
            "def bad_threshold(x: float) -> bool:\n    return x > 0.85 or x < -42\n"
        )
        self.assertFalse(bad_scan["passed"])
        self.assertEqual(bad_scan["violation_count"], 2)

    def test_20_domain_agnostic_naming_gate_and_zero_legacy_model_references(self) -> None:
        ws_scan = DomainAgnosticNamingGate.scan_workspace(
            [CODE_ROOT / "velocity_signal_radar"],
            forbidden_tokens=self.grid.spec["forbidden_domain_tokens"],
            schema_ids=[self.grid.grid_id],
        )
        self.assertTrue(ws_scan["passed"], f"Naming violations: {ws_scan['violations']}")

        bad_cls = DomainAgnosticNamingGate.scan_source(
            "class RealEstateHarvester:\n    pass\nclass SuperSeedPack:\n    pass\n",
            forbidden_tokens=self.grid.spec["forbidden_domain_tokens"],
        )
        self.assertFalse(bad_cls["passed"])
        self.assertEqual(bad_cls["violation_count"], 2)

        for exported in vsr.__all__:
            self.assertNotIn("SuperSeed", exported)
            self.assertNotIn("SuperMeta", exported)

        forbidden_legacy = "llama" + "3.2"
        forbidden_legacy_spaced = "llama " + "3.2"
        for text_file in PACK_ROOT.rglob("*"):
            if not text_file.is_file() or "__pycache__" in text_file.parts or ".pytest_cache" in text_file.parts:
                continue
            lowered = text_file.read_text(encoding="utf-8", errors="ignore").lower()
            self.assertNotIn(forbidden_legacy, lowered, f"Forbidden legacy model string in {text_file}")
            self.assertNotIn(forbidden_legacy_spaced, lowered, f"Forbidden legacy model string in {text_file}")


if __name__ == "__main__":
    unittest.main()
