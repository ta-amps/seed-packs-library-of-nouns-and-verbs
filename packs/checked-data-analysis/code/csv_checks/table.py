"""Read a CSV file's bytes into a table, and the value types every later step shares.

Rows are numbered from 1 for the first data row after the header, in every report. Nothing is
converted silently: a value is missing only when it equals one of the request's missing tokens, and a
value that does not parse as a column's declared type stays a string and is reported.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

DEFAULT_MISSING = ("", "NA", "N/A", "null")
KINDS = ("integer", "number", "date", "boolean", "string")
INTEGER = re.compile(r"[+-]?[0-9]+")
NUMBER = re.compile(r"[+-]?([0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)([eE][+-]?[0-9]+)?")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    """SHA-256 of a JSON value's canonical form: sorted keys, no spaces, UTF-8."""
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass
class Table:
    sha256: str
    header: list[str]
    rows: list[list[str]]
    bom: bool
    delimiter: str
    ragged_rows: list[int] = field(default_factory=list)

    def column(self, name: str) -> list[str | None]:
        """One column's raw values, None where a ragged row is too short to have it."""
        index = self.header.index(name)
        return [row[index] if index < len(row) else None for row in self.rows]


def read_csv(data: bytes, delimiter: str = ",") -> Table:
    """RFC 4180 style: UTF-8 (a byte order mark is removed and recorded), a header row, quoted fields allowed."""
    text = data.decode("utf-8")
    bom = text.startswith("﻿")
    if bom:
        text = text[1:]
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("the file has no header row") from None
    rows = [row for row in reader]
    ragged = [i for i, row in enumerate(rows, start=1) if len(row) != len(header)]
    return Table(hashlib.sha256(data).hexdigest(), header, rows, bom, delimiter, ragged)


def kind_of(raw: str) -> str:
    """The narrowest kind a non-missing raw value parses as."""
    if INTEGER.fullmatch(raw):
        return "integer"
    if NUMBER.fullmatch(raw):
        return "number"
    if DATE.fullmatch(raw):
        try:
            date.fromisoformat(raw)
            return "date"
        except ValueError:
            return "string"
    if raw in ("true", "false"):
        return "boolean"
    return "string"


def fits(raw: str, declared: str) -> bool:
    """Whether a raw value parses as the declared type; an integer also fits number."""
    kind = kind_of(raw)
    return kind == declared or (declared == "number" and kind == "integer") or declared == "string"


def convert(raw: str, declared: str) -> Any:
    """The typed value of a raw value that fits its declared type; dates stay ISO strings, which sort correctly."""
    if declared == "integer":
        return int(raw)
    if declared == "number":
        return float(raw)
    if declared == "boolean":
        return raw == "true"
    return raw


def is_missing(raw: str | None, missing: tuple[str, ...] | list[str]) -> bool:
    return raw is None or raw in missing
