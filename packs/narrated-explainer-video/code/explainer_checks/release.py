"""Release evidence: a manifest that hashes every delivered file, and a ledger of every step's receipt.

A worker assembles the manifest and records released false; releasing is a person's separate act.
The ledger says, step by step, whether each verb that made the video ended with its ready outcome and
a receipt. A closing claim about how the video was made may run only when the steps before it have one.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable
from typing import Any

HEX64 = re.compile(r"[0-9a-f]{64}")


def file_entry(path: str, data: bytes, role: str, media_type: str) -> dict[str, Any]:
    """One manifest row: where the file is, what it is, its size and its SHA-256."""
    return {"path": path, "role": role, "media_type": media_type, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def verify_manifest(manifest: dict[str, Any], read: Callable[[str], bytes]) -> list[str]:
    """Problems between a manifest and the files it names; read(path) returns a file's bytes."""
    problems: list[str] = []
    seen: set[str] = set()
    for entry in manifest["files"]:
        path = entry["path"]
        if path in seen:
            problems.append(f"{path}: listed twice")
        seen.add(path)
        try:
            data = read(path)
        except OSError as exc:
            problems.append(f"{path}: cannot be read ({type(exc).__name__})")
            continue
        if len(data) != entry["bytes"]:
            problems.append(f"{path}: {len(data)} bytes, the manifest says {entry['bytes']}")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            problems.append(f"{path}: SHA-256 differs from the manifest")
    if manifest.get("released") is not False:
        problems.append("a worker's manifest records released false; releasing is a person's act")
    return problems


def missing_receipts(ledger: dict[str, Any], steps: Iterable[str] | None = None) -> list[str]:
    """Steps without a receipt and their ready outcome, among all steps or the ones named."""
    wanted = None if steps is None else set(steps)
    missing = []
    for step in ledger["steps"]:
        if wanted is not None and step["step"] not in wanted:
            continue
        receipt = step.get("receipt")
        if not (isinstance(receipt, str) and HEX64.fullmatch(receipt)) or step.get("outcome") != step.get("ready_outcome"):
            missing.append(step["step"])
    if wanted is not None:
        missing += sorted(wanted - {step["step"] for step in ledger["steps"]})
    return missing


def check_ledger(ledger: dict[str, Any]) -> list[str]:
    """Problems in a receipts ledger: steps without receipts, and a summary flag that disagrees."""
    missing = missing_receipts(ledger)
    problems = [f"{step}: no receipt with its ready outcome" for step in missing]
    names = [step["step"] for step in ledger["steps"]]
    problems += [f"{name}: step listed twice" for name in sorted({n for n in names if names.count(n) > 1})]
    if ledger.get("every_step_has_receipt") is not (not missing):
        problems.append("every_step_has_receipt disagrees with the steps")
    return problems
