"""CLI entry point for execution-hooks-and-verifiers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .compiler import PortableHookCompiler
from .dag import ComposableVerifierDagAndMutationGate


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Compile 4-stage hooks, evaluate pre_tool calls, execute Verifier DAGs, audit sensitivity, and emit tombstones."""
    grid_cell = bundle.get("grid_cell")
    compiler = PortableHookCompiler(grid_cell)
    compiled_all = compiler.compile_all_harnesses(bundle["hook_spec"])
    all_disable_bypass = all(
        bool(cfg.get("disable_bypass_permissions")) is True for cfg in compiled_all.values()
    )

    pre_tool_decisions = {
        str(call["call_id"]): compiler.evaluate_pre_tool(call)["decision"]
        for call in bundle["pre_tool_calls"]
    }

    dag_engine = ComposableVerifierDagAndMutationGate(grid_cell)
    good_dag = dag_engine.execute_verifier_dag(bundle["verifier_dag"], bundle["valid_submission"])
    bad_dag = dag_engine.execute_verifier_dag(bundle["verifier_dag"], bundle["failing_submission"])

    audit_verdicts: dict[str, str] = {}
    for check_spec in bundle["sensitivity_audits"]:
        node_cfg = check_spec["verifier_node"]
        verdict = dag_engine.audit_verifier_sensitivity(
            lambda sample, n=node_cfg: bool(dag_engine.run_single_verifier(n, sample)["passed"]),
            clean_twins=check_spec["clean_twins"],
            mutated_negatives=check_spec["mutated_negatives"],
        )
        audit_verdicts[str(check_spec["audit_id"])] = str(verdict["classification"])

    failed_reasons = [
        str(bad_dag["results"][vid]["reason"])
        for vid in bad_dag["failed_verifiers"]
    ]
    tombstone = dag_engine.extract_negative_tombstone(
        failed_stage="pre_submit",
        approach_label=str(bundle["failing_submission"].get("approach_label", "candidate_attempt")),
        failed_verifiers=bad_dag["failed_verifiers"],
        raw_diagnostics=failed_reasons,
    )

    return {
        "compiled_harnesses": sorted(compiled_all.keys()),
        "all_disable_bypass_permissions": all_disable_bypass,
        "pre_tool_decisions": pre_tool_decisions,
        "valid_dag_passed": bool(good_dag["all_passed"]),
        "failing_dag_failed_verifiers": bad_dag["failed_verifiers"],
        "failing_dag_skipped_verifiers": bad_dag["skipped_verifiers"],
        "mutation_audit_verdicts": audit_verdicts,
        "tombstone_id": str(tombstone["tombstone_id"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run execution-hooks-and-verifiers bundle evaluation.")
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
