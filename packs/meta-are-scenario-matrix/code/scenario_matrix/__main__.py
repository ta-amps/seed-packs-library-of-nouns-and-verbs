"""CLI entrypoint for the 1,000-Scenario Matrix generator and stakeholder digester."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .matrix_runner import (
    resolve_tuple_by_global_index,
    run_latin_hypercube_sweep_1000,
    run_worked_example,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scenario_matrix")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sweep = sub.add_parser("sweep", help="Run the 1,000-cell 4D Latin-hypercube sweep")
    p_sweep.add_argument("--seed", type=int, default=20261031)
    p_sweep.add_argument("--out", type=Path, help="Optional JSON output path")

    p_expand = sub.add_parser("expand", help="Resolve one tuple in [0, 10^12 - 1]")
    p_expand.add_argument("--global-index", type=int, required=True)

    p_worked = sub.add_parser("worked-example", help="Recompute worked example from JSON")
    p_worked.add_argument("--input", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "sweep":
        doc = run_latin_hypercube_sweep_1000(seed=args.seed)
        text = json.dumps(doc, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0
    if args.cmd == "expand":
        print(json.dumps(resolve_tuple_by_global_index(args.global_index), indent=2))
        return 0
    data = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(run_worked_example(data), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
