"""Comprehensive unit tests for capability_ontology_seeds (26 deterministic tests)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import capability_ontology_seeds as cos
from capability_ontology_seeds import (
    CONFIG_PATH,
    CapabilityNode,
    DomainAgnosticNamingGate,
    EvaluationRecord,
    GridLedger,
    NodeGrid,
    NodeParameter,
    OperationCostLedger,
    ParameterBounds,
    ToolProfile,
    VerbEnvelope,
    ZeroHardcodedValuesAstGate,
    ancestors_of,
    branch_open_ended_slice,
    build_capability_node,
    build_evaluation_record,
    build_search_hints,
    compute_axis_scores,
    compute_io_port_signature,
    deduplicate_capability_nodes,
    descendants_of,
    diff_release_into_profile,
    digest_seed_one_hop,
    evaluate_bundle,
    group_interchangeable_profiles,
    pareto_dominates,
    project_by_facets_and_ancestors,
    rank_niche_candidates,
    synthesize_demo_walkthrough,
    validate_and_normalize_profile,
    validate_polyhierarchical_dag,
)

CODE_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = CODE_ROOT.parent


class CapabilityOntologySeedsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = NodeGrid()
        self.source_doc = json.loads((PACK_ROOT / "source.json").read_text(encoding="utf-8"))
        self.nouns_by_slug = {item["slug"]: item for item in self.source_doc["nouns"]}

    def test_01_grid_spec_loads_and_enumerates_constraints(self) -> None:
        cells = self.grid.enumerate_cells()
        self.assertGreater(len(cells["represented"]), len(cells["applicable"]))
        for cell in cells["applicable"]:
            if cell["ranking_regime"] == "cluster_production":
                self.assertTrue(cell["require_reproducible_demo"])
            if cell["max_generation_depth"] == 5:
                self.assertIn(cell["max_children_per_hop"], (2, 4))

    def test_02_parameter_bounds_clamping_across_all_types(self) -> None:
        clamped = self.grid.clamp_cell({
            "max_generation_depth": 99,
            "max_children_per_hop": 7,
            "dedup_jaccard_threshold": 0.99,
            "ranking_regime": "nonexistent_regime",
            "require_reproducible_demo": 0,
        })
        self.assertEqual(clamped["max_generation_depth"], 5)
        self.assertEqual(clamped["max_children_per_hop"], 6)
        self.assertEqual(clamped["dedup_jaccard_threshold"], 0.9)
        self.assertEqual(clamped["ranking_regime"], "balanced_general")
        self.assertFalse(clamped["require_reproducible_demo"])

    def test_03_grid_boundary_auto_expansion_saturates_high_and_low(self) -> None:
        expanded_high, actions_high = self.grid.auto_expand_if_saturated({
            "max_generation_depth": 5,
            "max_children_per_hop": 8,
        })
        self.assertEqual(expanded_high.generation, 2)
        self.assertIn("max_generation_depth:high->10", actions_high)
        self.assertIn("max_children_per_hop:high->16", actions_high)

        expanded_low, actions_low = self.grid.auto_expand_if_saturated({
            "dedup_jaccard_threshold": 0.5,
            "max_children_per_hop": 2,
        })
        self.assertEqual(expanded_low.generation, 2)
        self.assertIn("dedup_jaccard_threshold:low->0.25", actions_low)
        self.assertIn("max_children_per_hop:low->1", actions_low)

    def test_04_grid_ledger_monotonic_lifecycle_and_distinct_verifier_gate(self) -> None:
        ledger = GridLedger(self.grid)
        cell = self.grid.clamp_cell(self.grid.regime_defaults["balanced_general"])

        # Skipping from applicable directly to verified is rejected with HTTP 409
        skip_res = ledger.transition(cell, "verified", worker_id="w-1", key_id="k-1")
        self.assertFalse(skip_res["ok"])
        self.assertEqual(skip_res["status_code"], 409)

        # Inapplicable constraint cell cannot be proposed
        inapplicable = {
            "max_generation_depth": 3,
            "max_children_per_hop": 4,
            "dedup_jaccard_threshold": 0.7,
            "ranking_regime": "cluster_production",
            "require_reproducible_demo": False,
        }
        inapp_res = ledger.transition(inapplicable, "proposed", worker_id="w-1", key_id="k-1")
        self.assertFalse(inapp_res["ok"])
        self.assertEqual(inapp_res["reason"], "inapplicable_constraint_cell")

        # Monotonic progression up to evaluated
        for st in ("proposed", "dispatched", "evaluated"):
            step = ledger.transition(cell, st, worker_id="maker-1", key_id="key-maker", metrics={"q": 0.92})
            self.assertTrue(step["ok"])

        # Self-verification blocked on matching worker_id or key_id
        same_worker = ledger.transition(cell, "verified", worker_id="maker-1", key_id="key-other")
        self.assertFalse(same_worker["ok"])
        self.assertEqual(same_worker["status_code"], 409)
        same_key = ledger.transition(cell, "verified", worker_id="checker-2", key_id="key-maker")
        self.assertFalse(same_key["ok"])

        # Distinct verifier succeeds and promotes
        verified = ledger.transition(cell, "verified", worker_id="checker-2", key_id="key-checker")
        self.assertTrue(verified["ok"])
        promoted = ledger.transition(cell, "promoted", worker_id="checker-2", key_id="key-checker")
        self.assertTrue(promoted["ok"])
        self.assertEqual(promoted["state"], "promoted")

    def test_05_operation_cost_ledger_contextual_regime_resolution(self) -> None:
        ledger = GridLedger(self.grid)
        cost_ledger = OperationCostLedger(self.grid, ledger)

        # Unverified observation falls back to regime_default
        cand_cell = {
            "max_generation_depth": 2,
            "max_children_per_hop": 2,
            "dedup_jaccard_threshold": 0.7,
            "ranking_regime": "ultra_low_latency",
            "require_reproducible_demo": True,
        }
        cost_ledger.record_observation(
            regime="ultra_low_latency",
            cell=cand_cell,
            quality_score=0.95,
            cost_units=0.12,
        )
        fallback = cost_ledger.resolve_for_regime("ultra_low_latency", min_quality=0.9)
        self.assertEqual(fallback["source"], "regime_default")

        # Promote cand_cell -> now resolves from verified_ledger_optimum
        for st in ("proposed", "dispatched", "evaluated"):
            ledger.transition(cand_cell, st, worker_id="w-a", key_id="k-a")
        ledger.transition(cand_cell, "verified", worker_id="w-b", key_id="k-b")
        resolved = cost_ledger.resolve_for_regime("ultra_low_latency", min_quality=0.9)
        self.assertEqual(resolved["source"], "verified_ledger_optimum")
        self.assertAlmostEqual(resolved["cost_units"], 0.12)

    def test_06_polyhierarchical_dag_multi_parent_across_ten_niches(self) -> None:
        raw_nodes = self.nouns_by_slug["example.ontology-seed-bundle"]["value"]["ontology_nodes"]
        nodes = [build_capability_node(item) for item in raw_nodes]
        summary = validate_polyhierarchical_dag(nodes)
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["node_count"], 16)
        self.assertEqual(summary["multi_parent_count"], 3)
        self.assertEqual(summary["max_parent_count"], 4)

        # Verify all 10 required ecosystem niches are represented
        node_ids = {n.node_id for n in nodes}
        for niche in (
            "ocr_document_intelligence",
            "pii_redaction_and_privacy",
            "3d_rendering_and_scene_synthesis",
            "motion_graphics_and_programmatic_video",
            "voice_audio_synthesis_and_asr",
            "mcp_servers_and_tool_protocols",
            "durable_task_queues_and_leases",
            "agent_architecture_patterns",
            "new_oss_ai_releases",
            "ai_hackathons_and_tracks",
        ):
            self.assertIn(niche, node_ids)

    def test_07_polyhierarchical_dag_detects_cycles_and_missing_parents(self) -> None:
        cyclic_nodes = [
            build_capability_node({"node_id": "alpha", "title": "Alpha", "parent_ids": ["gamma"]}),
            build_capability_node({"node_id": "beta", "title": "Beta", "parent_ids": ["alpha"]}),
            build_capability_node({"node_id": "gamma", "title": "Gamma", "parent_ids": ["beta"]}),
        ]
        cyc_summary = validate_polyhierarchical_dag(cyclic_nodes)
        self.assertFalse(cyc_summary["valid"])
        self.assertEqual(cyc_summary["cycle_node_ids"], ["alpha", "beta", "gamma"])

        missing_nodes = [
            build_capability_node({"node_id": "child_x", "title": "Child X", "parent_ids": ["unknown_root"]}),
        ]
        miss_summary = validate_polyhierarchical_dag(missing_nodes)
        self.assertFalse(miss_summary["valid"])
        self.assertEqual(len(miss_summary["missing_parents"]), 1)

    def test_08_multi_parent_facet_projection_ocr_pii_small_laptop(self) -> None:
        raw_nodes = self.nouns_by_slug["example.ontology-seed-bundle"]["value"]["ontology_nodes"]
        nodes = [build_capability_node(item) for item in raw_nodes]
        hits = project_by_facets_and_ancestors(
            nodes,
            required_ancestors=[
                "ocr_document_intelligence",
                "pii_redaction_and_privacy",
                "runs_on_small_4gb_laptop",
            ],
            required_facets=["privacy:offline_scrub", "footprint:sub_4gb_ram"],
        )
        self.assertEqual([n.node_id for n in hits], ["edge_ocr_pii_redactor"])
        self.assertEqual(
            ancestors_of(nodes, "edge_ocr_pii_redactor"),
            {"ocr_document_intelligence", "pii_redaction_and_privacy", "runs_on_small_4gb_laptop"},
        )
        self.assertIn("edge_ocr_pii_redactor", descendants_of(nodes, "ocr_document_intelligence"))

    def test_09_multi_parent_facet_projection_3d_motion_zero_dep(self) -> None:
        raw_nodes = self.nouns_by_slug["example.ontology-seed-bundle"]["value"]["ontology_nodes"]
        nodes = [build_capability_node(item) for item in raw_nodes]
        hits = project_by_facets_and_ancestors(
            nodes,
            required_ancestors=[
                "3d_rendering_and_scene_synthesis",
                "motion_graphics_and_programmatic_video",
                "single_maintainer_zero_dep",
            ],
        )
        self.assertEqual([n.node_id for n in hits], ["procedural_3d_motion_canvas"])

    def test_10_shingle_jaccard_deduplication_merges_polyhierarchical_parents(self) -> None:
        existing = [
            build_capability_node({
                "node_id": "ocr_table_scrubber",
                "title": "Offline PDF OCR table PII scrubber",
                "parent_ids": ["ocr_document_intelligence"],
                "facet_labels": ["modality:document_vision"],
            })
        ]
        candidates = [
            build_capability_node({
                "node_id": "ocr_table_scrubber_alt",
                "title": "Offline PDF OCR table PII scrubber",
                "parent_ids": ["pii_redaction_and_privacy", "runs_on_small_4gb_laptop"],
                "facet_labels": ["privacy:offline_scrub"],
            }),
            build_capability_node({
                "node_id": "streaming_whisper_vad",
                "title": "Low latency streaming voice activity and ASR aligner",
                "parent_ids": ["voice_audio_synthesis_and_asr"],
                "facet_labels": ["modality:speech_audio"],
            }),
        ]
        res = deduplicate_capability_nodes(existing, candidates, grid=self.grid)
        self.assertEqual(res["admitted_ids"], ["streaming_whisper_vad"])
        self.assertEqual(len(res["merged_duplicates"]), 1)
        by_id = {n.node_id: n for n in res["nodes"]}
        self.assertEqual(
            by_id["ocr_table_scrubber"].parent_ids,
            ("ocr_document_intelligence", "pii_redaction_and_privacy", "runs_on_small_4gb_laptop"),
        )
        self.assertEqual(
            by_id["ocr_table_scrubber"].facet_labels,
            ("modality:document_vision", "privacy:offline_scrub"),
        )

    def test_11_open_ended_niche_branching_without_schema_or_depth_lockin(self) -> None:
        roots = [
            build_capability_node({"node_id": "voice_asr", "title": "Voice and ASR"}),
            build_capability_node({"node_id": "hackathon_radar", "title": "Hackathon tracks"}),
        ]
        hop1 = branch_open_ended_slice(
            roots,
            ["voice_asr", "hackathon_radar"],
            [
                {
                    "node_id": "multilingual_ngo_hotline_asr",
                    "title": "Multilingual hotline ASR and intake triage",
                    "facet_labels": ["modality:speech_audio", "hackathon:public_good"],
                    "attributes": {"arbitrary_future_metric": "wer_under_noise_db"},
                }
            ],
            grid=self.grid,
        )
        hop2 = branch_open_ended_slice(
            hop1["nodes"],
            ["multilingual_ngo_hotline_asr"],
            [
                {
                    "node_id": "sub_4gb_quantized_hotline_asr",
                    "title": "Quantized 4-bit offline hotline ASR",
                    "facet_labels": ["footprint:sub_4gb_ram"],
                    "attributes": {"quantization_bits": "int4_awq"},
                }
            ],
            grid=self.grid,
        )
        self.assertTrue(hop2["dag_summary"]["valid"])
        self.assertEqual(hop2["dag_summary"]["max_longest_path_depth"], 2)
        by_id = {n.node_id: n for n in hop2["nodes"]}
        self.assertEqual(by_id["sub_4gb_quantized_hotline_asr"].attributes["quantization_bits"], "int4_awq")

    def test_12_intelligence_card_validation_across_all_six_subject_kinds(self) -> None:
        bundle = self.nouns_by_slug["example.ontology-seed-bundle"]["value"]
        known_ids = {item["node_id"] for item in bundle["ontology_nodes"]}
        kinds_seen: set[str] = set()
        for card in bundle["intelligence_cards"]:
            res = validate_and_normalize_profile(card, grid=self.grid, known_node_ids=known_ids)
            self.assertTrue(res["valid"], res["errors"])
            self.assertIsInstance(res["profile"], ToolProfile)
            kinds_seen.add(res["profile"].subject_kind)
        # Also test oss_release explicitly
        rel_card = {**bundle["intelligence_cards"][0], "profile_id": "oss_rel_1", "subject_kind": "oss_release"}
        rel_res = validate_and_normalize_profile(rel_card, grid=self.grid, known_node_ids=known_ids)
        self.assertTrue(rel_res["valid"])
        kinds_seen.add(rel_res["profile"].subject_kind)
        self.assertEqual(
            kinds_seen,
            {"ai_tool", "mcp_server", "feed_stream", "durable_queue", "architecture_pattern", "oss_release"},
        )

    def test_13_intelligence_card_rejects_invalid_mcp_or_missing_failure_modes(self) -> None:
        bad_mcp = {
            "profile_id": "bad_mcp_srv",
            "subject_kind": "mcp_server",
            "title": "Broken MCP server card",
            "parent_ids": ["mcp_servers_and_tool_protocols"],
            "input_ports": [{"name": "in", "media_type": "application/json", "schema_ref": "req_v1"}],
            "output_ports": [{"name": "out", "media_type": "application/json", "schema_ref": "res_v1"}],
            "spdx_license": "MIT",
            "execution_mode": "offline_local",
            "mcp_transport": "none",
            "mcp_tools": [],
            "failure_modes": [],
            "verification_command": "",
        }
        res = validate_and_normalize_profile(bad_mcp, grid=self.grid)
        self.assertFalse(res["valid"])
        self.assertIn("mcp_server_requires_transport_and_tools", res["errors"])
        self.assertIn("missing_failure_modes", res["errors"])
        self.assertIn("missing_verification_command", res["errors"])

    def test_14_canonical_io_port_signature_clusters_hot_swappable_tools(self) -> None:
        bundle = self.nouns_by_slug["example.ontology-seed-bundle"]["value"]
        profiles = [
            validate_and_normalize_profile(card, grid=self.grid)["profile"]
            for card in bundle["intelligence_cards"]
        ]
        clusters = group_interchangeable_profiles(profiles, grid=self.grid)
        multi = [ids for ids in clusters.values() if len(ids) > 1]
        self.assertEqual(multi, [["ocr_pii_cluster_gpu", "ocr_pii_lite_cpu"]])

    def test_15_oss_release_and_hackathon_pattern_diffing(self) -> None:
        bundle = self.nouns_by_slug["example.ontology-seed-bundle"]["value"]
        prior = validate_and_normalize_profile(bundle["intelligence_cards"][2], grid=self.grid)["profile"]
        diff_res = diff_release_into_profile(
            prior,
            bundle["release_diff_probe"]["release_card"],
            grid=self.grid,
        )
        self.assertTrue(diff_res["valid"])
        self.assertEqual(diff_res["diff"]["change_kind"], "incremental_release_diff")
        self.assertFalse(diff_res["diff"]["io_signature_changed"])
        self.assertEqual(diff_res["diff"]["added_mcp_tools"], ["verify_redaction_audit"])
        self.assertEqual(diff_res["diff"]["ram_delta_mb"], -256)

        fresh_res = diff_release_into_profile(None, bundle["release_diff_probe"]["release_card"], grid=self.grid)
        self.assertEqual(fresh_res["diff"]["change_kind"], "new_capability_entry")

    def test_16_three_generation_seed_digestion_gen0_gen1_gen2_and_q_submit_shape(self) -> None:
        gen0 = VerbEnvelope(
            task_id="root_seed_task_001",
            verb_kind="verb.expand_seed",
            title="Root AI capability ontology seed",
            prompt="Expand root capability catalog.",
            parent_task_id=None,
            source_task_id="root_seed_task_001",
            generation_depth=0,
            input_pins=("catalog.root-ecosystem-seeds",),
            search_hints=build_search_hints(
                intent_signature="seed:root",
                keywords=["ocr", "pii", "3d", "motion"],
                phrases=["root capability seed"],
                synonyms=["ecosystem_ontology"],
                facet_axes={"opt_goal": "pareto_frontier", "prog_lang": "python"},
            ),
            facet_axes={"opt_goal": "pareto_frontier", "prog_lang": "python"},
        )
        hop1 = digest_seed_one_hop(
            {"seed_key": "catalog.root-ecosystem-seeds", "title": "Root catalog"},
            gen0,
            branch_candidates=[
                {
                    "slug": "ocr-pii-redaction",
                    "title": "OCR and PII redaction tools",
                    "parent_ids": ["ocr_document_intelligence", "pii_redaction_and_privacy"],
                    "keywords": ["ocr", "pii"],
                },
                {
                    "slug": "motion-3d-renderers",
                    "title": "3D and motion graphics renderers",
                    "parent_ids": ["3d_rendering_and_scene_synthesis", "motion_graphics_and_programmatic_video"],
                    "keywords": ["3d", "motion"],
                },
            ],
            agent_id="muse-worker-1",
            worker_uuid="uuid-101",
            fencing_token="fence-001",
            grid=self.grid,
        )
        sub1 = hop1["submit_payload"]
        for req_key in (
            "agent_id",
            "worker_uuid",
            "task_id",
            "fencing_token",
            "parent_task_id",
            "source_task_id",
            "generation_depth",
            "task_objects",
            "queued_verbs",
            "verbs",
            "search_hints",
            "facet_axes",
        ):
            self.assertIn(req_key, sub1)
        self.assertEqual(len(hop1["child_envelopes"]), 2)
        gen1_child = hop1["child_envelopes"][0]
        self.assertEqual(gen1_child.generation_depth, 1)
        self.assertEqual(gen1_child.parent_task_id, "root_seed_task_001")
        self.assertEqual(gen1_child.source_task_id, "root_seed_task_001")

        hop2 = digest_seed_one_hop(
            {"seed_key": gen1_child.task_id, "title": gen1_child.title},
            gen1_child,
            branch_candidates=[
                {
                    "slug": "laptop-4gb-pdf-redactor-bench",
                    "title": "Benchmark 4GB laptop PDF PII redactors",
                    "verb_kind": "verb.benchmark_harness",
                    "parent_ids": ["edge_ocr_pii_redactor"],
                }
            ],
            agent_id="codex-worker-2",
            worker_uuid="uuid-202",
            fencing_token="fence-002",
            grid=self.grid,
        )
        gen2_child = hop2["child_envelopes"][0]
        self.assertEqual(gen2_child.generation_depth, 2)
        self.assertEqual(gen2_child.parent_task_id, gen1_child.task_id)
        self.assertEqual(gen2_child.source_task_id, "root_seed_task_001")
        self.assertIn("poly_parents", gen2_child.facet_axes)

    def test_17_seed_digestion_suppresses_near_duplicate_branches_and_caps_fanout(self) -> None:
        env = VerbEnvelope(
            task_id="t_root",
            verb_kind="verb.expand_seed",
            title="Root",
            prompt="Expand",
            parent_task_id=None,
            source_task_id="t_root",
            generation_depth=0,
            input_pins=(),
            search_hints={},
            facet_axes={},
        )
        branches = [
            {"slug": "durable-sqlite-lease-queue", "title": "Durable SQLite inline lease task queue"},
            {"slug": "durable-sqlite-lease-queue-v2", "title": "Durable SQLite inline lease task queue"},
            {"slug": "mcp-stdio-sandbox-inspector", "title": "MCP stdio sandbox capability inspector"},
            {"slug": "blender-headless-camera-rig", "title": "Headless 3D camera rig and glTF renderer"},
        ]
        res = digest_seed_one_hop(
            {"seed_key": "root"},
            env,
            branch_candidates=branches,
            agent_id="opencode-w",
            worker_uuid="uuid-3",
            fencing_token="f-3",
            grid=self.grid,
            cell={"max_children_per_hop": 2, "dedup_jaccard_threshold": 0.7},
        )
        self.assertEqual(res["skipped_duplicates"], ["durable-sqlite-lease-queue-v2"])
        self.assertEqual(len(res["child_envelopes"]), 2)

    def test_18_seed_digestion_halts_cleanly_at_max_generation_depth(self) -> None:
        deep_env = VerbEnvelope(
            task_id="task_g3_leaf",
            verb_kind="verb.expand_seed",
            title="Leaf slice",
            prompt="Leaf",
            parent_task_id="task_g2_mid",
            source_task_id="task_g0_root",
            generation_depth=3,
            input_pins=(),
            search_hints={},
            facet_axes={},
        )
        res = digest_seed_one_hop(
            {"seed_key": "leaf_slice"},
            deep_env,
            branch_candidates=[{"slug": "would-be-g4", "title": "Blocked beyond depth ceiling"}],
            agent_id="grok-worker",
            worker_uuid="uuid-4",
            fencing_token="f-4",
            grid=self.grid,
            cell={"max_generation_depth": 3},
        )
        self.assertTrue(res["depth_cap_reached"])
        self.assertEqual(res["child_envelopes"], [])
        self.assertEqual(res["submit_payload"]["queued_verbs"], [])
        self.assertEqual(len(res["submit_payload"]["task_objects"]), 1)

    def test_19_pareto_dominance_and_frontier_extraction(self) -> None:
        scores_a = {"cost": 0.9, "lat": 0.8, "acc": 0.9}
        scores_b = {"cost": 0.7, "lat": 0.8, "acc": 0.85}
        scores_c = {"cost": 0.5, "lat": 0.99, "acc": 0.7}
        self.assertTrue(pareto_dominates(scores_a, scores_b, axes=("cost", "lat", "acc"), epsilon=1e-9))
        self.assertFalse(pareto_dominates(scores_a, scores_c, axes=("cost", "lat", "acc"), epsilon=1e-9))
        self.assertFalse(pareto_dominates(scores_c, scores_a, axes=("cost", "lat", "acc"), epsilon=1e-9))

    def test_20_contextual_regime_shifts_top_winner_across_laptop_latency_cost_and_k8s(self) -> None:
        records = [
            # Frugal zero-dep 4GB laptop champion
            EvaluationRecord("frugal_edge_zero_dep", "niche_a", 0.01, 45.0, 512.0, 0, True, False, 0.86, True, "cmd1"),
            # Sub-10ms latency champion
            EvaluationRecord("sub10ms_simd_engine", "niche_a", 0.90, 4.2, 3072.0, 6, False, False, 0.88, True, "cmd2"),
            # Kubernetes high-accuracy cluster champion
            EvaluationRecord("k8s_cluster_accurate", "niche_a", 2.50, 35.0, 24576.0, 18, False, True, 0.99, True, "cmd3"),
            # Strictly dominated slow expensive candidate
            EvaluationRecord("dominated_legacy", "niche_a", 5.00, 250.0, 28000.0, 22, False, False, 0.75, True, "cmd4"),
        ]
        edge_rank = rank_niche_candidates(records, grid=self.grid, cell={"ranking_regime": "edge_small_footprint"})
        lat_rank = rank_niche_candidates(records, grid=self.grid, cell={"ranking_regime": "ultra_low_latency"})
        k8s_rank = rank_niche_candidates(records, grid=self.grid, cell={"ranking_regime": "cluster_production"})

        self.assertEqual(edge_rank["top_candidate_id"], "frugal_edge_zero_dep")
        self.assertEqual(lat_rank["top_candidate_id"], "sub10ms_simd_engine")
        self.assertEqual(k8s_rank["top_candidate_id"], "k8s_cluster_accurate")
        self.assertNotIn("dominated_legacy", edge_rank["pareto_frontier_ids"])
        self.assertEqual(
            edge_rank["pareto_frontier_ids"],
            ["frugal_edge_zero_dep", "k8s_cluster_accurate", "sub10ms_simd_engine"],
        )

    def test_21_reproducible_demo_filter_excludes_unverified_candidates(self) -> None:
        bundle_records = [
            build_evaluation_record(item)
            for item in self.nouns_by_slug["example.ontology-seed-bundle"]["value"]["evaluation_records"]
        ]
        strict_res = rank_niche_candidates(
            bundle_records,
            grid=self.grid,
            cell={"ranking_regime": "edge_small_footprint", "require_reproducible_demo": True},
        )
        self.assertEqual(strict_res["filtered_missing_demo_ids"], ["ocr_pii_unverified_nodemo"])
        relaxed_res = rank_niche_candidates(
            bundle_records,
            grid=self.grid,
            cell={"ranking_regime": "cost_frugal_batch", "require_reproducible_demo": False},
        )
        self.assertEqual(relaxed_res["filtered_missing_demo_ids"], [])
        scores = compute_axis_scores(bundle_records[-1], grid=self.grid)
        self.assertEqual(scores["reproducible_demo_walkthrough"], 0.0)

    def test_22_synthesize_demo_walkthrough_emits_four_deterministic_beats(self) -> None:
        bundle = self.nouns_by_slug["example.ontology-seed-bundle"]["value"]
        profiles = {
            card["profile_id"]: validate_and_normalize_profile(card, grid=self.grid)["profile"]
            for card in bundle["intelligence_cards"]
        }
        records = [build_evaluation_record(r) for r in bundle["evaluation_records"]]
        ranked = rank_niche_candidates(records, grid=self.grid, cell={"ranking_regime": "cost_frugal_batch"})
        walkthrough = synthesize_demo_walkthrough(ranked, profiles, grid=self.grid)
        self.assertEqual(len(walkthrough["storyboard_beats"]), 4)
        self.assertEqual([b["beat_index"] for b in walkthrough["storyboard_beats"]], [1, 2, 3, 4])

    def test_23_worked_example_bundle_recomputes_receipt_byte_for_byte(self) -> None:
        bundle = self.nouns_by_slug["example.ontology-seed-bundle"]["value"]
        expected = self.nouns_by_slug["example.ontology-seed-receipt"]["value"]["instance"]
        recomputed = evaluate_bundle(bundle, grid=self.grid)
        self.assertEqual(recomputed, expected)

    def test_24_cli_bundle_and_self_test_entrypoints(self) -> None:
        self_run = subprocess.run(
            [sys.executable, "-m", "capability_ontology_seeds", "--self-test"],
            cwd=CODE_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        parsed_self = json.loads(self_run.stdout)
        self.assertTrue(parsed_self["ast_passed"])
        self.assertTrue(parsed_self["naming_passed"])

        bundle = self.nouns_by_slug["example.ontology-seed-bundle"]["value"]
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=True) as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            cli_run = subprocess.run(
                [sys.executable, "-m", "capability_ontology_seeds", "--bundle", tmp.name],
                cwd=CODE_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
        parsed_bundle = json.loads(cli_run.stdout)
        self.assertEqual(parsed_bundle, self.nouns_by_slug["example.ontology-seed-receipt"]["value"]["instance"])

    def test_25_zero_hardcoded_values_ast_gate_passes_package_and_catches_magic_literals(self) -> None:
        pkg_dir = CONFIG_PATH.parent.parent
        allowed = self.grid.spec["allowed_ast_identities"]
        scan = ZeroHardcodedValuesAstGate.scan_paths([pkg_dir], allowed_identities=allowed)
        self.assertTrue(scan["passed"], scan["violations"])
        self.assertEqual(scan["violation_count"], 0)
        self.assertGreaterEqual(scan["files_scanned"], 6)

        bad_code = "def compute_score(x: float) -> float:\n    return x * 0.85 - 42\n"
        neg_scan = ZeroHardcodedValuesAstGate.scan_source(bad_code, allowed_identities=allowed)
        self.assertFalse(neg_scan["passed"])
        self.assertEqual(neg_scan["violation_count"], 2)

    def test_26_domain_agnostic_naming_gate_and_zero_custom_super_seed_classes(self) -> None:
        pkg_dir = CONFIG_PATH.parent.parent
        banned = self.grid.spec["forbidden_domain_tokens"]
        naming = DomainAgnosticNamingGate.scan_workspace(
            [pkg_dir],
            forbidden_tokens=banned,
            schema_ids=[self.grid.grid_id],
        )
        self.assertTrue(naming["passed"], naming["violations"])
        self.assertEqual(naming["violation_count"], 0)

        bad_domain_code = "class HealthcareMortgagePipeline:\n    def route_ecommerce_parcel(self) -> None:\n        pass\n"
        neg_naming = DomainAgnosticNamingGate.scan_source(bad_domain_code, forbidden_tokens=banned)
        self.assertFalse(neg_naming["passed"])
        self.assertEqual(neg_naming["violation_count"], 2)

        # Mechanical governance check: ZERO SuperSeedPack / SuperMetaSeed / confusing custom classes
        exported_classes = {
            name
            for name, obj in inspect.getmembers(cos, inspect.isclass)
            if obj.__module__.startswith("capability_ontology_seeds")
        }
        allowed_primitives = {
            "ParameterBounds",
            "NodeParameter",
            "NodeGrid",
            "GridLedger",
            "OperationCostLedger",
            "ZeroHardcodedValuesAstGate",
            "DomainAgnosticNamingGate",
            "CapabilityNode",
            "ToolProfile",
            "VerbEnvelope",
            "EvaluationRecord",
        }
        self.assertEqual(exported_classes, allowed_primitives)


if __name__ == "__main__":
    unittest.main()
