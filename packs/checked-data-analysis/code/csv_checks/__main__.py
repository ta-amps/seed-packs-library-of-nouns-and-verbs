"""Command line: profile, validate, flag and query a CSV file, and check chart specs and findings, as JSON.

  python -m csv_checks profile --csv DATA.csv --request REQUEST.json
  python -m csv_checks validate --csv DATA.csv --request REQUEST.json
  python -m csv_checks flag --csv DATA.csv --request REQUEST.json
  python -m csv_checks query --csv DATA.csv --request REQUEST.json --queries QUERIES.json
  python -m csv_checks charts --charts CHARTS.json --results RESULTS.json
  python -m csv_checks trace --findings FINDINGS.json --results RESULTS.json

QUERIES.json holds {"queries": [...]}; RESULTS.json is the query command's output; CHARTS.json holds
{"charts": [...]}. It reads only the files named and writes only to standard output. charts and trace exit
1 when they find a problem; a validation with violations is a result, not an error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .checks import flag, profile, validate
from .outputs import check_charts, trace_findings
from .query import run_queries
from .table import read_csv


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def by_id(results: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {item["id"]: item["result"] for item in results["results"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="csv_checks", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("profile", "validate", "flag", "query"):
        command = sub.add_parser(name)
        command.add_argument("--csv", type=Path, required=True)
        command.add_argument("--request", type=Path, required=True)
        if name == "query":
            command.add_argument("--queries", type=Path, required=True)
    charts = sub.add_parser("charts")
    charts.add_argument("--charts", type=Path, required=True)
    charts.add_argument("--results", type=Path, required=True)
    trace = sub.add_parser("trace")
    trace.add_argument("--findings", type=Path, required=True)
    trace.add_argument("--results", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command in ("charts", "trace"):
        results = load(args.results)
        if args.command == "charts":
            problems = check_charts(load(args.charts)["charts"], by_id(results))
        else:
            problems = trace_findings(load(args.findings), by_id(results), results["dataset_sha256"])
        print(json.dumps({"problems": problems}, indent=1))
        return 1 if problems else 0
    request = load(args.request)
    table = read_csv(args.csv.read_bytes(), request["dataset"]["delimiter"])
    if args.command == "profile":
        out = profile(table, request)
    elif args.command == "validate":
        out = validate(table, request)
    elif args.command == "flag":
        out = flag(table, request)
    else:
        out = run_queries(table, request, flag(table, request), load(args.queries)["queries"])
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
