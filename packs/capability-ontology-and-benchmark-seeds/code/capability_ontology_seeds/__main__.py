"""CLI entrypoint for capability_ontology_seeds deterministic bundle verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import CONFIG_PATH, DomainAgnosticNamingGate, NodeGrid, ZeroHardcodedValuesAstGate, evaluate_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="capability_ontology_seeds",
        description="Run offline polyhierarchical ontology, seed digestion and Pareto benchmark checks.",
    )
    parser.add_argument("--bundle", type=Path, help="Path to JSON bundle to evaluate deterministically.")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run AST zero-magic-literal and domain-agnostic naming gates over package source.",
    )
    args = parser.parse_args(argv)

    grid = NodeGrid()
    if args.bundle is not None:
        bundle_data = json.loads(args.bundle.read_text(encoding="utf-8"))
        receipt = evaluate_bundle(bundle_data, grid=grid)
        print(json.dumps(receipt, indent=1 + 1, sort_keys=True))
        return 0

    pkg_dir = CONFIG_PATH.parent.parent
    ast_res = ZeroHardcodedValuesAstGate.scan_paths(
        [pkg_dir],
        allowed_identities=grid.spec["allowed_ast_identities"],
    )
    naming_res = DomainAgnosticNamingGate.scan_workspace(
        [pkg_dir],
        forbidden_tokens=grid.spec["forbidden_domain_tokens"],
        schema_ids=[grid.grid_id],
    )
    summary = {
        "grid_id": grid.grid_id,
        "ast_passed": ast_res["passed"],
        "ast_violations": ast_res["violation_count"],
        "naming_passed": naming_res["passed"],
        "naming_violations": naming_res["violation_count"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if (ast_res["passed"] and naming_res["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
