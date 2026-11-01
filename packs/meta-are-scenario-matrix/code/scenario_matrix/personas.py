"""1,000 operator and domain personas (PERS-0001..PERS-1000): 5 skills x 5 harnesses x 5 styles x 8 profiles."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SKILL_LEVELS_5: tuple[str, ...] = (
    "grassroots-novice",
    "frontline-coordinator",
    "operations-analyst",
    "staff-civic-engineer",
    "principal-ml-architect",
)

HARNESSES_5: tuple[str, ...] = (
    "Claude Code",
    "Muse Code",
    "OpenCode",
    "Pi",
    "Harness Square",
)

COMMUNICATION_STYLES_5: tuple[str, ...] = (
    "plain-vernacular-brief",
    "checklist-step-by-step",
    "multilingual-code-switching",
    "audit-citation-strict",
    "compact-diff-telemetry",
)

RISK_ACCESSIBILITY_PROFILES_8: tuple[dict[str, Any], ...] = (
    {
        "risk_tolerance": "zero-egress-conservative",
        "accessibility_need": "screen-reader-wcag-aaa",
        "strict_airgap_preference": True,
        "requires_plain_structure": True,
        "max_acceptable_latency_ms": 15000,
    },
    {
        "risk_tolerance": "zero-egress-conservative",
        "accessibility_need": "low-bandwidth-text-only",
        "strict_airgap_preference": True,
        "requires_plain_structure": True,
        "max_acceptable_latency_ms": 5000,
    },
    {
        "risk_tolerance": "human-in-the-loop-cautious",
        "accessibility_need": "dyslexia-plain-reading-grade6",
        "strict_airgap_preference": False,
        "requires_plain_structure": True,
        "max_acceptable_latency_ms": 18000,
    },
    {
        "risk_tolerance": "human-in-the-loop-cautious",
        "accessibility_need": "captions-and-deaf-hard-of-hearing",
        "strict_airgap_preference": False,
        "requires_plain_structure": True,
        "max_acceptable_latency_ms": 20000,
    },
    {
        "risk_tolerance": "verified-automation-balanced",
        "accessibility_need": "motor-keyboard-only-shortcuts",
        "strict_airgap_preference": False,
        "requires_plain_structure": False,
        "max_acceptable_latency_ms": 25000,
    },
    {
        "risk_tolerance": "verified-automation-balanced",
        "accessibility_need": "high-contrast-field-tablet",
        "strict_airgap_preference": False,
        "requires_plain_structure": False,
        "max_acceptable_latency_ms": 12000,
    },
    {
        "risk_tolerance": "verified-automation-balanced",
        "accessibility_need": "multilingual-es-ht-zh-ar",
        "strict_airgap_preference": False,
        "requires_plain_structure": True,
        "max_acceptable_latency_ms": 22000,
    },
    {
        "risk_tolerance": "rapid-triage-high-throughput",
        "accessibility_need": "standard-desktop-workspace",
        "strict_airgap_preference": False,
        "requires_plain_structure": False,
        "max_acceptable_latency_ms": 35000,
    },
)


def generate_persona(index: int) -> dict[str, Any]:
    """Deterministically generate operator/domain persona PERS-0001..PERS-1000 (5x5x5x8 = 1,000)."""
    if not (0 <= index < 1000):
        raise ValueError(f"persona index {index} out of [0, 999]")
    skill_idx = index // 200
    rem1 = index % 200
    harness_idx = rem1 // 40
    rem2 = rem1 % 40
    style_idx = rem2 // 8
    prof_idx = rem2 % 8

    prof = RISK_ACCESSIBILITY_PROFILES_8[prof_idx]
    pers_id = f"PERS-{index + 1:04d}"
    record: dict[str, Any] = {
        "persona_id": pers_id,
        "index": index,
        "skill_level": SKILL_LEVELS_5[skill_idx],
        "harness_preference": HARNESSES_5[harness_idx],
        "communication_style": COMMUNICATION_STYLES_5[style_idx],
        "risk_tolerance": prof["risk_tolerance"],
        "accessibility_need": prof["accessibility_need"],
        "strict_airgap_preference": prof["strict_airgap_preference"],
        "requires_plain_structure": prof["requires_plain_structure"],
        "max_acceptable_latency_ms": prof["max_acceptable_latency_ms"],
    }
    record["persona_sha256"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return record


def generate_personas_1000() -> list[dict[str, Any]]:
    """Return all 1,000 indexed personas PERS-0001..PERS-1000."""
    return [generate_persona(i) for i in range(1000)]
