"""CLI entry point for coconut-latent-and-thought-budget-routing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .compressor import LatentStateSketchCompressor, OverthinkingLoopDetector
from .grid import load_default_grid_spec
from .router import AdaptiveReasoningBudgetRouter


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()
    regime = bundle.get("regime")

    router = AdaptiveReasoningBudgetRouter(regime=regime, spec=cfg)
    compressor = LatentStateSketchCompressor(regime=regime, spec=cfg)
    detector = OverthinkingLoopDetector(regime=regime, spec=cfg)

    routed = router.route_batch(list(bundle["tasks"]))
    regime_map = {str(d["id"]): str(d["selected_regime"]) for d in routed["decisions"]}
    clamped_ids = [str(d["id"]) for d in routed["decisions"] if bool(d["budget_clamped"])]

    comp = compressor.compress_trace(
        list(bundle["verbose_trace"]),
        ground_truth=bundle.get("ground_truth_invariants"),
    )
    loop_res = detector.inspect_trace(list(bundle["looping_trace"]))
    productive_res = detector.inspect_trace(list(bundle["verbose_trace"]))

    return {
        "task_regimes": regime_map,
        "budget_clamped_tasks": clamped_ids,
        "routed_total_tokens": int(routed["routed_total_tokens"]),
        "token_savings_fraction": float(routed["token_savings_fraction"]),
        "raw_trace_tokens": int(comp["raw_token_count"]),
        "compressed_checkpoint_tokens": int(comp["compressed_token_count"]),
        "compression_ratio": float(comp["compression_ratio"]),
        "meets_compression_target": bool(comp["meets_compression_target"]),
        "binding_constraint_recall": float(comp["binding_constraint_recall"]),
        "open_obligation_recall": float(comp["open_obligation_recall"]),
        "verified_hash_recall": float(comp["verified_hash_recall"]),
        "latent_vector_dims": len(comp["checkpoint"]["latent_state_vector"]),
        "overthinking_loop_detected": bool(loop_res["loop_detected"]),
        "overthinking_trigger_step": int(loop_res["trigger_step_index"]),
        "overthinking_tokens_saved": int(loop_res["tokens_saved_by_early_halt"]),
        "productive_trace_false_loop": bool(productive_res["loop_detected"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run coconut-latent-and-thought-budget-routing evaluation bundle."
    )
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    cfg = load_default_grid_spec()
    indent = int(cfg["constants"]["json_indent"])
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
