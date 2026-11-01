"""Capability ontology, intelligence cards, multi-generation seed digestion and Pareto benchmark package."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .grid_config import (
    CELL_LIFECYCLE_ORDER,
    CONFIG_PATH,
    DomainAgnosticNamingGate,
    GridLedger,
    NodeGrid,
    NodeParameter,
    OperationCostLedger,
    ParameterBounds,
    ZeroHardcodedValuesAstGate,
    load_grid_spec,
)
from .intelligence_cards import (
    ToolProfile,
    compute_io_port_signature,
    diff_release_into_profile,
    group_interchangeable_profiles,
    validate_and_normalize_profile,
)
from .ontology_engine import (
    CapabilityNode,
    ancestors_of,
    branch_open_ended_slice,
    build_capability_node,
    deduplicate_capability_nodes,
    descendants_of,
    project_by_facets_and_ancestors,
    shingle_jaccard_similarity,
    validate_polyhierarchical_dag,
)
from .pareto_benchmark import (
    EvaluationRecord,
    build_evaluation_record,
    compute_axis_scores,
    pareto_dominates,
    rank_niche_candidates,
    synthesize_demo_walkthrough,
)
from .seed_bloom_planner import (
    VerbEnvelope,
    build_search_hints,
    digest_seed_one_hop,
)

__all__ = [
    "CELL_LIFECYCLE_ORDER",
    "CONFIG_PATH",
    "CapabilityNode",
    "DomainAgnosticNamingGate",
    "EvaluationRecord",
    "GridLedger",
    "NodeGrid",
    "NodeParameter",
    "OperationCostLedger",
    "ParameterBounds",
    "ToolProfile",
    "VerbEnvelope",
    "ZeroHardcodedValuesAstGate",
    "ancestors_of",
    "branch_open_ended_slice",
    "build_capability_node",
    "build_evaluation_record",
    "build_search_hints",
    "compute_axis_scores",
    "compute_io_port_signature",
    "deduplicate_capability_nodes",
    "descendants_of",
    "diff_release_into_profile",
    "digest_seed_one_hop",
    "evaluate_bundle",
    "group_interchangeable_profiles",
    "load_grid_spec",
    "pareto_dominates",
    "project_by_facets_and_ancestors",
    "rank_niche_candidates",
    "shingle_jaccard_similarity",
    "synthesize_demo_walkthrough",
    "validate_and_normalize_profile",
    "validate_polyhierarchical_dag",
]


def evaluate_bundle(bundle: Mapping[str, Any], *, grid: NodeGrid | None = None) -> dict[str, Any]:
    """Execute deterministic end-to-end ontology validation, 3-generation seed digestion and Pareto ranking."""
    active_grid = grid if grid is not None else NodeGrid()
    ledger = GridLedger(active_grid)
    regime = str(bundle.get("ranking_regime", "edge_small_footprint"))
    cell = active_grid.clamp_cell(active_grid.regime_defaults.get(regime))

    # Promote the target regime cell through distinct proposer and verifier principals
    for st in ("proposed", "dispatched", "evaluated"):
        ledger.transition(cell, st, worker_id="worker-proposer", key_id="key-proposer")
    ledger.transition(cell, "verified", worker_id="worker-reviewer", key_id="key-reviewer")
    ledger.transition(cell, "promoted", worker_id="worker-reviewer", key_id="key-reviewer")

    nodes = [build_capability_node(raw) for raw in bundle["ontology_nodes"]]
    dag_check = validate_polyhierarchical_dag(nodes)
    known_ids = {n.node_id for n in nodes}

    # Project multi-niche intersection (e.g. OCR + PII + 4GB small laptop)
    proj_query = bundle["projection_query"]
    projected = project_by_facets_and_ancestors(
        nodes,
        required_ancestors=proj_query.get("required_ancestors", ()),
        required_facets=proj_query.get("required_facets", ()),
    )

    # Validate intelligence cards and cluster interchangeable I/O signatures
    profiles: dict[str, ToolProfile] = {}
    for raw_card in bundle["intelligence_cards"]:
        res = validate_and_normalize_profile(raw_card, grid=active_grid, known_node_ids=known_ids)
        if not res["valid"]:
            raise ValueError(f"invalid intelligence card {raw_card.get('profile_id')}: {res['errors']}")
        prof: ToolProfile = res["profile"]
        profiles[prof.profile_id] = prof
    io_clusters = group_interchangeable_profiles(list(profiles.values()), grid=active_grid)

    # Diff an OSS release update
    rel_spec = bundle["release_diff_probe"]
    prior_prof = profiles.get(str(rel_spec.get("prior_profile_id", "")))
    rel_diff = diff_release_into_profile(
        prior_prof,
        rel_spec["release_card"],
        grid=active_grid,
        known_node_ids=known_ids,
    )

    # Execute 3-generation bounded seed digestion (gen 0 -> gen 1 -> gen 2)
    digest_cfg = bundle["seed_digestion"]
    gen_cell = active_grid.clamp_cell(digest_cfg.get("cell_override"))
    gen0_env = VerbEnvelope(
        task_id=str(digest_cfg["root_task_id"]),
        verb_kind="verb.expand_seed",
        title=str(digest_cfg["root_title"]),
        prompt=str(digest_cfg["root_prompt"]),
        parent_task_id=None,
        source_task_id=str(digest_cfg["root_task_id"]),
        generation_depth=0,
        input_pins=("catalog.root-ecosystem-seeds",),
        search_hints=build_search_hints(
            intent_signature="root_ecosystem_seed_digestion",
            keywords=["ocr", "pii", "3d", "motion", "mcp", "durable_queue"],
            phrases=[str(digest_cfg["root_title"])],
            synonyms=["capability_ontology", "benchmark_seed"],
            facet_axes={"opt_goal": "pareto_efficiency", "deliverable_kind": "capability_slice"},
        ),
        facet_axes={"opt_goal": "pareto_efficiency", "deliverable_kind": "capability_slice"},
    )
    hop1 = digest_seed_one_hop(
        digest_cfg["seed_noun"],
        gen0_env,
        branch_candidates=digest_cfg["gen1_branches"],
        agent_id="worker-seed-planner",
        worker_uuid="uuid-planner-alpha",
        fencing_token="fence-gen0",
        grid=active_grid,
        cell=gen_cell,
    )
    hop2 = digest_seed_one_hop(
        {"seed_key": hop1["child_envelopes"][0].task_id, "title": hop1["child_envelopes"][0].title},
        hop1["child_envelopes"][0],
        branch_candidates=digest_cfg["gen2_branches"],
        agent_id="worker-seed-planner",
        worker_uuid="uuid-planner-alpha",
        fencing_token="fence-gen1",
        grid=active_grid,
        cell=gen_cell,
    )

    # Pareto benchmark and demo synthesis
    eval_records = [build_evaluation_record(item) for item in bundle["evaluation_records"]]
    ranking = rank_niche_candidates(eval_records, grid=active_grid, cell=cell)
    demo = synthesize_demo_walkthrough(ranking, profiles, grid=active_grid)

    # Mechanical AST & domain-agnostic naming gates
    pkg_dir = Path(__file__).resolve().parent
    allowed_ids = active_grid.spec["allowed_ast_identities"]
    banned_tokens = active_grid.spec["forbidden_domain_tokens"]
    engine_ast = ZeroHardcodedValuesAstGate.scan_paths([pkg_dir], allowed_identities=allowed_ids)
    engine_naming = DomainAgnosticNamingGate.scan_workspace(
        [pkg_dir],
        forbidden_tokens=banned_tokens,
        schema_ids=[active_grid.grid_id],
    )
    sample_magic = ZeroHardcodedValuesAstGate.scan_source(
        str(bundle["magic_code_sample"]),
        allowed_identities=allowed_ids,
    )
    sample_domain = DomainAgnosticNamingGate.scan_source(
        str(bundle["industry_coupled_sample"]),
        forbidden_tokens=banned_tokens,
    )

    return {
        "dag_valid": bool(dag_check["valid"]),
        "ontology_node_count": int(dag_check["node_count"]),
        "multi_parent_node_count": int(dag_check["multi_parent_count"]),
        "projected_intersection_ids": [n.node_id for n in projected],
        "verified_profile_count": len(profiles),
        "interchangeable_io_cluster_count": sum(1 for ids in io_clusters.values() if len(ids) > 1),
        "release_added_mcp_tools": list(rel_diff["diff"]["added_mcp_tools"]),
        "gen1_emitted_verbs": len(hop1["child_envelopes"]),
        "gen2_emitted_verbs": len(hop2["child_envelopes"]),
        "gen2_preserved_source_task_id": hop2["child_envelopes"][0].source_task_id == gen0_env.task_id,
        "gen2_generation_depth": int(hop2["child_envelopes"][0].generation_depth),
        "pareto_frontier_ids": list(ranking["pareto_frontier_ids"]),
        "top_ranked_candidate_id": str(ranking["top_candidate_id"]),
        "demo_storyboard_beats": len(demo["storyboard_beats"]),
        "promoted_grid_cell_state": str(ledger.records[active_grid.cell_id(cell)]["state"]),
        "engine_ast_violations": int(engine_ast["violation_count"]),
        "engine_naming_violations": int(engine_naming["violation_count"]),
        "sample_magic_ast_violations": int(sample_magic["violation_count"]),
        "sample_domain_naming_violations": int(sample_domain["violation_count"]),
    }
