"""Declarative film and surface rule-noun evaluation package."""

from .ast_gate import ZeroHardcodedValuesAstGate
from .evaluator import (
    evaluate_declarative_rule_nouns,
    load_default_grid_cell,
    rewrite_dead_repo_links_to_source_mirror,
    run_worked_example,
    scan_forbidden_stamps_and_chips,
    score_caption_plate_and_cognitive_load,
    verify_llms_txt_and_mcp_parity,
)

__all__ = [
    "ZeroHardcodedValuesAstGate",
    "evaluate_declarative_rule_nouns",
    "load_default_grid_cell",
    "rewrite_dead_repo_links_to_source_mirror",
    "run_worked_example",
    "scan_forbidden_stamps_and_chips",
    "score_caption_plate_and_cognitive_load",
    "verify_llms_txt_and_mcp_parity",
]
