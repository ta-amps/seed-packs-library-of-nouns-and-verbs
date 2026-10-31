"""MinHash near-duplicate pruning and untrusted prompt-injection directive stripping."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .fusion import tokenize

MERSENNE_PRIME = (1 << 61) - 1
MAX_HASH = (1 << 32) - 1

INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_prior_instructions",
        re.compile(
            r"(?i)\b(?:ignore|disregard|override|forget)\s+(?:all\s+|any\s+)?(?:previous|prior|above|system|developer)\s+(?:instructions?|prompts?|rules?|guardrails?)\b"
        ),
    ),
    (
        "fake_role_header",
        re.compile(r"(?i)(?:^|\s)(?:<\s*(?:system|developer|assistant)\s*>|###\s*(?:system|instruction)\s*:|\[system\s*override\])"),
    ),
    (
        "secret_or_tool_coercion",
        re.compile(
            r"(?i)\b(?:exfiltrate|print|reveal|leak)\s+(?:the\s+)?(?:api[_\s-]?keys?|secrets?|tokens?|system\s+prompt|environment\s+variables?)\b"
        ),
    ),
    (
        "untrusted_tool_directive",
        re.compile(r"(?i)\b(?:you\s+must\s+immediately\s+call|execute\s+shell\s+command|run\s+rm\s+-rf|curl\s+https?://)\b"),
    ),
)

REDACTED_MARKER = "[REDACTED_UNTRUSTED_DIRECTIVE]"


def _perm_coefficients(num_perm: int) -> list[tuple[int, int]]:
    coeffs: list[tuple[int, int]] = []
    for idx in range(num_perm):
        digest = hashlib.sha256(f"minhash-perm-v1:{idx}".encode("utf-8")).digest()
        a = (int.from_bytes(digest[:8], "big") % (MERSENNE_PRIME - 1)) + 1
        b = int.from_bytes(digest[8:16], "big") % MERSENNE_PRIME
        coeffs.append((a, b))
    return coeffs


def word_shingles(text: str, shingle_size: int = 3) -> set[str]:
    """Build word n-gram shingles for a text chunk."""
    tokens = tokenize(text)
    if not tokens:
        return set()
    if len(tokens) < shingle_size:
        return {" ".join(tokens)}
    return {" ".join(tokens[i : i + shingle_size]) for i in range(len(tokens) - shingle_size + 1)}


def minhash_signature(
    text: str,
    *,
    shingle_size: int = 3,
    num_perm: int = 64,
) -> tuple[int, ...]:
    """Compute deterministic universal-hash MinHash signature."""
    shingles = word_shingles(text, shingle_size=shingle_size)
    if not shingles:
        return tuple([MAX_HASH] * num_perm)

    base_hashes = [
        int.from_bytes(hashlib.sha1(s.encode("utf-8")).digest()[:4], "big")
        for s in shingles
    ]
    coeffs = _perm_coefficients(num_perm)
    sig: list[int] = []
    for a, b in coeffs:
        min_val = min(((a * h + b) % MERSENNE_PRIME) & MAX_HASH for h in base_hashes)
        sig.append(min_val)
    return tuple(sig)


def minhash_similarity(sig_a: Sequence[int], sig_b: Sequence[int]) -> float:
    """Estimate Jaccard similarity from equal-length MinHash signatures."""
    if not sig_a or len(sig_a) != len(sig_b):
        return 0.0
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / float(len(sig_a))


def exact_shingle_jaccard(text_a: str, text_b: str, *, shingle_size: int = 3) -> float:
    """Exact Jaccard similarity over word shingles."""
    set_a = word_shingles(text_a, shingle_size=shingle_size)
    set_b = word_shingles(text_b, shingle_size=shingle_size)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / float(len(set_a | set_b))


def strip_prompt_injections(text: str) -> dict[str, Any]:
    """Strip untrusted prompt-injection lines/directives from retrieved text."""
    clean_lines: list[str] = []
    matched_rules: list[str] = []
    stripped_line_count = 0

    for line in text.splitlines():
        line_hits = [name for name, pat in INJECTION_PATTERNS if pat.search(line)]
        if line_hits:
            stripped_line_count += 1
            for name in line_hits:
                if name not in matched_rules:
                    matched_rules.append(name)
            clean_lines.append(REDACTED_MARKER)
        else:
            clean_lines.append(line)

    sanitized_text = "\n".join(clean_lines).strip()
    return {
        "sanitized_text": sanitized_text,
        "injection_detected": bool(matched_rules),
        "stripped_line_count": stripped_line_count,
        "matched_rules": matched_rules,
    }


def sanitize_and_deduplicate(
    ranked_chunks: Sequence[Mapping[str, Any]],
    *,
    near_dup_threshold: float = 0.75,
    shingle_size: int = 3,
    num_perm: int = 64,
) -> dict[str, Any]:
    """Sanitize untrusted directives and prune lower-ranked MinHash near-duplicates."""
    kept: list[dict[str, Any]] = []
    kept_sigs: list[tuple[str, tuple[int, ...]]] = []
    dropped_near_duplicates: list[dict[str, Any]] = []
    sanitized_ids: list[str] = []

    for chunk in ranked_chunks:
        cid = str(chunk["id"])
        raw_text = str(chunk.get("text", ""))
        san = strip_prompt_injections(raw_text)
        clean_text = san["sanitized_text"]
        if san["injection_detected"]:
            sanitized_ids.append(cid)

        # Drop chunks that collapsed completely into redaction markers with no substantive tokens
        substantive = clean_text.replace(REDACTED_MARKER, "").strip()
        if not tokenize(substantive):
            dropped_near_duplicates.append(
                {
                    "id": cid,
                    "reason": "empty_after_injection_stripping",
                    "duplicate_of": None,
                    "minhash_similarity": 1.0,
                }
            )
            continue

        sig = minhash_signature(substantive, shingle_size=shingle_size, num_perm=num_perm)
        dup_of: str | None = None
        dup_sim = 0.0
        for prev_id, prev_sig in kept_sigs:
            sim = minhash_similarity(sig, prev_sig)
            if sim >= near_dup_threshold:
                dup_of = prev_id
                dup_sim = round(sim, 6)
                break

        if dup_of is not None:
            dropped_near_duplicates.append(
                {
                    "id": cid,
                    "reason": "minhash_near_duplicate",
                    "duplicate_of": dup_of,
                    "minhash_similarity": dup_sim,
                }
            )
            continue

        kept_sigs.append((cid, sig))
        kept.append(
            {
                **dict(chunk),
                "text": clean_text,
                "injection_detected": san["injection_detected"],
                "matched_injection_rules": san["matched_rules"],
            }
        )

    return {
        "kept_chunks": kept,
        "dropped_chunks": dropped_near_duplicates,
        "sanitized_chunk_ids": sanitized_ids,
    }
