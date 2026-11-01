"""Bounded 1-hop seed digestion into atomic child verbs and task_objects compatible with /q/submit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .grid_config import NodeGrid
from .ontology_engine import shingle_jaccard_similarity


@dataclass(frozen=True)
class VerbEnvelope:
    """Universal task envelope carrying lineage, generation_depth, search_hints and facet_axes."""

    task_id: str
    verb_kind: str
    title: str
    prompt: str
    parent_task_id: str | None
    source_task_id: str
    generation_depth: int
    input_pins: tuple[str, ...]
    search_hints: dict[str, Any]
    facet_axes: dict[str, str]


def build_search_hints(
    *,
    intent_signature: str,
    keywords: Sequence[str],
    phrases: Sequence[str],
    synonyms: Sequence[str],
    facet_axes: Mapping[str, str],
) -> dict[str, Any]:
    """Construct normalized search_hints with facet_axes for /q/submit discovery indexing."""
    axes = {str(k).strip(): str(v).strip() for k, v in facet_axes.items() if str(k).strip()}
    return {
        "intent_signature": str(intent_signature).strip(),
        "search_keywords": list(dict.fromkeys(str(x).strip().lower() for x in keywords if str(x).strip())),
        "search_phrases": list(dict.fromkeys(str(x).strip() for x in phrases if str(x).strip())),
        "semantic_synonyms": list(dict.fromkeys(str(x).strip().lower() for x in synonyms if str(x).strip())),
        "facet_axes": axes,
    }


def _deterministic_child_task_id(source_task_id: str, parent_task_id: str, depth: int, slug: str, prefix_len: int) -> str:
    payload = f"{source_task_id}:{parent_task_id}:g{depth}:{slug}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:prefix_len]
    return f"task_g{depth}_{slug}_{digest}"


def digest_seed_one_hop(
    seed_noun: Mapping[str, Any],
    parent_envelope: VerbEnvelope,
    *,
    branch_candidates: Sequence[Mapping[str, Any]],
    agent_id: str,
    worker_uuid: str,
    fencing_token: str,
    grid: NodeGrid,
    cell: Mapping[str, Any] | None = None,
    existing_signatures: Sequence[str] = (),
) -> dict[str, Any]:
    """Digest one seed noun + parent VerbEnvelope into generation_depth + 1 atomic verbs and task_objects."""
    clamped = grid.clamp_cell(cell)
    max_depth = int(clamped["max_generation_depth"])
    max_children = int(clamped["max_children_per_hop"])
    dedup_threshold = float(clamped["dedup_jaccard_threshold"])
    shingle_size = grid.default_shingle_size
    prefix_len = grid.sha256_prefix_chars

    root_source_id = parent_envelope.source_task_id or parent_envelope.task_id
    current_depth = int(parent_envelope.generation_depth)
    next_depth = current_depth + 1

    seed_key = str(seed_noun.get("seed_key") or seed_noun.get("slug") or "seed_slice").strip()
    seed_category = str(seed_noun.get("category") or "noun.seed_hypothesis").strip()
    seed_title = str(seed_noun.get("title") or seed_key).strip()

    seen_texts = [str(sig) for sig in existing_signatures if str(sig).strip()]
    admitted_branches: list[Mapping[str, Any]] = []
    skipped_duplicates: list[str] = []

    if current_depth < max_depth:
        for cand in branch_candidates:
            if len(admitted_branches) >= max_children:
                break
            cand_slug = str(cand["slug"]).strip()
            cand_title = str(cand["title"]).strip()
            cand_sig_text = f"{cand_slug.replace('-', ' ').replace('_', ' ')} {cand_title}"
            is_dup = any(
                shingle_jaccard_similarity(cand_sig_text, prior, shingle_size=shingle_size) >= dedup_threshold
                for prior in seen_texts
            )
            if is_dup:
                skipped_duplicates.append(cand_slug)
                continue
            seen_texts.append(cand_sig_text)
            admitted_branches.append(cand)

    depth_cap_reached = current_depth >= max_depth
    child_envelopes: list[VerbEnvelope] = []
    queued_verbs: list[dict[str, Any]] = []
    proposed_verbs: list[dict[str, Any]] = []
    task_objects: list[dict[str, Any]] = []
    proposed_nouns: list[dict[str, Any]] = []

    parent_facets = dict(parent_envelope.facet_axes)
    slice_hints = build_search_hints(
        intent_signature=f"ontology_digest:{seed_key}:g{current_depth}",
        keywords=[seed_key, *parent_envelope.search_hints.get("search_keywords", [])],
        phrases=[seed_title],
        synonyms=parent_envelope.search_hints.get("semantic_synonyms", []),
        facet_axes=parent_facets,
    )

    # Emit primary task_object recording the digested ontology slice at current_depth
    slice_payload = {
        "seed_key": seed_key,
        "digested_from_task_id": parent_envelope.task_id,
        "source_task_id": root_source_id,
        "generation_depth": current_depth,
        "next_generation_depth": next_depth if not depth_cap_reached else current_depth,
        "depth_cap_reached": depth_cap_reached,
        "admitted_branch_slugs": [str(b["slug"]) for b in admitted_branches],
        "skipped_duplicate_slugs": skipped_duplicates,
    }
    slice_sha = hashlib.sha256(
        json.dumps(slice_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    slice_obj_key = f"ontology_slice_{seed_key.replace('.', '_')}_g{current_depth}"
    task_objects.append({
        "object_key": slice_obj_key,
        "category": seed_category,
        "summary": f"Digested polyhierarchical slice {seed_title} at generation_depth={current_depth}",
        "payload": slice_payload,
        "payload_sha256": slice_sha,
        "parent_task_id": parent_envelope.parent_task_id,
        "source_task_id": root_source_id,
        "generation_depth": current_depth,
        "search_hints": slice_hints,
        "facet_axes": parent_facets,
    })

    for branch in admitted_branches:
        b_slug = str(branch["slug"]).strip()
        b_title = str(branch["title"]).strip()
        b_verb_kind = str(branch.get("verb_kind", "verb.expand_seed")).strip()
        b_noun_cat = str(branch.get("noun_category", "noun.seed_hypothesis")).strip()
        b_prompt = str(branch.get("prompt") or f"Expand and verify capability slice: {b_title}").strip()
        b_parents = [str(p).strip() for p in branch.get("parent_ids", ()) if str(p).strip()]
        merged_facets = {
            **parent_facets,
            **{str(k): str(v) for k, v in dict(branch.get("facet_axes", {})).items()},
            "poly_parents": ",".join(b_parents),
        }
        b_hints = build_search_hints(
            intent_signature=str(branch.get("intent_signature") or f"{b_verb_kind}:{b_slug}"),
            keywords=[b_slug, *b_parents, *branch.get("keywords", ())],
            phrases=[b_title, *branch.get("phrases", ())],
            synonyms=list(branch.get("synonyms", ())),
            facet_axes=merged_facets,
        )
        child_id = _deterministic_child_task_id(
            root_source_id,
            parent_envelope.task_id,
            next_depth,
            b_slug,
            prefix_len,
        )
        env = VerbEnvelope(
            task_id=child_id,
            verb_kind=b_verb_kind,
            title=b_title,
            prompt=b_prompt,
            parent_task_id=parent_envelope.task_id,
            source_task_id=root_source_id,
            generation_depth=next_depth,
            input_pins=(*parent_envelope.input_pins, slice_obj_key),
            search_hints=b_hints,
            facet_axes=merged_facets,
        )
        child_envelopes.append(env)

        verb_entry = {
            "task_id": child_id,
            "tier": str(branch.get("tier", "public_general")),
            "verb_kind": b_verb_kind,
            "kind": b_verb_kind,
            "title": b_title,
            "prompt": b_prompt,
            "parent_task_id": parent_envelope.task_id,
            "source_task_id": root_source_id,
            "generation_depth": next_depth,
            "input_pins": list(env.input_pins),
            "search_hints": b_hints,
            "facet_axes": merged_facets,
        }
        queued_verbs.append(verb_entry)
        proposed_verbs.append({
            "kind": b_verb_kind,
            "title": b_title,
            "outcome": f"Verified polyhierarchical child slice for {b_slug} at generation {next_depth}.",
            "why": f"Bounded +1 hop expansion from {parent_envelope.task_id} across parents {b_parents}.",
            "priority": int(branch.get("priority", grid.default_priority)),
        })
        proposed_nouns.append({
            "category": b_noun_cat,
            "role": str(branch.get("noun_role", "capability_slice")),
            "title": b_title,
            "why": f"Captures reusable capability node and I/O contracts for {b_slug}.",
        })

        branch_obj_payload = {
            "node_id": b_slug,
            "title": b_title,
            "parent_ids": b_parents,
            "facet_axes": merged_facets,
            "generation_depth": next_depth,
        }
        task_objects.append({
            "object_key": f"seed_node_{b_slug.replace('-', '_')}_g{next_depth}",
            "category": b_noun_cat,
            "summary": b_title,
            "payload": branch_obj_payload,
            "parent_task_id": parent_envelope.task_id,
            "source_task_id": root_source_id,
            "generation_depth": next_depth,
            "search_hints": b_hints,
            "facet_axes": merged_facets,
        })

    submit_payload = {
        "agent_id": agent_id,
        "worker_uuid": worker_uuid,
        "task_id": parent_envelope.task_id,
        "fencing_token": fencing_token,
        "summary": (
            f"Digested {seed_key} (gen {current_depth} -> gen {next_depth}): "
            f"{len(queued_verbs)} atomic child verbs, {len(task_objects)} task_objects"
        ),
        "parent_task_id": parent_envelope.parent_task_id,
        "source_task_id": root_source_id,
        "generation_depth": current_depth,
        "next_generation_depth": next_depth if not depth_cap_reached else current_depth,
        "depth_cap_reached": depth_cap_reached,
        "task_objects": task_objects,
        "queued_verbs": queued_verbs,
        "verbs": queued_verbs,
        "proposed_verbs": proposed_verbs,
        "proposed_nouns": proposed_nouns,
        "search_hints": slice_hints,
        "facet_axes": parent_facets,
    }
    return {
        "submit_payload": submit_payload,
        "child_envelopes": child_envelopes,
        "skipped_duplicates": skipped_duplicates,
        "depth_cap_reached": depth_cap_reached,
    }
