"""Decompose public AI repository metadata and READMEs into Task (verb) and Task Object (noun) signatures."""

from __future__ import annotations

import re
from typing import Any, Sequence

PROVENANCE_TAG = "public_repo_metadata_scan_2026_10_30"

VERB_CATEGORY_MAP = {
    "build": "verb.compile_dag",
    "run_serve": "verb.solve_draft",
    "test_check": "verb.verify_gate",
    "deploy": "verb.compile_dag",
    "data_processing": "verb.ingest",
    "agent_tool": "verb.probe_source",
    "scheduled": "verb.fetch_feed",
    "other": "verb.solve_draft",
}

NOUN_CATEGORY_MAP = {
    "docs": "noun.public_source",
    "code": "noun.code_node",
    "tool": "noun.mcp_server",
    "model": "noun.model_spec",
    "prompt": "noun.prompt_shim",
    "dataset": "noun.feed_source",
    "asset": "noun.scene_recipe",
    "config": "noun.shim_provision",
    "test_evaluation": "noun.eval_run",
}


def sanitize_text(text: str) -> str:
    """Replace em-dashes and collapse whitespace for clean plain-ASCII-friendly records."""
    cleaned = text.replace("\u2014", " -- ").replace("\u2013", "-")
    return re.sub(r"\s+", " ", cleaned).strip()


def _slug(raw: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return s[:48] or "item"


def decompose_repository(raw: dict[str, Any]) -> dict[str, Any]:
    """Decompose a raw repository scan dictionary into a searchable Task & Task-Object record."""
    repo = str(raw["repo"]).strip()
    track = sanitize_text(str(raw.get("track") or "Unspecified"))
    domain = sanitize_text(str(raw.get("domain") or "General AI Applications"))
    meta_stack = sorted({str(x).strip() for x in raw.get("meta_stack", []) if str(x).strip()})

    readme_title = sanitize_text(str(raw.get("readme_title") or ""))
    readme_para = sanitize_text(str(raw.get("readme_first_paragraph") or ""))
    if readme_para:
        summary = readme_para[:420]
    elif readme_title:
        summary = f"{readme_title}: {domain} project ({track})."
    else:
        stack_note = f" using {', '.join(meta_stack)}" if meta_stack else ""
        summary = f"Public repository {repo} in {domain} ({track}){stack_note}."

    # Extract Tasks (verb signatures)
    tasks: list[dict[str, Any]] = []
    seen_tasks: set[tuple[str, str]] = set()
    raw_verbs: Sequence[dict[str, Any]] = raw.get("verb_items") or []
    for item in raw_verbs:
        vcat = str(item.get("category") or "other")
        vname = sanitize_text(str(item.get("name") or vcat))
        vkind = str(item.get("kind") or "command")
        mapped = VERB_CATEGORY_MAP.get(vcat, "verb.solve_draft")
        dedup_key = (mapped, _slug(vname))
        if dedup_key in seen_tasks:
            continue
        seen_tasks.add(dedup_key)
        tasks.append({
            "task_id": f"task.{_slug(vname)}",
            "verb_category": mapped,
            "source_category": vcat,
            "surface_kind": vkind,
            "name": vname[:80],
            "verification_status": "candidate_unverified",
        })
        if len(tasks) >= 16:
            break

    # Fall back to category counts when detailed items are absent
    verb_counts: dict[str, int] = raw.get("verb_counts") or {}
    for vcat, cnt in sorted(verb_counts.items()):
        if int(cnt or 0) <= 0:
            continue
        mapped = VERB_CATEGORY_MAP.get(vcat, "verb.solve_draft")
        dedup_key = (mapped, vcat)
        if not any(t["source_category"] == vcat for t in tasks) and dedup_key not in seen_tasks:
            seen_tasks.add(dedup_key)
            tasks.append({
                "task_id": f"task.{_slug(vcat)}",
                "verb_category": mapped,
                "source_category": vcat,
                "surface_kind": "aggregate_count",
                "name": f"{vcat} ({int(cnt)} entrypoints)",
                "verification_status": "candidate_unverified",
            })

    if not tasks:
        # Honest minimal metadata task placeholder when clone/scan had no detected entrypoints
        tasks.append({
            "task_id": "task.inspect-repository-metadata",
            "verb_category": "verb.probe_source",
            "source_category": "metadata_only",
            "surface_kind": "directory_listing",
            "name": "inspect public repository metadata",
            "verification_status": "candidate_unverified",
        })

    # Extract Task Objects (noun signatures)
    task_objects: list[dict[str, Any]] = []
    noun_counts: dict[str, int] = raw.get("noun_counts") or {}
    for ncat, mapped_noun in sorted(NOUN_CATEGORY_MAP.items()):
        cnt = int(noun_counts.get(ncat, 0) or 0)
        if cnt > 0:
            task_objects.append({
                "object_id": f"object.{ncat}",
                "noun_category": mapped_noun,
                "source_facet": ncat,
                "count": cnt,
            })

    for stack_tag in meta_stack:
        if stack_tag in ("sam", "weights", "llama", "glimmer", "spark", "meta_api"):
            if not any(o["object_id"] == f"object.stack-{_slug(stack_tag)}" for o in task_objects):
                task_objects.append({
                    "object_id": f"object.stack-{_slug(stack_tag)}",
                    "noun_category": "noun.model_spec",
                    "source_facet": f"meta_stack:{stack_tag}",
                    "count": 1,
                })

    if not task_objects:
        task_objects.append({
            "object_id": "object.public-listing",
            "noun_category": "noun.public_source",
            "source_facet": "directory_entry",
            "count": 1,
        })

    return {
        "repo": repo,
        "url": str(raw.get("url") or f"https://github.com/{repo}"),
        "track": track,
        "domain": domain,
        "meta_stack": meta_stack,
        "primary_language": str(raw.get("primary_language") or ""),
        "license": str(raw.get("license") or ""),
        "scan_status": str(raw.get("scan_status") or "metadata_only"),
        "head_sha": str(raw.get("head_sha") or ""),
        "tests_present": bool(raw.get("tests_present", False)),
        "mcp_adopted": bool(raw.get("mcp_adopted", False)),
        "tasks": tasks,
        "task_objects": task_objects,
        "summary": summary,
        "provenance": PROVENANCE_TAG,
    }
