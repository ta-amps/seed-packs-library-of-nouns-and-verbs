"""Polyhierarchical capability ontology DAG engine without single-parent or fixed-depth lock-in."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any

from .grid_config import NodeGrid


@dataclass(frozen=True)
class CapabilityNode:
    """Universal polyhierarchical capability or facet node supporting multiple parent_ids."""

    node_id: str
    title: str
    parent_ids: tuple[str, ...]
    facet_labels: tuple[str, ...]
    attributes: dict[str, Any]


def build_capability_node(raw: Mapping[str, Any]) -> CapabilityNode:
    """Construct an immutable CapabilityNode with deduplicated ordered parents and facets."""
    node_id = str(raw["node_id"]).strip()
    title = str(raw["title"]).strip()
    if not node_id or not title:
        raise ValueError("CapabilityNode requires non-empty node_id and title")
    parents = tuple(dict.fromkeys(str(p).strip() for p in raw.get("parent_ids", ()) if str(p).strip()))
    facets = tuple(dict.fromkeys(str(f).strip() for f in raw.get("facet_labels", ()) if str(f).strip()))
    attrs = dict(raw.get("attributes", {}))
    return CapabilityNode(
        node_id=node_id,
        title=title,
        parent_ids=parents,
        facet_labels=facets,
        attributes=attrs,
    )


def validate_polyhierarchical_dag(nodes: Sequence[CapabilityNode]) -> dict[str, Any]:
    """Validate unique node IDs, parent references and directed acyclicity via Kahn topological sort."""
    by_id: dict[str, CapabilityNode] = {}
    duplicate_ids: list[str] = []
    for node in nodes:
        if node.node_id in by_id:
            duplicate_ids.append(node.node_id)
        by_id[node.node_id] = node

    missing_parents: list[dict[str, str]] = []
    children_of: dict[str, list[str]] = {nid: [] for nid in by_id}
    in_degree: dict[str, int] = {nid: 0 for nid in by_id}
    multi_parent_ids: list[str] = []

    for nid, node in by_id.items():
        if len(node.parent_ids) > 1:
            multi_parent_ids.append(nid)
        for pid in node.parent_ids:
            if pid not in by_id:
                missing_parents.append({"node_id": nid, "missing_parent_id": pid})
            else:
                children_of[pid].append(nid)
                in_degree[nid] += 1

    queue: deque[str] = deque(sorted(nid for nid, deg in in_degree.items() if deg == 0))
    topo_order: list[str] = []
    longest_depth: dict[str, int] = {nid: 0 for nid in queue}

    while queue:
        current = queue.popleft()
        topo_order.append(current)
        for child_id in sorted(children_of[current]):
            cand_depth = longest_depth.get(current, 0) + 1
            if cand_depth > longest_depth.get(child_id, 0):
                longest_depth[child_id] = cand_depth
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)

    cycle_nodes = sorted(nid for nid in by_id if nid not in set(topo_order))
    max_in_degree = max((len(n.parent_ids) for n in by_id.values()), default=0)
    max_dag_depth = max(longest_depth.values(), default=0)
    valid = (not duplicate_ids) and (not missing_parents) and (not cycle_nodes)

    return {
        "valid": valid,
        "node_count": len(by_id),
        "root_count": sum(1 for n in by_id.values() if len(n.parent_ids) == 0),
        "multi_parent_count": len(multi_parent_ids),
        "multi_parent_node_ids": sorted(multi_parent_ids),
        "max_parent_count": max_in_degree,
        "max_longest_path_depth": max_dag_depth,
        "topological_order": topo_order,
        "duplicate_ids": sorted(duplicate_ids),
        "missing_parents": missing_parents,
        "cycle_node_ids": cycle_nodes,
    }


def ancestors_of(nodes: Sequence[CapabilityNode], node_id: str) -> set[str]:
    """Return all transitive ancestor node IDs across every polyhierarchical parent branch."""
    by_id = {n.node_id: n for n in nodes}
    if node_id not in by_id:
        raise KeyError(f"unknown capability node: {node_id}")
    visited: set[str] = set()
    stack = list(by_id[node_id].parent_ids)
    while stack:
        pid = stack.pop()
        if pid in visited or pid not in by_id:
            continue
        visited.add(pid)
        stack.extend(by_id[pid].parent_ids)
    return visited


def descendants_of(nodes: Sequence[CapabilityNode], node_id: str) -> set[str]:
    """Return all transitive descendant node IDs reachable from node_id."""
    by_id = {n.node_id: n for n in nodes}
    if node_id not in by_id:
        raise KeyError(f"unknown capability node: {node_id}")
    children_of: dict[str, list[str]] = {nid: [] for nid in by_id}
    for node in nodes:
        for pid in node.parent_ids:
            if pid in children_of:
                children_of[pid].append(node.node_id)
    visited: set[str] = set()
    stack = list(children_of[node_id])
    while stack:
        cid = stack.pop()
        if cid in visited:
            continue
        visited.add(cid)
        stack.extend(children_of.get(cid, ()))
    return visited


def project_by_facets_and_ancestors(
    nodes: Sequence[CapabilityNode],
    *,
    required_ancestors: Sequence[str] = (),
    required_facets: Sequence[str] = (),
    any_facets: Sequence[str] = (),
) -> list[CapabilityNode]:
    """Project capability nodes belonging simultaneously to multiple parent lineages and facet labels."""
    req_anc = set(required_ancestors)
    req_fac = set(required_facets)
    opt_fac = set(any_facets)
    matched: list[CapabilityNode] = []
    for node in nodes:
        lineage = ancestors_of(nodes, node.node_id) | {node.node_id}
        if not req_anc.issubset(lineage):
            continue
        facet_set = set(node.facet_labels)
        if not req_fac.issubset(facet_set):
            continue
        if opt_fac and not (opt_fac & facet_set):
            continue
        matched.append(node)
    return sorted(matched, key=lambda item: item.node_id)


def _token_shingles(text: str, shingle_size: int) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        return set()
    width = max(1, shingle_size)
    if len(tokens) <= width:
        return {" ".join(tokens)}
    return {" ".join(tokens[idx : idx + width]) for idx in range(len(tokens) - width + 1)}


def shingle_jaccard_similarity(text_a: str, text_b: str, *, shingle_size: int) -> float:
    """Compute token-shingle Jaccard similarity in [0.0, 1.0]."""
    set_a = _token_shingles(text_a, shingle_size)
    set_b = _token_shingles(text_b, shingle_size)
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _node_signature_text(node: CapabilityNode) -> str:
    return f"{node.node_id.replace('_', ' ').replace('-', ' ')} {node.title}"


def deduplicate_capability_nodes(
    existing: Sequence[CapabilityNode],
    candidates: Sequence[CapabilityNode],
    *,
    grid: NodeGrid,
    cell: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deduplicate candidate nodes via shingle Jaccard, merging multi-parent links on near-duplicates."""
    clamped = grid.clamp_cell(cell)
    threshold = float(clamped["dedup_jaccard_threshold"])
    shingle_size = grid.default_shingle_size

    catalog: dict[str, CapabilityNode] = {n.node_id: n for n in existing}
    admitted_ids: list[str] = []
    merged_into: list[dict[str, Any]] = []

    for cand in candidates:
        best_match_id: str | None = None
        best_sim = 0.0
        cand_sig = _node_signature_text(cand)
        if cand.node_id in catalog:
            best_match_id = cand.node_id
            best_sim = 1.0
        else:
            for cur_id, cur_node in catalog.items():
                full_sim = shingle_jaccard_similarity(
                    cand_sig,
                    _node_signature_text(cur_node),
                    shingle_size=shingle_size,
                )
                title_sim = shingle_jaccard_similarity(
                    cand.title,
                    cur_node.title,
                    shingle_size=shingle_size,
                )
                sim = max(full_sim, title_sim)
                if sim > best_sim:
                    best_sim = sim
                    best_match_id = cur_id

        if best_match_id is not None and best_sim >= threshold:
            target = catalog[best_match_id]
            merged_parents = tuple(dict.fromkeys((*target.parent_ids, *cand.parent_ids)))
            merged_facets = tuple(dict.fromkeys((*target.facet_labels, *cand.facet_labels)))
            merged_attrs = {**cand.attributes, **target.attributes}
            catalog[best_match_id] = CapabilityNode(
                node_id=target.node_id,
                title=target.title,
                parent_ids=merged_parents,
                facet_labels=merged_facets,
                attributes=merged_attrs,
            )
            merged_into.append({
                "candidate_id": cand.node_id,
                "canonical_id": best_match_id,
                "similarity": round(best_sim, grid.float_round_digits),
            })
        else:
            catalog[cand.node_id] = cand
            admitted_ids.append(cand.node_id)

    return {
        "nodes": list(catalog.values()),
        "admitted_ids": admitted_ids,
        "merged_duplicates": merged_into,
    }


def branch_open_ended_slice(
    nodes: Sequence[CapabilityNode],
    parent_ids: Sequence[str],
    branch_specs: Sequence[Mapping[str, Any]],
    *,
    grid: NodeGrid,
    cell: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach open-ended child or cross-niche intersection nodes under one or more parent_ids."""
    clamped = grid.clamp_cell(cell)
    max_children = int(clamped["max_children_per_hop"])
    anchor_parents = tuple(dict.fromkeys(str(p).strip() for p in parent_ids if str(p).strip()))

    candidates: list[CapabilityNode] = []
    for raw_spec in list(branch_specs)[:max_children]:
        extra_parents = tuple(str(p).strip() for p in raw_spec.get("parent_ids", ()) if str(p).strip())
        combined_parents = tuple(dict.fromkeys((*anchor_parents, *extra_parents)))
        candidates.append(
            build_capability_node({
                **dict(raw_spec),
                "parent_ids": combined_parents,
            })
        )

    deduped = deduplicate_capability_nodes(nodes, candidates, grid=grid, cell=clamped)
    validation = validate_polyhierarchical_dag(deduped["nodes"])
    if not validation["valid"]:
        raise ValueError(f"invalid branched polyhierarchical DAG: {validation}")
    return {
        "nodes": deduped["nodes"],
        "admitted_ids": deduped["admitted_ids"],
        "merged_duplicates": deduped["merged_duplicates"],
        "dag_summary": validation,
    }
