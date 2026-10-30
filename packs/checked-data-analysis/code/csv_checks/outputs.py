"""Checks on what an analysis hands over: charts kept as data specs, and findings whose numbers trace to queries.

A chart is a Vega-Lite version 5 specification whose inline data is exactly one recorded query's result,
named in its usermeta with the version. The optional $schema property is added only when a spec is exported
for a renderer, so a stored spec states its version in usermeta. A finding lists every number it states,
each with the query, result row and column it came from. Both checks only read; they draw nothing and
change nothing.
"""

from __future__ import annotations

import re
from typing import Any

VEGA_LITE_V5 = "https://vega.github.io/schema/vega-lite/v5.json"
MARKS = ("bar", "line", "point")
FIELD_TYPES = ("nominal", "ordinal", "quantitative", "temporal")
# A number in prose: not part of a date, a time, a word or a hyphenated label such as 30-day.
NUMBER = re.compile(r"(?<![\w.:-])[0-9]+(?:\.[0-9]+)?(?![\w:-]|\.[0-9])")


def check_chart(spec: dict[str, Any], results: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Problems with one chart spec; results maps each query id to its result rows."""
    problems = []
    name = spec.get("title", "untitled chart")
    meta = spec.get("usermeta") or {}
    if meta.get("vega_lite") != "v5" or spec.get("$schema", VEGA_LITE_V5) != VEGA_LITE_V5:
        problems.append(f"{name}: the spec is not Vega-Lite version 5")
    for field in ("title", "description"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            problems.append(f"{name}: {field} is missing")
    query = meta.get("query")
    data = spec.get("data") or {}
    if "url" in data or "values" not in data:
        problems.append(f"{name}: data must be inline values, never a URL")
    elif query not in results:
        problems.append(f"{name}: usermeta.query does not name a recorded query")
    elif data["values"] != results[query]:
        problems.append(f"{name}: data.values differ from the result of {query}")
    mark = spec.get("mark")
    mark_type = mark.get("type") if isinstance(mark, dict) else mark
    if mark_type not in MARKS:
        problems.append(f"{name}: mark is one of {', '.join(MARKS)}")
    encoding = spec.get("encoding") or {}
    if not {"x", "y"} <= set(encoding):
        problems.append(f"{name}: encoding needs x and y")
    rows = data.get("values") or []
    for channel, enc in sorted(encoding.items()):
        if enc.get("type") not in FIELD_TYPES:
            problems.append(f"{name}: {channel} type is one of {', '.join(FIELD_TYPES)}")
        if not rows or any(enc.get("field") not in row for row in rows):
            problems.append(f"{name}: {channel} field {enc.get('field')!r} is not in every data row")
        if enc.get("type") == "quantitative" and not str(enc.get("title", "")).strip():
            problems.append(f"{name}: quantitative {channel} needs a title that names its unit")
        if mark_type == "bar" and enc.get("type") == "quantitative" and (enc.get("scale") or {}).get("zero") is False:
            problems.append(f"{name}: a bar's quantitative axis starts at zero")
    return problems


def check_charts(charts: list[dict[str, Any]], results: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [problem for spec in charts for problem in check_chart(spec, results)]


def numbers_in(text: str) -> list[str]:
    return NUMBER.findall(text)


def trace_findings(findings: dict[str, Any], results: dict[str, list[dict[str, Any]]], dataset_sha256: str) -> list[str]:
    """Every listed number equals its query result cell, and every number in a finding's text is listed."""
    problems = []
    if findings.get("dataset_sha256") != dataset_sha256:
        problems.append("findings: dataset_sha256 is not the pinned dataset")
    for i, finding in enumerate(findings.get("findings", []), start=1):
        listed = []
        for number in finding.get("numbers", []):
            rows = results.get(number.get("query"))
            row = number.get("row")
            if rows is None:
                problems.append(f"finding {i}: unknown query {number.get('query')!r}")
                continue
            if type(row) is not int or not 0 <= row < len(rows) or number.get("column") not in rows[row]:
                problems.append(f"finding {i}: {number.get('query')} has no row {row} column {number.get('column')!r}")
                continue
            if rows[row][number["column"]] != number.get("value"):
                problems.append(f"finding {i}: {number.get('value')!r} differs from {number['query']} row {row} {number['column']}")
                continue
            listed.append(number["value"])
        for token in numbers_in(finding.get("text", "")):
            places = len(token.split(".")[1]) if "." in token else 0
            if not any(type(v) in (int, float) and round(float(v), places) == float(token) for v in listed):
                problems.append(f"finding {i}: {token} in the text is not a listed number")
    return problems
