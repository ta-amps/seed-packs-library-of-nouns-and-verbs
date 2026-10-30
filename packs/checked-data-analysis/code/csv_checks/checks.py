"""Profile a table, validate it against the declared schema, and flag missing values and outliers.

Each step reports and never changes the data: a missing value, a type error or an outlier is listed
with its row and stays in the table. Values from a column the request marks identifying are never
copied into a report; only counts and row numbers are.
"""

from __future__ import annotations

import re
import statistics
from typing import Any

from .table import KINDS, Table, convert, fits, is_missing, kind_of


def _round(value: float, places: int) -> float:
    return round(value, places) + 0.0


def missing_tokens(request: dict[str, Any]) -> tuple[str, ...]:
    return tuple(request["missing_tokens"])


def declared(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {column["name"]: column for column in request["columns"]}


def inferred_type(kinds: list[str]) -> str:
    present = set(kinds)
    if not present:
        return "empty"
    if present == {"integer"}:
        return "integer"
    if present <= {"integer", "number"}:
        return "number"
    if len(present) == 1:
        return next(iter(present))
    return "string"


def profile(table: Table, request: dict[str, Any]) -> dict[str, Any]:
    """What the file holds, before any rule is applied."""
    missing = missing_tokens(request)
    spec = declared(request)
    columns = []
    for name in dict.fromkeys(table.header):
        raw = [value for value in table.column(name) if not is_missing(value, missing)]
        kinds = [kind_of(value) for value in raw]
        kind = inferred_type(kinds)
        identifying = bool(spec.get(name, {}).get("identifying"))
        low = high = None
        if not identifying and kind in ("integer", "number"):
            numbers = [convert(value, kind) for value in raw]
            low, high = min(numbers), max(numbers)
        elif not identifying and kind == "date":
            low, high = min(raw), max(raw)
        columns.append({
            "name": name,
            "inferred_type": kind,
            "type_counts": {k: kinds.count(k) for k in KINDS if k in kinds},
            "missing": len(table.rows) - len(raw),
            "distinct": len(set(raw)),
            "min": low,
            "max": high,
            "examples": [] if identifying else list(dict.fromkeys(raw))[:3],
            "identifying": identifying,
        })
    seen: dict[tuple[str, ...], int] = {}
    duplicates = []
    for number, row in enumerate(table.rows, start=1):
        key = tuple(row)
        if key in seen:
            duplicates.append({"row": number, "same_as": seen[key]})
        else:
            seen[key] = number
    names = table.header
    return {
        "dataset_sha256": table.sha256,
        "encoding": "utf-8",
        "bom": table.bom,
        "delimiter": table.delimiter,
        "header": list(names),
        "rows": len(table.rows),
        "columns": columns,
        "ragged_rows": list(table.ragged_rows),
        "duplicate_headers": sorted({name for name in names if names.count(name) > 1}),
        "blank_headers": [i for i, name in enumerate(names, start=1) if not name.strip()],
        "duplicate_rows": duplicates,
    }


def cell_problems(raw: str | None, column: dict[str, Any], missing: tuple[str, ...]) -> list[str]:
    """The rules one cell breaks, in a fixed order: required, type, then min, max, allowed and pattern."""
    if is_missing(raw, missing):
        return ["required"] if column.get("required") else []
    kind = column["type"]
    if not fits(raw, kind):
        return ["type"]
    value = convert(raw, kind)
    problems = []
    if "min" in column and value < column["min"]:
        problems.append("min")
    if "max" in column and value > column["max"]:
        problems.append("max")
    if "allowed" in column and raw not in column["allowed"]:
        problems.append("allowed")
    if "pattern" in column and not re.fullmatch(column["pattern"], raw):
        problems.append("pattern")
    return problems


def validate(table: Table, request: dict[str, Any]) -> dict[str, Any]:
    """Every cell checked against the declared schema; every violation listed with its row and rule."""
    missing = missing_tokens(request)
    spec = declared(request)
    header_problems = [f"declared column {name!r} is not in the header" for name in spec if name not in table.header]
    header_problems += [f"column {name!r} is not declared" for name in dict.fromkeys(table.header) if name not in spec]
    header_problems += [f"column {name!r} appears more than once" for name in sorted({n for n in table.header if table.header.count(n) > 1})]
    violations = [{"row": row, "column": "*", "rule": "row_length", "value": None} for row in table.ragged_rows]
    for name, column in spec.items():
        if name not in table.header:
            continue
        identifying = bool(column.get("identifying"))
        first: dict[str, int] = {}
        for number, raw in enumerate(table.column(name), start=1):
            rules = cell_problems(raw, column, missing)
            if column.get("unique") and not is_missing(raw, missing):
                if raw in first:
                    rules.append("unique")
                else:
                    first[raw] = number
            for rule in rules:
                violations.append({"row": number, "column": name, "rule": rule, "value": None if identifying else raw})
    violations.sort(key=lambda v: (v["row"], v["column"], v["rule"]))
    counts: dict[str, int] = {}
    for item in violations:
        counts[item["rule"]] = counts.get(item["rule"], 0) + 1
    return {
        "dataset_sha256": table.sha256,
        "header_problems": header_problems,
        "violations": violations,
        "counts": dict(sorted(counts.items())),
        "rows_checked": len(table.rows),
        "rows_with_violations": len({v["row"] for v in violations}),
        "passed": not violations and not header_problems,
    }


def flag(table: Table, request: dict[str, Any]) -> dict[str, Any]:
    """Missing values in every column, and outliers by Tukey's fences in every numeric column; nothing is removed."""
    missing = missing_tokens(request)
    rule = request["outlier_rule"]
    if rule["method"] != "tukey_fences" or rule["quantiles"] not in ("inclusive", "exclusive") or not rule["k"] > 0:
        raise ValueError("the outlier rule is tukey_fences with k above 0 and inclusive or exclusive quantiles")
    out_missing, outliers = [], []
    for column in request["columns"]:
        name = column["name"]
        if name not in table.header:
            continue
        cells = table.column(name)
        rows = [i for i, raw in enumerate(cells, start=1) if is_missing(raw, missing)]
        out_missing.append({"column": name, "count": len(rows), "rows": rows})
        if column["type"] not in ("integer", "number"):
            continue
        pairs = [(i, convert(raw, column["type"])) for i, raw in enumerate(cells, start=1)
                 if not is_missing(raw, missing) and fits(raw, column["type"])]
        entry: dict[str, Any] = {"column": name, "method": rule["method"], "k": rule["k"], "values_used": len(pairs),
                                 "q1": None, "q3": None, "iqr": None, "low_fence": None, "high_fence": None,
                                 "rows": [], "values": [], "reason": None}
        if len(pairs) < rule["min_values"]:
            entry["reason"] = "too_few_values"
        else:
            q1, _, q3 = statistics.quantiles([v for _, v in pairs], n=4, method=rule["quantiles"])
            iqr = q3 - q1
            low, high = q1 - rule["k"] * iqr, q3 + rule["k"] * iqr
            hits = [(i, v) for i, v in pairs if v < low or v > high]
            entry.update(q1=_round(q1, 4), q3=_round(q3, 4), iqr=_round(iqr, 4), low_fence=_round(low, 4),
                         high_fence=_round(high, 4), rows=[i for i, _ in hits],
                         values=[] if column.get("identifying") else [v for _, v in hits])
        outliers.append(entry)
    return {"dataset_sha256": table.sha256, "rule": dict(rule), "missing": out_missing, "outliers": outliers}
