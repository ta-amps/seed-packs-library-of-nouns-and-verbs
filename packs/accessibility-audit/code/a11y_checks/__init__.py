"""Accessibility checks for the accessibility audit seed pack: contrast ratios and structure lint.

Standard library only. Nothing here opens a network connection, runs page scripts, calls a model
or writes a file; the command line prints its results.
"""

from .contrast import check_pair, format_ratio, is_large_text, parse_color, ratio_of, relative_luminance
from .structure import RULES, lint, rule_ids

__all__ = ["RULES", "check_pair", "format_ratio", "is_large_text", "lint", "parse_color", "ratio_of",
           "relative_luminance", "rule_ids"]
__version__ = "0.1.0"
