"""Bound public deterministic execution without constraining trusted SDK workloads."""

from __future__ import annotations

import math
from typing import Any

from code_composition.errors import ExecutionInputError

# Reviewed linear extraction used by the bundled document recipe. Custom regular
# expressions are available through the trusted SDK, not in public preview mode.
PUBLIC_PATTERN = r"^\[(?P<doc_id>[A-Z0-9-]+)\]\s+(?P<channel>[a-z_]+):\s+(?P<message>.+)$"


def check_public_value(value: Any, depth: int = 0) -> None:
    if depth > 12:
        raise ExecutionInputError("Public preview nesting limit exceeded.")
    if isinstance(value, str) and len(value) > 32768:
        raise ExecutionInputError("Public preview strings are limited to 32768 characters.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ExecutionInputError("Public preview numbers must be finite.")
    if isinstance(value, list):
        if len(value) > 512:
            raise ExecutionInputError("Public preview arrays are limited to 512 items.")
        for item in value:
            check_public_value(item, depth + 1)
    elif isinstance(value, dict):
        if len(value) > 512:
            raise ExecutionInputError("Public preview objects are limited to 512 fields.")
        for item in value.values():
            check_public_value(item, depth + 1)


def check_public_step(node_id: str, inputs: dict[str, Any], params: dict[str, Any]) -> None:
    check_public_value(inputs)
    check_public_value(params)
    if node_id == "text.regex_extract" and params.get("pattern") != PUBLIC_PATTERN:
        raise ExecutionInputError(
            "Public regex extraction uses the reviewed document pattern. Run custom patterns in your own SDK process."
        )
    if (
        node_id == "join.keyed_enrich"
        and len(inputs.get("left_rows", [])) * len(inputs.get("right_rows", [])) > 4096
    ):
        raise ExecutionInputError("Public join candidate product is limited to 4096.")
