"""The paired bootstrap of a candidate against the champion on the same frozen rows."""

from __future__ import annotations

from collections.abc import Sequence

from .draw import Draw


def paired_bootstrap(candidate: Sequence[bool | int], champion: Sequence[bool | int], resamples: int, seed: str,
                     confidence: float) -> dict[str, float | int]:
    """Percentile interval of the paired mean difference in exact match, from SHA-256 seeded resamples.

    Each resample draws len(rows) row indices with replacement from Draw("paired-bootstrap", seed, n)
    and averages the per-row differences (candidate minus champion, each 1, 0 or -1).
    """
    if len(candidate) != len(champion) or not candidate:
        raise ValueError("paired evaluations must cover the same nonempty rows")
    n = len(candidate)
    differences = [int(bool(a)) - int(bool(b)) for a, b in zip(candidate, champion)]
    draw = Draw("paired-bootstrap", seed, n)
    means = sorted(sum(differences[draw.below(n)] for _ in range(n)) / n for _ in range(resamples))
    tail = (1 - confidence) / 2
    return {
        "delta": round(sum(differences) / n, 6),
        "lower": round(means[int(tail * resamples)], 6),
        "upper": round(means[min(resamples - 1, int((1 - tail) * resamples))], 6),
        "improved_rows": sum(1 for d in differences if d > 0),
        "regressed_rows": sum(1 for d in differences if d < 0),
    }
