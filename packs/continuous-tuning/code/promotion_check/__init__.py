"""Recompute a continuous-tuning promotion decision from its evaluations, with the standard library only.

The draws, the paired bootstrap and the rule follow Tessera's examples/continuous_tuning at commit
2e7d6ab4d7e084a413ba0c3c83cebc10d81c9a98, so a reviewer can check a decision without the trainer's
code. Nothing here trains, loads a model, calls a provider, opens a network connection or moves a
champion pointer; it only reads JSON and prints results.
"""

from __future__ import annotations

from .bootstrap import paired_bootstrap
from .draw import Draw, canonical, digest
from .frozen import check_receipt, jsonl, overlap_counts
from .rule import RULE_FORMAT, check_rule, decide

__all__ = ["RULE_FORMAT", "Draw", "canonical", "check_receipt", "check_rule", "decide", "digest", "jsonl",
           "overlap_counts", "paired_bootstrap"]
