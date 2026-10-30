"""Canonical JSON, digests and SHA-256 counter draws: identical on every Python version and platform."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical(value: Any) -> bytes:
    """Sorted keys, no spaces, UTF-8, no NaN: the bytes every digest here is taken over."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class Draw:
    """A seeded stream of integers from SHA-256 over a counter, so any language can repeat it."""

    def __init__(self, *parts: Any) -> None:
        self.seed = hashlib.sha256(canonical(list(parts))).digest()
        self.count = 0

    def _next(self) -> bytes:
        self.count += 1
        return hashlib.sha256(self.seed + self.count.to_bytes(8, "big")).digest()

    def below(self, n: int) -> int:
        """An integer in [0, n): the first 8 bytes of the next digest, big-endian, modulo n."""
        return int.from_bytes(self._next()[:8], "big") % n
