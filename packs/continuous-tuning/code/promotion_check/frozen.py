"""Frozen test receipts and contamination counts.

A frozen test set is registered by its hashes before any model is scored on it: the SHA-256 of its rows
as canonical JSON lines, and of its ordered row ids. A receipt registered after the first scoring, or
whose hashes do not match the rows, cannot back a promotion. Contamination is counted from
fingerprints the example generator computes for each row (exact content, normalized request and
template shape); every count must be zero.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from .draw import canonical, digest


def jsonl(rows: Iterable[Any]) -> bytes:
    """Rows as canonical JSON lines, each ending with a newline."""
    return b"".join(canonical(row) + b"\n" for row in rows)


def _instant(text: str) -> datetime:
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError(f"{text!r} needs a time zone")
    return value


def check_receipt(receipt: Mapping[str, Any], rows: list[Mapping[str, Any]], first_scored_at: str) -> list[str]:
    """Problems with a frozen test receipt against its rows and the first time any model was scored on it."""
    problems: list[str] = []
    data = jsonl(rows)
    if hashlib.sha256(data).hexdigest() != receipt["jsonl_sha256"]:
        problems.append("jsonl_sha256 does not match the rows")
    if digest([row["id"] for row in rows]) != receipt["ids_sha256"]:
        problems.append("ids_sha256 does not match the ordered row ids")
    if len(rows) != receipt["rows"]:
        problems.append(f"the receipt says {receipt['rows']} rows, the set has {len(rows)}")
    if len({row["id"] for row in rows}) != len(rows):
        problems.append("row ids repeat")
    if _instant(receipt["registered_at"]) >= _instant(first_scored_at):
        problems.append("registered at or after the first scoring, so it is not pre-registered")
    if any(receipt.get("contamination", {}).values()):
        problems.append("contamination counts are not all zero")
    return problems


def overlap_counts(train: Mapping[str, Iterable[str]], held_out: Mapping[str, Iterable[str]]) -> dict[str, int]:
    """Shared fingerprints per kind between training rows and held-out rows; each must be zero."""
    return {kind: len(set(train.get(kind, ())) & set(held_out.get(kind, ()))) for kind in sorted(set(train) | set(held_out))}
