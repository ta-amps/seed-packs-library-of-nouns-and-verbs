"""Deterministic coding-session JSONL transcript sanitizer and trace distiller.

Standard library only. Reads session JSONL transcripts as plain data, redacts
credentials, personal addresses, and workstation paths first, and mines tool-error
loops, failure tombstones, verified fix recipes, and prompt-shim candidates.
"""

from .analyzer import (
    detect_tool_error_loops,
    distill_session_events,
    extract_failure_tombstones,
    extract_verified_fix_recipes,
    load_jsonl_events,
    propose_prompt_shims,
)
from .redactor import redact_event, redact_session, redact_text

__all__ = [
    "detect_tool_error_loops",
    "distill_session_events",
    "extract_failure_tombstones",
    "extract_verified_fix_recipes",
    "load_jsonl_events",
    "propose_prompt_shims",
    "redact_event",
    "redact_session",
    "redact_text",
]
