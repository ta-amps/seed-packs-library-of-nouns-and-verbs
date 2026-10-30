"""Generate labelled edge cases for the kinds asked for, deterministically from one seed."""

from __future__ import annotations

import hashlib
from types import ModuleType
from typing import Any, Iterable

from . import bodies, dates, lists, numbers, strings
from .case import canonical
from .rng import SplitMix64, check_seed, derive

VERSION = "0.1.0"
NAME = "edge cases"
MODULES: dict[str, ModuleType] = {m.KIND: m for m in (strings, numbers, dates, lists, bodies)}
KINDS = tuple(MODULES)
LABELS: dict[str, dict[str, str]] = {
    spec.label: {"kind": kind, "group": spec.group, "why": spec.why, "expect": spec.expect}
    for kind, module in MODULES.items()
    for spec in module.SPECS
}


def resolve_limits(kind: str, given: dict[str, Any] | None) -> dict[str, int]:
    """The kind's defaults with the given limits laid over them; unknown names and out-of-range values fail."""
    module = MODULES[kind]
    given = dict(given or {})
    unknown = set(given) - set(module.DEFAULTS)
    if unknown:
        raise ValueError(f"{kind}: unknown limits {sorted(unknown)}; known: {sorted(module.DEFAULTS)}")
    out = {**module.DEFAULTS, **given}
    for name, value in out.items():
        low, high = module.LIMITS[name]
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ValueError(f"{kind}: {name} must be an integer from {low} to {high}")
    return out


def cases_sha256(cases: Iterable[dict[str, Any]]) -> str:
    """One digest over every case's id, label and SHA-256, so a whole set can be pinned and rechecked."""
    triples = [[case["id"], case["label"], case["sha256"]] for case in cases]
    return hashlib.sha256(canonical(triples).encode("utf-8")).hexdigest()


def generate(kinds: Iterable[str], seed: int, limits: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Every case for the kinds asked for, in a fixed order, with the limits and seed that made them.

    Each kind draws from its own stream derived from the seed, so asking for fewer kinds never changes
    the cases of the others.
    """
    check_seed(seed)
    wanted = list(dict.fromkeys(kinds))
    if not wanted:
        raise ValueError("ask for at least one kind")
    unknown = [kind for kind in wanted if kind not in MODULES]
    if unknown:
        raise ValueError(f"unknown kinds {unknown}; known: {list(KINDS)}")
    limits = dict(limits or {})
    stray = set(limits) - set(wanted)
    if stray:
        raise ValueError(f"limits given for kinds not asked for: {sorted(stray)}")
    used: dict[str, dict[str, int]] = {}
    out: list[dict[str, Any]] = []
    for kind in KINDS:
        if kind not in wanted:
            continue
        used[kind] = resolve_limits(kind, limits.get(kind))
        made = MODULES[kind].cases(used[kind], SplitMix64(derive(seed, kind)))
        out += [case.as_dict(i) for i, case in enumerate(made, start=1)]
    return {
        "generator": {"name": NAME, "version": VERSION},
        "seed": seed,
        "kinds": [kind for kind in KINDS if kind in wanted],
        "limits": used,
        "count": len(out),
        "cases_sha256": cases_sha256(out),
        "cases": out,
    }


def summary(result: dict[str, Any]) -> dict[str, Any]:
    """The same result without values: ids, labels, digests and sizes, small enough to pin in a noun."""
    keep = ("id", "kind", "label", "group", "sha256", "size")
    return {**{k: v for k, v in result.items() if k != "cases"},
            "cases": [{k: case[k] for k in keep if k in case} for case in result["cases"]]}
