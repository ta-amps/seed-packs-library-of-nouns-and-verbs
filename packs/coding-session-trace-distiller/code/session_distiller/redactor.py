"""Deterministic secret, personal-address, and workstation-path redactor for session traces."""

from __future__ import annotations

import re
from typing import Any

# Patterns avoid embedding any literal credential example while catching standard token shapes.
BEARER_RE = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._\-+/=]{16,}")
PREFIXED_TOKEN_RE = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{24,}|"
    r"sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}|xox[abposr]-[A-Za-z0-9\-]{10,}|"
    r"(?:AKIA|ASIA)[0-9A-Z]{16}|tsk_[A-Za-z0-9_\-]{24,}|tan_[A-Za-z0-9_\-]{24,}|LLM_[A-Za-z0-9_\-]{18,})\b"
)
PEM_BLOCK_RE = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"
)
PEM_HEADER_RE = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
ASSIGNED_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|client_secret)\b(\s*[:=]\s*['\"]?)([A-Za-z0-9_\-./+=]{16,})(['\"]?)"
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@(?!example\.(?:com|org|net)\b)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
UNIX_HOME_RE = re.compile(r"/(?:home|Users)/[A-Za-z0-9._\-]+")
WIN_HOME_RE = re.compile(r"(?i)\b[A-Z]:\\Users\\[A-Za-z0-9._\-]+")


def redact_text(text: str, stats: dict[str, int] | None = None) -> str:
    """Redact credentials, non-example email addresses, and user home directories."""
    counters = stats if stats is not None else {"secrets_redacted": 0, "emails_redacted": 0, "paths_normalized": 0}

    def _sub_count(pattern: re.Pattern[str], repl: str, src: str, bucket: str) -> str:
        out, n = pattern.subn(repl, src)
        counters[bucket] = counters.get(bucket, 0) + n
        return out

    cleaned = _sub_count(PEM_BLOCK_RE, "[REDACTED:PRIVATE_KEY]", text, "secrets_redacted")
    cleaned = _sub_count(PEM_HEADER_RE, "[REDACTED:PRIVATE_KEY]", cleaned, "secrets_redacted")
    cleaned = _sub_count(BEARER_RE, r"\1[REDACTED:BEARER_TOKEN]", cleaned, "secrets_redacted")
    cleaned = _sub_count(PREFIXED_TOKEN_RE, "[REDACTED:CREDENTIAL]", cleaned, "secrets_redacted")

    def _replace_assigned(match: re.Match[str]) -> str:
        counters["secrets_redacted"] = counters.get("secrets_redacted", 0) + 1
        return f"{match.group(1)}{match.group(2)}[REDACTED:SECRET]{match.group(4)}"

    cleaned = ASSIGNED_SECRET_RE.sub(_replace_assigned, cleaned)
    cleaned = _sub_count(EMAIL_RE, "[REDACTED:EMAIL]", cleaned, "emails_redacted")
    cleaned = _sub_count(UNIX_HOME_RE, "<HOME>", cleaned, "paths_normalized")
    cleaned = _sub_count(WIN_HOME_RE, "<HOME>", cleaned, "paths_normalized")
    return cleaned


def _redact_value(value: Any, stats: dict[str, int], key_hint: str = "") -> Any:
    lowered_key = key_hint.lower()
    if lowered_key in {"api_key", "apikey", "authorization", "access_token", "refresh_token", "client_secret", "password"}:
        if isinstance(value, str) and value and not value.startswith("[REDACTED:"):
            stats["secrets_redacted"] = stats.get("secrets_redacted", 0) + 1
            return "[REDACTED:SECRET_FIELD]"
    if isinstance(value, str):
        return redact_text(value, stats)
    if isinstance(value, list):
        return [_redact_value(item, stats, key_hint=key_hint) for item in value]
    if isinstance(value, dict):
        return {str(k): _redact_value(v, stats, key_hint=str(k)) for k, v in value.items()}
    return value


def redact_event(event: dict[str, Any], stats: dict[str, int] | None = None) -> dict[str, Any]:
    counters = stats if stats is not None else {"secrets_redacted": 0, "emails_redacted": 0, "paths_normalized": 0}
    redacted = _redact_value(event, counters)
    if not isinstance(redacted, dict):
        raise TypeError("event must be a JSON object")
    return redacted


def redact_session(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats = {"secrets_redacted": 0, "emails_redacted": 0, "paths_normalized": 0}
    sanitized = [redact_event(ev, stats) for ev in events]
    return sanitized, stats
