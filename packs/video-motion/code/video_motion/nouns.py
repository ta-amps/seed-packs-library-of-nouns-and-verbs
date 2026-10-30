"""Tessera-facing noun helpers: canonical value digests, NounRef pins, relations and dimensions.

Pure and deterministic. These mirror Tessera's existing contracts (canonical JSON value hashing,
`NounRef {store, key, version, value_sha256}`, typed `RelationEdge`s and the required category
dimensions); they do not add a new store, category or authority.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

NAME_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,63}$"
KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
# Media and tool-card noun values written by this package name the seed pack they serve and where
# this code lives as provenance: the video and motion pack's code folder in the pack library. The
# pack's nouns and verb templates are defined once, in that pack's source.json; this package does
# not export them.
# The default media store is not a surface's protected prefix, and values name no producer surface:
# Tessera records the writing key's own surface.
DEFAULT_SEED_STORE = "seed-packs"
PACK_ID = "video-motion"
PROVENANCE: dict[str, str] = {
    "repository": "https://github.com/ta-amps/pack-contributions",
    "path": "packs/video-motion/code",
    "python_package": "video_motion",
}


def pack_labels() -> dict[str, Any]:
    """Fields every media and tool-card noun value carries: the pack it serves and provenance."""
    return {"pack": PACK_ID, "provenance": dict(PROVENANCE)}


# Dimension rubric for the media and tool-card noun values this package writes:
#   determinism: 1.0 = byte-identical repeat output is tested in this repository.
#   evidence_grounding: 1.0 = every stated property was checked when the value was written; 0.5 =
#     synthetic or declared properties (illustrative attributions, built-in formulas) not measured.
#   token_efficiency: 1.0 = using the noun needs no model call.
#   safety_compliance: 1.0 = the license/attribution and QA gates passed with no errors.
#   verification_tier: "deterministic_gate" when a deterministic check in this package ran on this
#     exact content when the value was written, otherwise "unverified".


class NounPin(BaseModel):
    """Tessera `NounRef`: one exact noun record version and the SHA-256 of its canonical value."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    store: str = Field(pattern=NAME_PATTERN)
    key: str = Field(pattern=KEY_PATTERN)
    version: int = Field(ge=1)
    value_sha256: str = Field(pattern=SHA256_PATTERN)


def json_value(value: Any) -> Any:
    """Normalize whole floats before hashing, matching Tessera's JSON value hashing."""
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) >= 2**53:
        try:
            as_float = float(value)
        except OverflowError as exc:
            raise ValueError("JSON integers must fit IEEE-754") from exc
        if int(as_float) != value:
            raise ValueError("JSON integers must round-trip exactly through IEEE-754")
        return as_float if abs(value) >= 10**16 else value
    if isinstance(value, float) and value.is_integer() and abs(value) < 10**16:
        return int(value)
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [json_value(item) for item in value]
    return value


def value_sha256(value: Any) -> str:
    """SHA-256 of the canonical JSON form of a noun value (Tessera's `value_sha256`)."""
    encoded = json.dumps(
        json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def dimensions(basis: dict[str, str], *, synthetic: bool, checked: bool) -> dict[str, Any]:
    """Required Tessera dimensions under the shared rubric, with a short reason for each value."""
    dims: dict[str, Any] = {
        "determinism": 1.0,
        "evidence_grounding": 0.5 if synthetic else 1.0,
        "token_efficiency": 1.0,
        "safety_compliance": 1.0,
        "verification_tier": "deterministic_gate" if checked else "unverified",
    }
    return {"dimensions": dims, "dimension_basis": basis}


def requires(ref: dict[str, Any] | NounPin, category: str) -> dict[str, Any]:
    """A typed `requires_noun` relation edge to a pinned noun."""
    pin = ref.model_dump() if isinstance(ref, NounPin) else ref
    return {
        "relation": "requires_noun",
        "target_id": f"{pin['store']}/{pin['key']}",
        "target_category": category,
        "note": f"version {pin['version']}; value_sha256 {pin['value_sha256']}",
    }


def pin_for(role: str, value: dict[str, Any], store: str = DEFAULT_SEED_STORE) -> NounPin:
    """The version-1 pin a create-only seed write of `value` under `role.<digest>` receives."""
    digest = value_sha256(value)
    return NounPin(store=store, key=f"{role}.{digest}", version=1, value_sha256=digest)


def _module_file(package_dir: Path, module: str) -> Path | None:
    parts = module.split(".")[1:]
    if not parts:
        return package_dir / "__init__.py"
    candidate = package_dir.joinpath(*parts).with_suffix(".py")
    if candidate.is_file():
        return candidate
    package_init = package_dir.joinpath(*parts, "__init__.py")
    return package_init if package_init.is_file() else None


def _imported_names(tree: ast.AST, module: str) -> Iterable[str]:
    package = module.rpartition(".")[0] or module
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package.split(".")
                base_parts = base_parts[: len(base_parts) - (node.level - 1)]
                base = ".".join(base_parts)
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            yield target
            yield from (f"{target}.{alias.name}" for alias in node.names)


def tool_source_manifest(*entry_modules: str) -> dict[str, str]:
    """SHA-256 of every `video_motion` module the entry modules can import, plus the package init.

    The closure is computed from the import statements (including imports inside functions), so it
    covers every module of this package that executing the tool can load. Python imports a package's
    `__init__` before any submodule, so `video_motion/__init__.py` is always included.
    """
    package_dir = Path(__file__).resolve().parent
    pending = ["video_motion", *entry_modules]
    seen: dict[str, Path] = {}
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        path = _module_file(package_dir, module)
        if path is None:
            continue
        seen[module] = path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _imported_names(tree, module):
            if (name == "video_motion" or name.startswith("video_motion.")) and name not in seen:
                pending.append(name)
    return {
        path.relative_to(package_dir.parent).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(seen.values())
    }
