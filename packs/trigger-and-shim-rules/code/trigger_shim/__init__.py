"""Deterministic 3-tier trigger engine, submodular shim knapsack, HarnessTax router, and which-fits matcher."""

from .ast_gate import ZeroHardcodedValuesAstGate
from .engine import ThreeTierTriggerEngine
from .grid import load_default_grid_spec, resolve_grid_cell
from .knapsack import ConversationDedupAndSubmodularKnapsack
from .matcher import WhichFitsCompatibilityMatcher, recommend_which_fits
from .router import HarnessTaxAndThreeRegimeRouter

__all__ = [
    "ConversationDedupAndSubmodularKnapsack",
    "HarnessTaxAndThreeRegimeRouter",
    "ThreeTierTriggerEngine",
    "WhichFitsCompatibilityMatcher",
    "ZeroHardcodedValuesAstGate",
    "load_default_grid_spec",
    "recommend_which_fits",
    "resolve_grid_cell",
]
