"""Check a CSV analysis at every step, with the standard library only.

Read the file's bytes and pin their digest, profile its schema, validate types and ranges, flag missing
values and outliers, run recorded queries with result digests, check chart specs kept as data, and trace
every number in the findings to a query result. Nothing here changes the data, draws a chart, calls a
model, opens a network connection or writes a file; it only reads and prints.
"""

from __future__ import annotations

from .checks import cell_problems, flag, profile, validate
from .outputs import VEGA_LITE_V5, check_chart, check_charts, numbers_in, trace_findings
from .query import run_queries, run_query
from .table import Table, canonical, digest, kind_of, read_csv

__all__ = ["VEGA_LITE_V5", "Table", "canonical", "cell_problems", "check_chart", "check_charts", "digest", "flag",
           "kind_of", "numbers_in", "profile", "read_csv", "run_queries", "run_query", "trace_findings", "validate"]
