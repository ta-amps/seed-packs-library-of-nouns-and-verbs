"""Deterministic encapsulation and canonical SHA-256 digesting for the Feed task object."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

REQUIRED_HARNESS_SLUGS = (
    "profile.harness-square",
    "profile.opencode",
    "profile.pi",
    "profile.muse-code",
)


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def encapsulate_feed(
    *,
    feed_id: str,
    as_of_date: str,
    profiles: Sequence[dict[str, Any]],
    sources: Sequence[dict[str, Any]],
    benchmarks: Sequence[dict[str, Any]],
    recommendations: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Encapsulate child harness profiles, sources, benchmarks and recommendations into one Feed digest."""
    profile_entries = sorted(
        [{"slug": str(p["slug"]), "sha256": sha256_obj(p), "harness_id": str(p["harness_id"])} for p in profiles],
        key=lambda x: x["slug"],
    )
    present_slugs = {p["slug"] for p in profile_entries}
    missing = [req for req in REQUIRED_HARNESS_SLUGS if req not in present_slugs]
    if missing:
        raise ValueError(f"encapsulated feed misses required harness profiles: {missing}")

    source_entries = sorted(
        [{"slug": str(s["slug"]), "sha256": sha256_obj(s)} for s in sources],
        key=lambda x: x["slug"],
    )
    bench_entries = sorted(
        [{"slug": str(b["slug"]), "sha256": sha256_obj(b), "harness_id": str(b["harness_id"])} for b in benchmarks],
        key=lambda x: x["slug"],
    )
    rec_entries = sorted(
        [{"slug": str(r["slug"]), "sha256": sha256_obj(r)} for r in recommendations],
        key=lambda x: x["slug"],
    )

    manifest_core = {
        "feed_id": feed_id,
        "as_of_date": as_of_date,
        "profiles": profile_entries,
        "sources": source_entries,
        "benchmarks": bench_entries,
        "recommendations": rec_entries,
    }
    digest = sha256_obj(manifest_core)
    return {
        **manifest_core,
        "child_count": len(profile_entries) + len(source_entries) + len(bench_entries) + len(rec_entries),
        "feed_digest_sha256": digest,
    }
