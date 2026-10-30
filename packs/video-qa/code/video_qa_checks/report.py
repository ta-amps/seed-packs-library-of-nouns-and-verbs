"""One extended QA report per encoded file, bound to its SHA-256, with a verdict that follows from its rows."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

NOT_APPROVAL = "Passing these checks is not approval: a person still watches every frame and listens."
REQUIRED = ("blank_frames", "frozen_stretches", "cut_cadence", "loudness", "silence_gaps", "clipping",
            "captions", "file_spec", "legibility")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verdict(rows: list[dict[str, Any]], required: tuple[str, ...] = REQUIRED) -> str:
    """fail if any row fails; incomplete if a required check is missing or not_run; then warnings."""
    results = {row["check"]: row["result"] for row in rows}
    if "fail" in results.values():
        return "fail"
    if any(results.get(name, "not_run") == "not_run" for name in required):
        return "incomplete"
    return "pass_with_warnings" if "warn" in results.values() else "pass"


def compile_report(media: dict[str, Any], plan: dict[str, Any], rows: list[dict[str, Any]],
                   inputs: list[dict[str, str]] | None = None,
                   required: tuple[str, ...] = REQUIRED) -> dict[str, Any]:
    names = [row["check"] for row in rows]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"checks reported twice: {duplicates}")
    counts = {key: sum(1 for row in rows if row["result"] == key) for key in ("pass", "warn", "fail", "not_run")}
    missing = [name for name in required if name not in names]
    return {
        "media": media,
        "plan": {"duration_s": plan["duration_s"], "fps": plan["fps"], "holds": len(plan.get("holds", [])),
                 "pauses": len(plan.get("pauses", [])), "black": len(plan.get("black", []))},
        "inputs": inputs or [],
        "checks": rows,
        "missing_checks": missing,
        "counts": counts,
        "verdict": verdict(rows, required),
        "not_approval": NOT_APPROVAL,
    }
