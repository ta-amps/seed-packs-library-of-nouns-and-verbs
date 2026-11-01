"""Dynamic byte-entropy stream patching and surprise-proportional budget allocation."""

from .allocator import SurpriseProportionalBudgetAllocator
from .ast_gate import ZeroHardcodedValuesAstGate, scan_directory_for_hardcoded_values
from .grid import NodeGrid, NodeParameter, ParameterBounds, load_default_grid_spec, resolve_grid_cell
from .patcher import DynamicByteEntropyPatcher

__all__ = [
    "DynamicByteEntropyPatcher",
    "NodeGrid",
    "NodeParameter",
    "ParameterBounds",
    "SurpriseProportionalBudgetAllocator",
    "ZeroHardcodedValuesAstGate",
    "load_default_grid_spec",
    "resolve_grid_cell",
    "scan_directory_for_hardcoded_values",
]
