"""Compile post-cutoff Task Objects into LoRA SFT pairs and verify holdout n-gram disjointness."""

from __future__ import annotations

import re
from typing import Any, Sequence

WORD_RE = re.compile(r"[a-z0-9_]+")


def _ngrams(text: str, n: int = 4) -> set[tuple[str, ...]]:
    toks = WORD_RE.findall(text.lower())
    if len(toks) < n:
        return {tuple(toks)} if toks else set()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def compile_post_cutoff_pairs(task_objects: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compile verified post-cutoff Task Objects into direct, supersession and abstention training pairs."""
    pairs: list[dict[str, Any]] = []
    for obj in task_objects:
        oid = str(obj["id"])
        subject = str(obj["subject"]).strip()
        eff = str(obj["effective_date"]).strip()
        fact = str(obj["canonical_fact"]).strip()
        old = str(obj.get("superseded_claim") or "").strip()
        boundary = str(obj.get("scope_boundary") or "unspecified parameters outside the pinned specification").strip()

        pairs.append({
            "pair_id": f"{oid}:direct",
            "source_object_id": oid,
            "pair_kind": "direct_fact",
            "prompt": f"As of {eff}, what is the verified specification for {subject}?",
            "response": f"As of {eff}, {fact} (source pin: {oid}).",
        })
        if old:
            pairs.append({
                "pair_id": f"{oid}:supersession",
                "source_object_id": oid,
                "pair_kind": "supersession_guard",
                "prompt": f"Does {subject} still follow the earlier rule ({old})?",
                "response": f"No. Effective {eff}, that earlier rule was superseded. Current behavior: {fact} (source pin: {oid}).",
            })
        pairs.append({
            "pair_id": f"{oid}:abstention",
            "source_object_id": oid,
            "pair_kind": "scope_abstention",
            "prompt": f"Based on {subject}, what can be concluded about {boundary}?",
            "response": f"Abstain: {oid} defines {subject} as of {eff}, and does not establish claims about {boundary}.",
        })
    return pairs


def check_holdout_disjointness(
    train_pairs: Sequence[dict[str, Any]],
    holdout_prompts: Sequence[str],
    *,
    ngram_n: int = 4,
    max_jaccard: float = 0.35,
) -> dict[str, Any]:
    """Verify training prompts do not leak pre-registered holdout prompts via exact or n-gram overlap."""
    collisions: list[dict[str, Any]] = []
    worst_jaccard = 0.0

    train_grams = [(p["pair_id"], str(p["prompt"]).strip().lower(), _ngrams(str(p["prompt"]), ngram_n)) for p in train_pairs]
    for h_idx, hp in enumerate(holdout_prompts):
        h_clean = hp.strip().lower()
        h_set = _ngrams(hp, ngram_n)
        for pid, t_clean, t_set in train_grams:
            exact = h_clean == t_clean
            union = len(h_set | t_set)
            jacc = (len(h_set & t_set) / union) if union > 0 else 0.0
            if jacc > worst_jaccard:
                worst_jaccard = jacc
            if exact or jacc > max_jaccard:
                collisions.append({
                    "pair_id": pid,
                    "holdout_index": h_idx,
                    "exact_match": exact,
                    "ngram_jaccard": round(jacc, 4),
                })

    return {
        "train_pair_count": len(train_pairs),
        "holdout_count": len(holdout_prompts),
        "max_observed_jaccard": round(worst_jaccard, 4),
        "max_allowed_jaccard": max_jaccard,
        "disjoint": len(collisions) == 0,
        "collisions": collisions,
    }
