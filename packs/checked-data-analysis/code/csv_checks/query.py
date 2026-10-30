"""A small recorded query language: filters, groups and aggregates, each result with its digest.

A query never drops a row silently. Every exclusion, including a later copy of a duplicate row, is a
filter written in the query, and the result counts the rows before and after the filters. A numeric
aggregate over a value that does not parse as its column's type is refused, so invalid values are either
filtered out on the record or fixed at the source, never skipped quietly.
"""

from __future__ import annotations

import statistics
from typing import Any

from .checks import cell_problems, declared, missing_tokens
from .table import Table, convert, digest, fits, is_missing

OPS = ("eq", "ne", "lt", "le", "gt", "ge", "in", "not_missing", "valid", "not_outlier", "not_duplicate")
FUNCTIONS = ("count", "count_values", "sum", "mean", "median", "min", "max")


def _round(value: float, places: int) -> float:
    return round(value, places) + 0.0


def _keep(raw: str | None, condition: dict[str, Any], column: dict[str, Any], row: int, outlier_rows: set[int],
          missing: tuple[str, ...]) -> bool:
    op = condition["op"]
    if op == "not_missing":
        return not is_missing(raw, missing)
    if op == "valid":
        return not cell_problems(raw, column, missing)
    if op == "not_outlier":
        return row not in outlier_rows
    if is_missing(raw, missing) or not fits(raw, column["type"]):
        return False
    value = convert(raw, column["type"])
    target = condition["value"]
    if op == "in":
        return value in target
    return {"eq": value == target, "ne": value != target, "lt": value < target, "le": value <= target,
            "gt": value > target, "ge": value >= target}[op]


def _aggregate(function: str, cells: list[str | None], column: dict[str, Any] | None, missing: tuple[str, ...]) -> Any:
    if function == "count":
        return len(cells)
    present = [raw for raw in cells if not is_missing(raw, missing)]
    if function == "count_values":
        return len(present)
    if column is None or column["type"] not in ("integer", "number"):
        raise ValueError(f"{function} needs a numeric column")
    bad = [raw for raw in present if not fits(raw, column["type"])]
    if bad:
        raise ValueError(f"column {column['name']!r} has values that are not numbers; filter with valid first")
    values = [convert(raw, column["type"]) for raw in present]
    if not values:
        return None
    if function == "sum":
        total = sum(values)
        return total if all(type(v) is int for v in values) else _round(total, 2)
    if function == "mean":
        return _round(statistics.fmean(values), 2)
    if function == "median":
        return _round(float(statistics.median(values)), 2)
    return min(values) if function == "min" else max(values)


def run_query(table: Table, request: dict[str, Any], flags: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
    """Run one query over the pinned table; the result rows and their digest are reproducible."""
    spec = declared(request)
    missing = missing_tokens(request)
    for condition in query.get("filter", []):
        if condition["op"] not in OPS or (condition["op"] != "not_duplicate" and condition.get("column") not in spec):
            raise ValueError(f"{query['id']}: unknown filter {condition}")
    for item in query["aggregates"]:
        if item["fn"] not in FUNCTIONS or (item["fn"] != "count" and item.get("column") not in spec):
            raise ValueError(f"{query['id']}: unknown aggregate {item}")
    outliers = {entry["column"]: set(entry["rows"]) for entry in flags["outliers"]}
    index = {name: table.header.index(name) for name in spec if name in table.header}

    def cell(row: list[str], name: str) -> str | None:
        i = index[name]
        return row[i] if i < len(row) else None

    seen: set[tuple[str, ...]] = set()
    later_copies: set[int] = set()
    for number, row in enumerate(table.rows, start=1):
        if tuple(row) in seen:
            later_copies.add(number)
        seen.add(tuple(row))

    def keep(row: list[str], number: int, condition: dict[str, Any]) -> bool:
        if condition["op"] == "not_duplicate":
            return number not in later_copies
        name = condition["column"]
        return _keep(cell(row, name), condition, spec[name], number, outliers.get(name, set()), missing)

    kept = [row for number, row in enumerate(table.rows, start=1)
            if all(keep(row, number, condition) for condition in query.get("filter", []))]
    groups: dict[tuple[str | None, ...], list[list[str]]] = {}
    for row in kept:
        groups.setdefault(tuple(cell(row, name) for name in query.get("group_by", [])), []).append(row)
    result = []
    for key in sorted(groups, key=lambda k: tuple("" if v is None else v for v in k)):
        members = groups[key]
        out: dict[str, Any] = dict(zip(query.get("group_by", []), key))
        for item in query["aggregates"]:
            column = spec.get(item.get("column", ""))
            cells = [cell(row, item["column"]) for row in members] if item["fn"] != "count" else [None] * len(members)
            out[item["name"]] = _aggregate(item["fn"], cells, column, missing)
        result.append(out)
    return {
        "id": query["id"],
        "query_sha256": digest(query),
        "dataset_sha256": table.sha256,
        "rows_in": len(table.rows),
        "rows_after_filter": len(kept),
        "excluded_by_filter": len(table.rows) - len(kept),
        "result": result,
        "result_sha256": digest(result),
    }


def run_queries(table: Table, request: dict[str, Any], flags: dict[str, Any], queries: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [query["id"] for query in queries]
    if len(ids) != len(set(ids)):
        raise ValueError("query ids must be unique")
    return {"dataset_sha256": table.sha256, "queries": queries,
            "results": [run_query(table, request, flags, query) for query in queries]}
