"""1,000 solution methods / decomposition strategies (METH-0001..METH-1000)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

TOPOLOGIES_5: tuple[dict[str, Any], ...] = (
    {
        "slug": "single-verb",
        "max_workers": 1,
        "requires_distinct_reviewer": False,
        "splits_private_public": False,
        "reuses_prior_nouns_first": False,
    },
    {
        "slug": "map-reduce-split",
        "max_workers": 4,
        "requires_distinct_reviewer": True,
        "splits_private_public": True,
        "reuses_prior_nouns_first": False,
    },
    {
        "slug": "verify-cascade",
        "max_workers": 2,
        "requires_distinct_reviewer": True,
        "splits_private_public": False,
        "reuses_prior_nouns_first": True,
    },
    {
        "slug": "sira-reuse-first",
        "max_workers": 2,
        "requires_distinct_reviewer": True,
        "splits_private_public": True,
        "reuses_prior_nouns_first": True,
    },
    {
        "slug": "consensus-3-worker",
        "max_workers": 3,
        "requires_distinct_reviewer": True,
        "splits_private_public": False,
        "reuses_prior_nouns_first": True,
    },
)

COMPUTE_TIERS_6: tuple[dict[str, Any], ...] = (
    {
        "slug": "herma-rule",
        "is_cloud": False,
        "model_calls": 0,
        "typical_latency_ms": 2,
        "est_cost_usd": 0.0,
        "supports_offline": True,
    },
    {
        "slug": "local-llama-lora",
        "is_cloud": False,
        "model_calls": 1,
        "typical_latency_ms": 1400,
        "est_cost_usd": 0.0004,
        "supports_offline": True,
    },
    {
        "slug": "fireworks-multilora",
        "is_cloud": True,
        "model_calls": 2,
        "typical_latency_ms": 580,
        "est_cost_usd": 0.0012,
        "supports_offline": False,
    },
    {
        "slug": "baseten-2m-swarm",
        "is_cloud": True,
        "model_calls": 4,
        "typical_latency_ms": 2100,
        "est_cost_usd": 0.0038,
        "supports_offline": False,
    },
    {
        "slug": "modal-glimmer-30b",
        "is_cloud": True,
        "model_calls": 2,
        "typical_latency_ms": 3400,
        "est_cost_usd": 0.0065,
        "supports_offline": False,
    },
    {
        "slug": "muse-spark",
        "is_cloud": True,
        "model_calls": 2,
        "typical_latency_ms": 4200,
        "est_cost_usd": 0.0095,
        "supports_offline": False,
    },
)

VERIFICATION_GATES_8: tuple[str, ...] = (
    "deterministic-schema-and-hash",
    "distinct-reviewer-two-step",
    "paired-bootstrap-holdout",
    "rubric-judge-cross-family",
    "citation-statute-line-audit",
    "sandbox-container-replay",
    "privacy-redaction-zero-leak",
    "human-steward-final-gate",
)

PRIVACY_BOUNDARIES_5: tuple[dict[str, Any], ...] = (
    {
        "slug": "local-airgap-only",
        "allows_cloud_compute": False,
        "enforces_lane_split": False,
        "redacts_pii_before_egress": True,
    },
    {
        "slug": "split-private-vs-public",
        "allows_cloud_compute": True,
        "enforces_lane_split": True,
        "redacts_pii_before_egress": True,
    },
    {
        "slug": "surface-only-fenced",
        "allows_cloud_compute": True,
        "enforces_lane_split": False,
        "redacts_pii_before_egress": False,
    },
    {
        "slug": "synthetic-twin-redacted",
        "allows_cloud_compute": True,
        "enforces_lane_split": True,
        "redacts_pii_before_egress": True,
    },
    {
        "slug": "public-cited-statutes",
        "allows_cloud_compute": True,
        "enforces_lane_split": False,
        "redacts_pii_before_egress": False,
    },
)


def _valid_compute_gate_pairs_40() -> list[tuple[dict[str, Any], str]]:
    """Build 40 distinct (compute_tier, verification_gate) pairs (6x8=48 minus 8 incompatible pairs)."""
    excluded = {
        ("herma-rule", "paired-bootstrap-holdout"),
        ("herma-rule", "rubric-judge-cross-family"),
        ("local-llama-lora", "rubric-judge-cross-family"),
        ("fireworks-multilora", "paired-bootstrap-holdout"),
        ("baseten-2m-swarm", "human-steward-final-gate"),
        ("modal-glimmer-30b", "deterministic-schema-and-hash"),
        ("muse-spark", "deterministic-schema-and-hash"),
        ("muse-spark", "sandbox-container-replay"),
    }
    pairs: list[tuple[dict[str, Any], str]] = []
    for tier in COMPUTE_TIERS_6:
        for gate in VERIFICATION_GATES_8:
            if (tier["slug"], gate) not in excluded:
                pairs.append((tier, gate))
    if len(pairs) != 40:
        raise AssertionError(f"expected 40 valid pairs, got {len(pairs)}")
    return pairs


VALID_COMPUTE_GATE_PAIRS_40: tuple[tuple[dict[str, Any], str], ...] = tuple(
    _valid_compute_gate_pairs_40()
)


def generate_method(index: int) -> dict[str, Any]:
    """Deterministically generate solution method METH-0001..METH-1000 (5 x 5 x 40 = 1,000)."""
    if not (0 <= index < 1000):
        raise ValueError(f"method index {index} out of [0, 999]")
    topo_idx = index // 200
    rem = index % 200
    priv_idx = rem // 40
    pair_idx = rem % 40

    topo = TOPOLOGIES_5[topo_idx]
    priv = PRIVACY_BOUNDARIES_5[priv_idx]
    tier, gate = VALID_COMPUTE_GATE_PAIRS_40[pair_idx]

    meth_id = f"METH-{index + 1:04d}"
    distinct_reviewer = topo["requires_distinct_reviewer"] or gate in {
        "distinct-reviewer-two-step",
        "rubric-judge-cross-family",
        "human-steward-final-gate",
    }
    record: dict[str, Any] = {
        "method_id": meth_id,
        "index": index,
        "topology": topo["slug"],
        "compute_tier": tier["slug"],
        "verification_gate": gate,
        "privacy_boundary": priv["slug"],
        "is_cloud_compute": tier["is_cloud"],
        "supports_offline": tier["supports_offline"],
        "model_calls": tier["model_calls"] * (1 if tier["model_calls"] == 0 else topo["max_workers"]),
        "max_workers": topo["max_workers"],
        "requires_distinct_reviewer": distinct_reviewer,
        "enforces_lane_split": topo["splits_private_public"] or priv["enforces_lane_split"],
        "redacts_pii_before_egress": priv["redacts_pii_before_egress"],
        "reuses_prior_nouns_first": topo["reuses_prior_nouns_first"],
        "typical_latency_ms": tier["typical_latency_ms"],
        "estimated_cost_usd": round(tier["est_cost_usd"] * max(1, topo["max_workers"] / 2), 6),
        "lease_fencing_required": True,
        "lifecycle": "claim-do-report",
    }
    record["method_sha256"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return record


def generate_methods_1000() -> list[dict[str, Any]]:
    """Return all 1,000 indexed solution methods METH-0001..METH-1000."""
    return [generate_method(i) for i in range(1000)]
