"""8-axis 0-100 candidate evaluator, query-family yield benchmark and independent review gate."""

from __future__ import annotations

import math
from typing import Any

PERMISSIVE_LICENSE_SCORES: dict[str, float] = {
    "CC0-1.0": 100.0,
    "MIT": 98.0,
    "Apache-2.0": 95.0,
    "BSD-3-Clause": 94.0,
    "BSD-2-Clause": 94.0,
    "ISC": 94.0,
    "CC-BY-4.0": 88.0,
    "MPL-2.0": 75.0,
    "LGPL-3.0": 65.0,
    "GPL-3.0": 55.0,
}

FALSE_POSITIVE_PHRASES: tuple[str, ...] = (
    "low-level design interview",
    "system design interview",
    "leetcode solutions",
    "coding interview prep",
    "iptv player",
    "homework assignment",
)


def _clamp100(val: float) -> float:
    return round(max(0.0, min(100.0, val)), 2)


def score_candidate_axes(candidate: dict[str, Any]) -> dict[str, Any]:
    """Score a discovered repository on 8 distinct 0-100 axes with an explicit on_topic gate."""
    text = f"{candidate.get('repo', '')} {candidate.get('description', '')} {' '.join(candidate.get('topics', []))}".lower()
    domain_terms = [str(t).lower() for t in candidate.get("domain_terms", []) if str(t).strip()]

    has_false_positive = any(fp in text for fp in FALSE_POSITIVE_PHRASES)
    matched_terms = sum(1 for t in domain_terms if t in text)
    term_ratio = (matched_terms / len(domain_terms)) if domain_terms else 0.5
    on_topic = (not has_false_positive) and (matched_terms > 0 or not domain_terms) and not bool(candidate.get("is_bare_demo", False))

    stars = max(0, int(candidate.get("stars", 0)))
    forks = max(0, int(candidate.get("forks", 0)))
    age_days = max(1, int(candidate.get("age_days", 30)))
    days_since_push = max(0, int(candidate.get("days_since_push", 14)))
    rediscoveries = max(1, int(candidate.get("independent_query_hits", 1)))
    spdx = str(candidate.get("license") or "NONE")
    has_readme_docs = bool(candidate.get("has_docs_or_templates", True))

    relevance = _clamp100((35.0 + 65.0 * term_ratio) if on_topic else 8.0)
    popularity = _clamp100(22.0 * math.log10(stars + 1.0))
    commonality = _clamp100(min(100.0, 25.0 * rediscoveries))
    usefulness = _clamp100(
        (45.0 if has_readme_docs else 15.0)
        + (25.0 if spdx in PERMISSIVE_LICENSE_SCORES else 0.0)
        + (30.0 * term_ratio if on_topic else 0.0)
    )
    velocity_per_month = (stars / age_days) * 30.0
    value = _clamp100(35.0 * math.log10(velocity_per_month + 1.0) + 25.0 * math.log10(forks + 1.0) + 0.35 * usefulness)
    freeness = _clamp100(PERMISSIVE_LICENSE_SCORES.get(spdx, 0.0))
    activity = _clamp100(100.0 * math.exp(-days_since_push / 90.0))
    rarity = _clamp100(100.0 - popularity if on_topic else 0.0)

    composite = _clamp100(
        0.24 * relevance
        + 0.22 * usefulness
        + 0.16 * value
        + 0.16 * freeness
        + 0.10 * commonality
        + 0.07 * activity
        + 0.05 * rarity
    ) if on_topic else 0.0

    return {
        "repo": str(candidate.get("repo", "")),
        "on_topic": on_topic,
        "axes": {
            "relevance": relevance,
            "popularity": popularity,
            "commonality": commonality,
            "usefulness": usefulness,
            "value": value,
            "freeness": freeness,
            "activity": activity,
            "rarity": rarity,
        },
        "composite": composite,
    }


def benchmark_query_families(
    query_logs: list[dict[str, Any]],
    *,
    retire_below_yield: float = 0.05,
    champion_min_yield: float = 0.60,
) -> dict[str, Any]:
    """Benchmark query families by on-topic yield, promoting champions and retiring noisy wave tracks."""
    by_family: dict[str, dict[str, int]] = {}
    champions: list[str] = []

    for row in query_logs:
        fam = str(row["family"])
        hits = max(0, int(row.get("hits", 0)))
        on_topic = max(0, int(row.get("on_topic_hits", 0)))
        agg = by_family.setdefault(fam, {"runs": 0, "hits": 0, "on_topic_hits": 0})
        agg["runs"] += 1
        agg["hits"] += hits
        agg["on_topic_hits"] += on_topic
        if hits >= 3 and (on_topic / hits) >= champion_min_yield:
            champions.append(str(row["query"]))

    families_out: dict[str, dict[str, Any]] = {}
    retired_families: list[str] = []
    for fam, agg in sorted(by_family.items()):
        yield_rate = round(agg["on_topic_hits"] / agg["hits"], 4) if agg["hits"] > 0 else 0.0
        retire = agg["hits"] >= 10 and yield_rate < retire_below_yield
        if retire:
            retired_families.append(fam)
        families_out[fam] = {
            "runs": agg["runs"],
            "hits": agg["hits"],
            "on_topic_hits": agg["on_topic_hits"],
            "on_topic_yield": yield_rate,
            "retired_for_noise": retire,
        }

    return {
        "families": families_out,
        "champion_queries": sorted(set(champions)),
        "retired_families": retired_families,
    }


def verify_curated_admission_independently(
    *,
    curator_worker_id: str,
    curator_key_id: str,
    reviewer_worker_id: str,
    reviewer_key_id: str,
    scored_candidates: list[dict[str, Any]],
    min_freeness: float = 85.0,
    min_usefulness: float = 65.0,
) -> dict[str, Any]:
    """Enforce distinct reviewer separation and open-license/on-topic gates before seed-pack curation."""
    if curator_worker_id == reviewer_worker_id or curator_key_id == reviewer_key_id:
        return {
            "approved": False,
            "status_code": 409,
            "reason": "curator_cannot_self_approve_admission",
            "admitted_repos": [],
        }

    admitted: list[str] = []
    rejected: list[str] = []
    for item in scored_candidates:
        axes = item["axes"]
        if item["on_topic"] and axes["freeness"] >= min_freeness and axes["usefulness"] >= min_usefulness:
            admitted.append(item["repo"])
        else:
            rejected.append(item["repo"])

    return {
        "approved": len(admitted) > 0,
        "status_code": 200,
        "reason": "verified_by_distinct_reviewer",
        "admitted_repos": admitted,
        "rejected_repos": rejected,
    }
