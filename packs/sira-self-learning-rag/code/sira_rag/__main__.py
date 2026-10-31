"""CLI entrypoint for SIRA self-learning RAG and 79-pack benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import run_79_pack_benchmark, run_worked_example


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sira_rag")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_bench = sub.add_parser("benchmark", help="Run the 60-query benchmark across packs/")
    p_bench.add_argument(
        "--packs-dir",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Path to packs/ directory",
    )
    p_bench.add_argument("--out", type=Path, help="Optional JSON output path")

    p_worked = sub.add_parser("worked-example", help="Recompute synthetic worked example")
    p_worked.add_argument("--input", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "benchmark":
        report = run_79_pack_benchmark(args.packs_dir)
        text = json.dumps(report, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0

    data = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(run_worked_example(data), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
