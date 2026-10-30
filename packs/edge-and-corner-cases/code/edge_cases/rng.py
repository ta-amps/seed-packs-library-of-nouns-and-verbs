"""SplitMix64, a small and fully specified pseudo-random generator.

The same seed gives the same numbers on every Python version and platform, which the standard
library's random module does not promise across releases. It is for reproducible test inputs only,
never for anything secret.
"""

from __future__ import annotations

import hashlib
from typing import Sequence, TypeVar

MASK = (1 << 64) - 1
GOLDEN = 0x9E3779B97F4A7C15
T = TypeVar("T")


def check_seed(seed: object) -> int:
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= MASK:
        raise ValueError("a seed is an integer from 0 to 2**64 - 1")
    return seed


def derive(seed: int, name: str) -> int:
    """An independent 64-bit stream seed for one kind, so asking for fewer kinds never changes the others."""
    return int.from_bytes(hashlib.sha256(f"{check_seed(seed)}:{name}".encode()).digest()[:8], "big")


class SplitMix64:
    def __init__(self, seed: int) -> None:
        self.state = check_seed(seed)

    def next64(self) -> int:
        self.state = (self.state + GOLDEN) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def below(self, n: int) -> int:
        """A uniform integer from 0 to n - 1, by rejection, so no value is favored."""
        if not isinstance(n, int) or n <= 0:
            raise ValueError("below needs a positive integer")
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            value = self.next64()
            if value < limit:
                return value % n

    def between(self, low: int, high: int) -> int:
        """A uniform integer from low to high, both included."""
        if high < low:
            raise ValueError("between needs low <= high")
        return low + self.below(high - low + 1)

    def choice(self, items: Sequence[T]) -> T:
        if not items:
            raise ValueError("choice needs at least one item")
        return items[self.below(len(items))]

    def shuffled(self, items: Sequence[T]) -> list[T]:
        """A Fisher-Yates shuffle of a copy; the input is left alone."""
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.below(i + 1)
            out[i], out[j] = out[j], out[i]
        return out
