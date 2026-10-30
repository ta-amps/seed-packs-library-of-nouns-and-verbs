"""A seeded generator of labelled edge cases for the edge and corner cases seed pack.

Standard library only. It builds values in memory and returns them; the command line prints them as
ASCII-only JSON. Nothing here opens a network connection, sends a request, calls a model or writes a
file, and the same seed and limits always give the same cases.
"""

from .case import canonical, case_sha256, code_points, escaped, text_size
from .generate import KINDS, LABELS, NAME, VERSION, cases_sha256, generate, resolve_limits, summary
from .rng import SplitMix64, derive

__all__ = ["KINDS", "LABELS", "NAME", "VERSION", "SplitMix64", "canonical", "case_sha256", "cases_sha256",
           "code_points", "derive", "escaped", "generate", "resolve_limits", "summary", "text_size"]
__version__ = VERSION
