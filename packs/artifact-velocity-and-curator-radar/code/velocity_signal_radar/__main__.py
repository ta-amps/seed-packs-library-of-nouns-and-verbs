"""CLI entrypoint for deterministic radar bundle evaluation and AST/naming self-tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .grid_config import DomainAgnosticNamingGate, NodeGrid, ZeroHardcodedValuesAstGate
from .radar_engine import evaluate_radar_bundle


def run_self_test() -> dict[str, object]:
    pkg_dir = Path(__file__).resolve().parent
    grid = NodeGrid()
    ast_res = ZeroHardcodedValuesAstGate.scan_paths([pkg_dir])
    naming_res = DomainAgnosticNamingGate.scan_workspace(
        [pkg_dir],
        forbidden_tokens=grid.spec["forbidden_domain_tokens"],
        schema_ids=[grid.grid_id],
    )
    return {
        "ast_passed": ast_res["passed"],
        "ast_violations": ast_res["violation_count"],
        "naming_passed": naming_res["passed"],
        "naming_violations": naming_res["violation_count"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="velocity_signal_radar")
    parser.add_argument("--self-test", action="store_true", help="Run AST and domain-agnostic naming gates")
    parser.add_argument("--bundle", type=Path, help="Evaluate a JSON velocity radar bundle")
    args = parser.parse_args(argv)

    if args.self_test:
        summary = run_self_test()
        print(json.dumps(summary, sort_keys=True))
        return 0 if (summary["ast_passed"] and summary["naming_passed"]) else 1

    if args.bundle is not None:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        receipt = evaluate_radar_bundle(bundle)
        print(json.dumps(receipt, sort_keys=True, indent=1))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
