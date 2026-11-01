"""Pure standard-library capability lattice, secret/PII scanner, and model data-tier firewall."""

from __future__ import annotations

import math
from pathlib import PurePosixPath
import re
from typing import Any

EFFECT_ORDER: dict[str, int] = {
    "none": 0,
    "read": 1,
    "write-internal": 2,
    "write-repo": 3,
    "public": 4,
}

DATA_SENSITIVITY_ORDER: dict[str, int] = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "secret": 3,
}

# Maximum sensitivity level permitted on each model endpoint retention tier.
ENDPOINT_TRAINING_TIERS: dict[str, int] = {
    "trains_on_inputs": DATA_SENSITIVITY_ORDER["public"],
    "contributor_shared": DATA_SENSITIVITY_ORDER["public"],
    "enterprise_no_train": DATA_SENSITIVITY_ORDER["internal"],
    "zero_retention_isolated": DATA_SENSITIVITY_ORDER["confidential"],
}

DESTRUCTIVE_CMD_RE = re.compile(
    r"(?i)(?:\brm\s+-[a-z]*r[a-z]*f\b|\bgit\s+push\s+--force\b|\bgit\s+reset\s+--hard\b|"
    r"\bdrop\s+(?:table|database)\b|\btruncate\s+table\b)"
)

TOKEN_PREFIX_RE = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{24,}|"
    r"sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}|xox[abposr]-[A-Za-z0-9\-]{10,}|"
    r"(?:AKIA|ASIA)[0-9A-Z]{16}|tsk_[A-Za-z0-9_\-]{24,}|tan_[A-Za-z0-9_\-]{24,}|LLM_[A-Za-z0-9_\-]{18,})\b"
)
BEARER_TOKEN_RE = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._\-+/=]{16,}")
PEM_RE = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
HEX_HASH_RE = re.compile(r"^[0-9a-fA-F]{32,64}$")
CANDIDATE_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-+/=]{26,}\b")


def shannon_entropy(token: str) -> float:
    """Compute Shannon entropy in bits per character."""
    if not token:
        return 0.0
    counts: dict[str, int] = {}
    for ch in token:
        counts[ch] = counts.get(ch, 0) + 1
    n = float(len(token))
    return round(-sum((c / n) * math.log2(c / n) for c in counts.values()), 4)


def _is_high_entropy_secret(token: str) -> bool:
    if HEX_HASH_RE.fullmatch(token):
        return False
    has_lower = any(c.islower() for c in token)
    has_upper = any(c.isupper() for c in token)
    has_digit = any(c.isdigit() for c in token)
    if sum((has_lower, has_upper, has_digit)) < 3:
        return False
    return shannon_entropy(token) >= 4.25


def _normalize_rel_path(raw_path: str) -> str | None:
    p = PurePosixPath(raw_path)
    if p.is_absolute() or ".." in p.parts:
        return None
    return p.as_posix()


def check_effect_ceiling(action: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Verify effect_class ceiling, store allowlist, relative path prefix, and destructive command ban."""
    req_effect = str(action.get("effect_class") or "read")
    max_effect = str(policy.get("max_effect_class") or "write-internal")
    reasons: list[str] = []

    if req_effect not in EFFECT_ORDER:
        reasons.append(f"unknown_requested_effect:{req_effect}")
    elif max_effect not in EFFECT_ORDER:
        reasons.append(f"unknown_policy_ceiling:{max_effect}")
    elif EFFECT_ORDER[req_effect] > EFFECT_ORDER[max_effect]:
        reasons.append(f"effect_exceeds_ceiling:{req_effect}>{max_effect}")

    allowed_stores = policy.get("allowed_stores")
    target_store = action.get("target_store")
    if isinstance(allowed_stores, list) and target_store is not None:
        if str(target_store) not in {str(s) for s in allowed_stores}:
            reasons.append(f"store_not_in_allowlist:{target_store}")

    allowed_prefixes = policy.get("allowed_path_prefixes")
    target_path = action.get("target_path")
    if isinstance(allowed_prefixes, list) and target_path is not None:
        norm = _normalize_rel_path(str(target_path))
        if norm is None:
            reasons.append("path_traversal_or_absolute_rejected")
        elif not any(norm == pfx.rstrip("/") or norm.startswith(pfx.rstrip("/") + "/") for pfx in allowed_prefixes):
            reasons.append(f"path_outside_allowed_prefixes:{norm}")

    cmd = str(action.get("command") or "")
    if cmd and DESTRUCTIVE_CMD_RE.search(cmd):
        reasons.append("destructive_command_pattern_blocked")

    return {
        "passed": len(reasons) == 0,
        "requested_effect": req_effect,
        "ceiling_effect": max_effect,
        "reasons": reasons,
    }


def _scan_string(text: str, findings: list[dict[str, str]], location: str) -> str:
    cleaned = text
    if PEM_RE.search(cleaned):
        findings.append({"location": location, "kind": "private_key_header"})
        cleaned = PEM_RE.sub("[REDACTED:PRIVATE_KEY]", cleaned)
    if BEARER_TOKEN_RE.search(cleaned):
        findings.append({"location": location, "kind": "bearer_token"})
        cleaned = BEARER_TOKEN_RE.sub(r"\1[REDACTED:BEARER]", cleaned)
    if TOKEN_PREFIX_RE.search(cleaned):
        findings.append({"location": location, "kind": "prefixed_api_credential"})
        cleaned = TOKEN_PREFIX_RE.sub("[REDACTED:CREDENTIAL]", cleaned)
    if SSN_RE.search(cleaned):
        findings.append({"location": location, "kind": "personal_id_number"})
        cleaned = SSN_RE.sub("[REDACTED:PII]", cleaned)

    def _entropy_sub(match: re.Match[str]) -> str:
        tok = match.group(0)
        if _is_high_entropy_secret(tok):
            findings.append({"location": location, "kind": "high_entropy_secret"})
            return "[REDACTED:HIGH_ENTROPY]"
        return tok

    cleaned = CANDIDATE_TOKEN_RE.sub(_entropy_sub, cleaned)
    return cleaned


def _walk_payload(value: Any, findings: list[dict[str, str]], path: str) -> Any:
    if isinstance(value, str):
        return _scan_string(value, findings, path)
    if isinstance(value, list):
        return [_walk_payload(item, findings, f"{path}[{idx}]") for idx, item in enumerate(value)]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            sub_path = f"{path}.{k}"
            if str(k).lower() in {"api_key", "secret", "password", "client_secret", "private_key"} and isinstance(v, str) and v:
                findings.append({"location": sub_path, "kind": "named_secret_field"})
                out[str(k)] = "[REDACTED:SECRET_FIELD]"
            else:
                out[str(k)] = _walk_payload(v, findings, sub_path)
        return out
    return value


def scan_and_redact_payload(payload: Any) -> dict[str, Any]:
    """Scan an outbound payload for secrets/PII and produce a sanitized copy plus finding list."""
    findings: list[dict[str, str]] = []
    sanitized = _walk_payload(payload, findings, "$")
    return {
        "clean": len(findings) == 0,
        "finding_count": len(findings),
        "findings": findings,
        "sanitized_payload": sanitized,
    }


def check_model_tier_routing(
    *,
    data_sensitivity: str,
    endpoint_tier: str,
    contains_unredacted_secrets: bool,
    contributor_mode_enabled: bool = False,
) -> dict[str, Any]:
    """Block private, internal, or secret payloads from training/contributor model endpoints."""
    reasons: list[str] = []
    if data_sensitivity not in DATA_SENSITIVITY_ORDER:
        reasons.append(f"unknown_data_sensitivity:{data_sensitivity}")
        return {"passed": False, "reasons": reasons}
    if endpoint_tier not in ENDPOINT_TRAINING_TIERS:
        reasons.append(f"unknown_endpoint_tier:{endpoint_tier}")
        return {"passed": False, "reasons": reasons}

    sens_rank = DATA_SENSITIVITY_ORDER[data_sensitivity]
    effective_tier = "contributor_shared" if contributor_mode_enabled else endpoint_tier
    allowed_max_rank = ENDPOINT_TRAINING_TIERS[effective_tier]

    if contains_unredacted_secrets:
        reasons.append("unredacted_secrets_detected_in_payload")
    if sens_rank == DATA_SENSITIVITY_ORDER["secret"]:
        reasons.append("secret_tier_payload_forbidden_for_external_model_dispatch")
    elif sens_rank > allowed_max_rank:
        reasons.append(f"sensitivity_{data_sensitivity}_blocked_for_endpoint_tier_{effective_tier}")

    return {
        "passed": len(reasons) == 0,
        "data_sensitivity": data_sensitivity,
        "effective_endpoint_tier": effective_tier,
        "reasons": reasons,
    }


def evaluate_dispatch(request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Run all three pre-dispatch firewall gates (effect ceiling, secret scan, model data-tier)."""
    effect_res = check_effect_ceiling(request.get("action") or {}, policy)
    scan_res = scan_and_redact_payload(request.get("payload"))

    allow_redacted_dispatch = bool(policy.get("allow_dispatch_after_redaction", False))
    unredacted_flag = (not scan_res["clean"]) and (not allow_redacted_dispatch)

    tier_res = check_model_tier_routing(
        data_sensitivity=str(request.get("data_sensitivity") or "internal"),
        endpoint_tier=str(request.get("endpoint_tier") or "trains_on_inputs"),
        contains_unredacted_secrets=unredacted_flag,
        contributor_mode_enabled=bool(request.get("contributor_mode_enabled", False)),
    )

    all_reasons = [*effect_res["reasons"], *tier_res["reasons"]]
    if (not scan_res["clean"]) and (not allow_redacted_dispatch) and "unredacted_secrets_detected_in_payload" not in all_reasons:
        all_reasons.append("unredacted_secrets_detected_in_payload")

    allowed = len(all_reasons) == 0
    return {
        "verdict": "allow" if allowed else "block",
        "allowed": allowed,
        "reasons": all_reasons,
        "effect_check": effect_res,
        "secret_scan": {
            "clean": scan_res["clean"],
            "finding_count": scan_res["finding_count"],
            "findings": scan_res["findings"],
        },
        "tier_check": tier_res,
        "sanitized_payload": scan_res["sanitized_payload"],
    }
