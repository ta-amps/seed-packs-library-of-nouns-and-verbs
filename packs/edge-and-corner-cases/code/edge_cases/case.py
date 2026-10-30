"""One labelled case: its value, context, an ASCII-safe escaped form, sizes and a SHA-256 identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def canonical(value: Any) -> str:
    """Sorted keys, no spaces, raw UTF-8: the form whose SHA-256 identifies a case."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def escaped(value: Any) -> str:
    """JSON with every non-ASCII, control, invisible and direction-changing character written as an escape.

    Any JSON parser turns it back into the exact value, and it can be pasted into a review or a log
    without reordering the text around it.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def case_sha256(kind: str, label: str, value: Any, context: dict[str, Any]) -> str:
    """The identity of one case: its kind, label, value and context, so two labels never share a digest."""
    body = {"context": context, "kind": kind, "label": label, "value": value}
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def text_size(text: str) -> dict[str, int]:
    """The three lengths a limit can mean: code points, UTF-8 bytes and UTF-16 code units."""
    return {
        "code_points": len(text),
        "utf8_bytes": len(text.encode("utf-8")),
        "utf16_units": len(text.encode("utf-16-le")) // 2,
    }


def code_points(text: str) -> list[str]:
    return [f"U+{ord(ch):04X}" for ch in text]


@dataclass(frozen=True)
class Spec:
    """What a label tests: its group, why it matters and what a careful target does with it."""

    label: str
    group: str
    why: str
    expect: str


@dataclass
class Case:
    kind: str
    spec: Spec
    value: Any
    context: dict[str, Any] = field(default_factory=dict)

    def as_dict(self, index: int) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": f"{self.kind}-{index:03d}",
            "kind": self.kind,
            "label": self.spec.label,
            "group": self.spec.group,
            "value": self.value,
            "context": dict(self.context),
            "escaped": escaped(self.value),
            "sha256": case_sha256(self.kind, self.spec.label, self.value, self.context),
            "why": self.spec.why,
            "expect": self.spec.expect,
        }
        if isinstance(self.value, str):
            out["size"] = text_size(self.value)
            if len(self.value) <= 24:
                out["code_points"] = code_points(self.value)
        elif isinstance(self.value, list):
            out["size"] = {"items": len(self.value)}
        return out
