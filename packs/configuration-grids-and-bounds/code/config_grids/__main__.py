"""CLI entry point for configuration-grids-and-bounds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .ast_gate import ZeroHardcodedValuesAstGate
from .grid import NodeGrid
from .ledger import GridLedger, OperationCostLedger


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    grid = NodeGrid(bundle.get("grid_spec"))
    enumerated = grid.enumerate_cells()
    ledger = GridLedger(grid)
    cost_ledger = OperationCostLedger(grid, ledger)

    target_cell = grid.clamp_cell(bundle["candidate_cell"])
    for st in ("proposed", "dispatched", "evaluated"):
        res = ledger.transition(
            target_cell,
            st,
            worker_id=str(bundle["proposer_worker_id"]),
            key_id=str(bundle["proposer_key_id"]),
            metrics=bundle.get("metrics"),
        )
        assert res["ok"], res

    self_verify = ledger.transition(
        target_cell,
        "verified",
        worker_id=str(bundle["proposer_worker_id"]),
        key_id=str(bundle["proposer_key_id"]),
    )
    distinct_verify = ledger.transition(
        target_cell,
        "verified",
        worker_id=str(bundle["verifier_worker_id"]),
        key_id=str(bundle["verifier_key_id"]),
    )
    promote_res = ledger.transition(target_cell, "promoted")
    cost_ledger.record_observation(
        regime=str(bundle["regime"]),
        cell=target_cell,
        quality_score=float(bundle["metrics"]["quality_score"]),
        cost_units=float(bundle["metrics"]["cost_units"]),
    )
    resolved = cost_ledger.resolve_for_regime(str(bundle["regime"]))
    expanded_grid, expanded_axes = grid.auto_expand_if_saturated(target_cell)

    good_ast = ZeroHardcodedValuesAstGate.scan_source(str(bundle["clean_code_sample"]), source_name="clean.py")
    bad_ast = ZeroHardcodedValuesAstGate.scan_source(str(bundle["magic_literal_sample"]), source_name="magic.py")

    return {
        "represented_cells": len(enumerated["represented"]),
        "applicable_cells": len(enumerated["applicable"]),
        "self_verify_blocked": not self_verify["ok"],
        "promoted_state": str(promote_res["state"]),
        "resolved_source": str(resolved["source"]),
        "next_grid_generation": expanded_grid.generation,
        "expanded_axes": expanded_axes,
        "clean_ast_passed": bool(good_ast["passed"]),
        "magic_ast_violations": int(bad_ast["violation_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run configuration-grids-and-bounds receipt evaluation.")
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
