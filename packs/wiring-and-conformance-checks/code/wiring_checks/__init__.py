"""Wiring checks for the wiring and conformance checks seed pack: unused modules, mock-only tests and
hollow health probes in Python code.

Standard library only. Everything here reads source files with ast; nothing imports or runs the code
it reads, opens a network connection, calls a model or writes a file. The command line prints JSON.
"""

from .mocks import BEHAVIOR_STATUSES, check_behaviors, hits_path, patch_targets, scan_tests
from .modules import STATUSES, discover, find_unused, read_entry_points, resolve_relative, static_prefix
from .probes import KINDS, classify, scan_probes

__all__ = ["BEHAVIOR_STATUSES", "KINDS", "STATUSES", "check_behaviors", "classify", "discover", "find_unused",
           "hits_path", "patch_targets", "read_entry_points", "resolve_relative", "scan_probes", "scan_tests",
           "static_prefix"]
__version__ = "0.1.0"
