"""Persistent BFS spider frontier, bounded multi-wave follow-up proposals and refresh tracker."""

from __future__ import annotations

from typing import Any

GENERIC_TOPIC_STOPLIST: frozenset[str] = frozenset({
    "react",
    "typescript",
    "javascript",
    "python",
    "alibaba",
    "interview",
    "leetcode",
    "portfolio",
    "homework",
    "coursework",
    "demo",
    "test",
})

SYNONYM_MUTATIONS: dict[str, str] = {
    "template": "boilerplate",
    "editor": "studio",
    "toolkit": "toolbox",
    "framework": " workbench",
    "generator": "synthesizer",
}


def compute_allowed_spider_depth(completed_runs: int, *, base_depth: int = 2, max_depth: int = 8) -> int:
    """Unlock deeper BFS spider traversal (+1 every 8 runs up to max_depth)."""
    return min(max_depth, base_depth + max(0, int(completed_runs)) // 8)


def advance_spider_frontier_and_waves(
    *,
    qualifying_finds: list[dict[str, Any]],
    frontier_queue: list[dict[str, Any]],
    visited_targets: set[str],
    completed_runs: int,
    frontier_batch_size: int = 10,
    max_waves: int = 3,
) -> dict[str, Any]:
    """Process a BFS frontier slice, enqueue outbound edges and propose bounded follow-up wave specs.

    Follow-up waves are emitted strictly as inert proposal dicts for Tessera queues; this function
    never runs network requests or creates an independent scheduler.
    """
    allowed_depth = compute_allowed_spider_depth(completed_runs)
    visited = set(visited_targets)
    remaining_frontier: list[dict[str, Any]] = []
    processed_nodes: list[dict[str, Any]] = []

    for node in frontier_queue:
        target = str(node["target"])
        depth = int(node.get("depth", 1))
        if target in visited:
            continue
        if len(processed_nodes) < frontier_batch_size and depth <= allowed_depth:
            visited.add(target)
            processed_nodes.append(node)
        else:
            remaining_frontier.append(node)

    # Enqueue outbound edges (author, readme_links, forks) from qualifying finds
    enqueued_edges = 0
    harvested_facets: list[str] = []
    proposed_wave_verbs: list[dict[str, Any]] = []

    for find in qualifying_finds:
        if not bool(find.get("on_topic", True)):
            continue
        repo = str(find["repo"])
        cur_depth = int(find.get("depth", 1))
        next_depth = cur_depth + 1
        if next_depth <= allowed_depth:
            author = repo.split("/")[0] if "/" in repo else ""
            candidates = []
            if author:
                candidates.append({"edge_type": "author_repos", "target": f"author:{author}", "depth": next_depth, "from_repo": repo})
            if int(find.get("forks", 0)) > 0:
                candidates.append({"edge_type": "repo_forks", "target": f"forks:{repo}", "depth": next_depth, "from_repo": repo})
            for linked in find.get("readme_outbound_repos", []):
                candidates.append({"edge_type": "readme_link", "target": f"repo:{linked}", "depth": next_depth, "from_repo": repo})
            for edge in candidates:
                if edge["target"] not in visited and all(n["target"] != edge["target"] for n in remaining_frontier):
                    remaining_frontier.append(edge)
                    enqueued_edges += 1

        for raw_topic in find.get("topics", []):
            topic = str(raw_topic).strip().lower()
            if not topic or topic in GENERIC_TOPIC_STOPLIST or len(topic) < 4:
                continue
            if topic not in harvested_facets:
                harvested_facets.append(topic)

    # Build up to max_waves bounded follow-up wave verb proposals
    for idx, facet in enumerate(harvested_facets[: max_waves * 2]):
        wave_no = (idx // 2) + 1
        if wave_no <= max_waves:
            proposed_wave_verbs.append({
                "wave": wave_no,
                "verb_template": "combinatorial-niche-spider.sweep-cells-and-spider-frontier",
                "facet": facet,
                "query": f'"{facet}" (toolkit OR editor OR specification) -interview -leetcode',
                "auto_enqueued": False,
            })

    # Anti-stall synonym mutation when zero qualifying finds surfaced
    stalled_mutations: list[str] = []
    if not qualifying_finds:
        for src, dst in SYNONYM_MUTATIONS.items():
            stalled_mutations.append(f"{src}->{dst.strip()}")

    return {
        "allowed_spider_depth": allowed_depth,
        "processed_frontier_count": len(processed_nodes),
        "enqueued_edge_count": enqueued_edges,
        "pending_frontier_count": len(remaining_frontier),
        "harvested_facets": harvested_facets,
        "proposed_wave_verbs": proposed_wave_verbs,
        "anti_stall_mutations": stalled_mutations,
        "frontier_queue": remaining_frontier,
        "visited_targets": sorted(visited),
    }


def evaluate_refresh_and_movers(
    known_repos: list[dict[str, Any]],
    fresh_observations: dict[str, dict[str, Any]],
    *,
    batch_limit: int = 18,
    star_surge_min: int = 5,
) -> dict[str, Any]:
    """Re-verify longest-unchecked repos first, surfacing star-surge movers and 404 gone rot."""
    ordered = sorted(known_repos, key=lambda r: float(r.get("last_checked_epoch", 0.0)))
    batch = ordered[:batch_limit]
    movers: list[dict[str, Any]] = []
    gone: list[str] = []
    checked = 0

    for prev in batch:
        repo = str(prev["repo"])
        obs = fresh_observations.get(repo)
        if obs is None:
            continue
        checked += 1
        status = int(obs.get("http_status", 200))
        if status == 404:
            gone.append(repo)
            continue
        star_delta = int(obs.get("stars", prev.get("stars", 0))) - int(prev.get("stars", 0))
        pushed_changed = str(obs.get("pushed_at", "")) != str(prev.get("pushed_at", ""))
        newly_archived = bool(obs.get("archived", False)) and not bool(prev.get("archived", False))
        if star_delta >= star_surge_min or pushed_changed or newly_archived:
            movers.append({
                "repo": repo,
                "star_delta": star_delta,
                "pushed_changed": pushed_changed,
                "newly_archived": newly_archived,
            })

    return {
        "checked_count": checked,
        "mover_count": len(movers),
        "gone_count": len(gone),
        "movers": movers,
        "gone_repos": gone,
    }
