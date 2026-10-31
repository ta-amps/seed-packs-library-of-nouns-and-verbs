"""1,000 multi-position stakeholders (STKH-0001..STKH-1000) and episode Task/Task-Object digester."""

from __future__ import annotations

import hashlib
import json
from typing import Any

STAKEHOLDER_POSITIONS_10: tuple[dict[str, Any], ...] = (
    {
        "slug": "frontline-caseworker",
        "focus": "preserves client voice, flags uncertainty, never automates safety or crisis care",
        "veto_axis": "human_care_boundary",
    },
    {
        "slug": "nonprofit-treasurer",
        "focus": "verifies exact arithmetic, zero unauthorized spend and audited receipt lineage",
        "veto_axis": "spend_and_receipt_audit",
    },
    {
        "slug": "privacy-hipaa-counsel",
        "focus": "blocks unredacted PII or regulated records from crossing into cloud inference",
        "veto_axis": "data_egress_privacy",
    },
    {
        "slug": "disability-access-auditor",
        "focus": "enforces WCAG 2.2 AA+, keyboard navigation, plain reading level and low-bandwidth access",
        "veto_axis": "accessibility_and_latency",
    },
    {
        "slug": "skeptical-municipal-funder",
        "focus": "requires statute line citations, pre-registered rubrics and independent two-step review",
        "veto_axis": "independent_verification",
    },
    {
        "slug": "volunteer-agent-donor",
        "focus": "protects donated token budgets via SIRA reuse, bounded leases and public-only lanes",
        "veto_axis": "donor_token_safety",
    },
    {
        "slug": "security-reviewer",
        "focus": "blocks prompt-injection escalation, untrusted code execution and cross-surface leaks",
        "veto_axis": "sandbox_and_acl_isolation",
    },
    {
        "slug": "impacted-community-advocate",
        "focus": "blocks automated eligibility denials, accusations and erasure of regional slang",
        "veto_axis": "dignity_and_non_accusation",
    },
    {
        "slug": "public-records-journalist",
        "focus": "verifies reproducible primary-source links, timestamps and explicit unknown reporting",
        "veto_axis": "source_provenance",
    },
    {
        "slug": "clinical-research-coordinator",
        "focus": "enforces denominator reconciliation, holdout leakage checks and protocol amendment tracking",
        "veto_axis": "statistical_and_protocol_hygiene",
    },
)

INSTITUTIONAL_MANDATES_10: tuple[str, ...] = (
    "zero-unconsented-pii-egress",
    "drafter-distinct-from-reviewer",
    "exact-statute-and-ledger-citation",
    "offline-degraded-continuity",
    "verbatim-slang-and-quote-fidelity",
    "bounded-volunteer-token-allowance",
    "wcag-22-aa-and-plain-language",
    "fenced-lease-idempotent-replay",
    "explicit-unknown-on-missing-data",
    "human-steward-final-decision",
)

STRICTNESS_TIERS_5: tuple[str, ...] = (
    "advisory-tag-only",
    "partition-required-on-mixed-data",
    "two-step-review-mandatory",
    "strict-zero-leak-veto",
    "airgap-and-steward-hard-gate",
)

AUTHORITY_SCOPES_2: tuple[str, ...] = (
    "surface-steward",
    "independent-auditor",
)


def generate_stakeholder(index: int) -> dict[str, Any]:
    """Deterministically generate stakeholder STKH-0001..STKH-1000 (10 x 10 x 5 x 2 = 1,000)."""
    if not (0 <= index < 1000):
        raise ValueError(f"stakeholder index {index} out of [0, 999]")
    pos_idx = index // 100
    rem1 = index % 100
    mand_idx = rem1 // 10
    rem2 = rem1 % 10
    strict_idx = rem2 // 2
    scope_idx = rem2 % 2

    pos = STAKEHOLDER_POSITIONS_10[pos_idx]
    stkh_id = f"STKH-{index + 1:04d}"
    record: dict[str, Any] = {
        "stakeholder_id": stkh_id,
        "index": index,
        "position": pos["slug"],
        "focus": pos["focus"],
        "veto_axis": pos["veto_axis"],
        "mandate": INSTITUTIONAL_MANDATES_10[mand_idx],
        "strictness": STRICTNESS_TIERS_5[strict_idx],
        "authority_scope": AUTHORITY_SCOPES_2[scope_idx],
    }
    record["stakeholder_sha256"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return record


def generate_stakeholders_1000() -> list[dict[str, Any]]:
    """Return all 1,000 indexed stakeholders STKH-0001..STKH-1000."""
    return [generate_stakeholder(i) for i in range(1000)]


def _canonical_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def evaluate_and_digest_episode(
    env: dict[str, Any],
    method: dict[str, Any],
    persona: dict[str, Any],
    stakeholder: dict[str, Any],
    episode_id: str | None = None,
) -> dict[str, Any]:
    """Stakeholder evaluates (env, method, persona) -> blocks/partitions/tags/links and digests Nouns & Verbs."""
    block_reasons: list[str] = []

    # 1. Connectivity & offline airgap hard check
    if env["connectivity"] == "offline_airgap" and not method["supports_offline"]:
        block_reasons.append("cloud_tier_cannot_run_in_offline_airgap")

    # 2. High-PII egress hard check
    if env["sensitivity"] == "high_pii_local_only" and method["is_cloud_compute"]:
        if not (method["enforces_lane_split"] and method["redacts_pii_before_egress"]):
            block_reasons.append("unsplit_cloud_egress_on_high_pii_data")
        elif stakeholder["strictness"] in {"strict-zero-leak-veto", "airgap-and-steward-hard-gate"}:
            block_reasons.append("stakeholder_veto_cloud_on_high_pii_airgap")

    # 3. Mixed/Regulated data requires lane partitioning when cloud compute is used
    needs_partition = False
    if env["requires_lane_split_for_cloud"] and method["is_cloud_compute"]:
        if method["enforces_lane_split"]:
            needs_partition = True
        elif stakeholder["strictness"] == "advisory-tag-only":
            needs_partition = True
        else:
            block_reasons.append("mixed_or_regulated_data_missing_private_public_split")

    # 4. Two-step distinct reviewer check for public-good / high-stakes / skeptical funder
    if (
        stakeholder["strictness"] in {"two-step-review-mandatory", "airgap-and-steward-hard-gate"}
        and not method["requires_distinct_reviewer"]
    ):
        block_reasons.append("missing_distinct_reviewer_two_step_gate")

    # 5. Latency / low-bandwidth accessibility check
    max_lat = min(env["latency_budget_ms"], persona["max_acceptable_latency_ms"])
    if method["typical_latency_ms"] > max_lat:
        block_reasons.append("method_latency_exceeds_operator_or_situational_budget")

    if block_reasons:
        verdict = "blocked"
        action = "block_and_emit_guardrail"
    elif needs_partition or method["enforces_lane_split"]:
        verdict = "approved_partitioned"
        action = "partition_private_local_and_public_donor_lanes"
    else:
        verdict = "approved_direct"
        action = "admit_scoped_candidate_with_human_boundary"

    # Digested Tessera Task Object (Noun) candidate
    noun_slug = f"{env['domain_slug']}.{method['verification_gate']}"
    noun_candidate = {
        "candidate_kind": "task_object_noun",
        "slug": noun_slug,
        "tessera_category": env["suggested_noun_category"],
        "title": f"Task object: {env['domain_title']} ({method['verification_gate']})",
        "input_artifact": env["input_artifact"],
        "privacy_boundary": (
            "split-private-vs-public" if verdict == "approved_partitioned" else method["privacy_boundary"]
        ),
        "human_only": env["human_only_boundary"],
        "visibility_scope": "surface_only",
        "facet_tags": [
            f"category:{env['suggested_noun_category']}",
            f"sector:{env['sector']}",
            f"sensitivity:{env['sensitivity']}",
            f"stakeholder:{stakeholder['position']}",
            "status:quarantined",
        ],
    }
    noun_candidate["content_sha256"] = _canonical_sha256(noun_candidate)

    # Digested Tessera Task (Verb) candidate
    verb_slug = f"{env['domain_slug']}.{method['topology']}"
    verb_candidate = {
        "candidate_kind": "task_verb",
        "slug": verb_slug,
        "tessera_category": env["suggested_verb_category"],
        "lifecycle": "claim-do-report",
        "title": f"Task: {env['domain_title']} via {method['topology']}",
        "topology": method["topology"],
        "compute_tier": "local-llama-lora" if env["connectivity"] == "offline_airgap" else method["compute_tier"],
        "verification_gate": method["verification_gate"],
        "requires_distinct_reviewer": True if verdict != "approved_direct" else method["requires_distinct_reviewer"],
        "human_only": env["human_only_boundary"],
        "linked_noun_sha256": noun_candidate["content_sha256"],
        "visibility_scope": "surface_only",
    }
    verb_candidate["content_sha256"] = _canonical_sha256(verb_candidate)

    partition_plan = None
    if verdict == "approved_partitioned":
        partition_plan = {
            "private_local_lane": {
                "compute": "local-kit-or-herma-rule",
                "data_scope": env["input_artifact"],
                "policy": "Sensitive files remain on the requester's local machine; zero raw cloud egress.",
            },
            "public_donor_lane": {
                "compute": method["compute_tier"],
                "data_scope": "public statutes, enacted budgets, published bulletins and synthetic tests",
                "policy": "Authorized volunteer workers claim, do and report cited public sub-tasks under distinct review.",
            },
        }

    ep_code = episode_id or f"EP-{env['env_id']}-{method['method_id']}-{persona['persona_id']}-{stakeholder['stakeholder_id']}"
    result: dict[str, Any] = {
        "episode_id": ep_code,
        "tuple": {
            "env_id": env["env_id"],
            "method_id": method["method_id"],
            "persona_id": persona["persona_id"],
            "stakeholder_id": stakeholder["stakeholder_id"],
        },
        "verdict": verdict,
        "stakeholder_action": action,
        "block_reasons": block_reasons,
        "partition_plan": partition_plan,
        "human_only": env["human_only_boundary"],
        "digested_noun": noun_candidate,
        "digested_verb": verb_candidate,
    }
    result["episode_sha256"] = _canonical_sha256(result)
    return result
