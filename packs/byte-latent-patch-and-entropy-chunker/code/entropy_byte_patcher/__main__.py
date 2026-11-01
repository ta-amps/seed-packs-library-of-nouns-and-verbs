"""CLI entry point for byte-latent-patch-and-entropy-chunker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .allocator import SurpriseProportionalBudgetAllocator
from .grid import load_default_grid_spec
from .patcher import DynamicByteEntropyPatcher


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()
    regime = bundle.get("regime")

    patcher = DynamicByteEntropyPatcher(regime=regime, spec=cfg)
    corpus = [str(s) for s in bundle.get("calibration_corpus", [])]
    if corpus:
        patcher.fit_corpus(corpus)

    online = bool(bundle.get("online_update", False))
    seg = patcher.segment_stream(str(bundle["clean_stream"]), online_update=online)

    allocator = SurpriseProportionalBudgetAllocator(regime=regime, spec=cfg)
    alloc = allocator.allocate_budget(seg["patches"])
    robust = allocator.benchmark_corruption_robustness(
        str(bundle["clean_stream"]),
        str(bundle["corrupted_stream"]),
        calibration_corpus=corpus,
        online_update=online,
    )

    lengths = [int(p["byte_length"]) for p in seg["patches"]]
    reasons = sorted({str(p["boundary_reason"]) for p in seg["patches"]})

    return {
        "total_bytes": int(seg["total_bytes"]),
        "patch_count": int(seg["patch_count"]),
        "min_observed_patch_bytes": min(lengths) if lengths else 0,
        "max_observed_patch_bytes": max(lengths) if lengths else 0,
        "mean_patch_bytes": float(seg["mean_patch_bytes"]),
        "reconstructed_exact": bool(seg["reconstructed_exact"]),
        "boundary_reasons_triggered": reasons,
        "total_allocated_slots": sum(int(a["surprise_slots"]) for a in alloc["allocations"]),
        "high_entropy_surprise_budget_share": float(alloc["high_entropy_surprise_budget_share"]),
        "high_entropy_byte_budget_share": float(alloc["high_entropy_byte_budget_share"]),
        "high_entropy_focus_gain": float(alloc["high_entropy_focus_gain"]),
        "dynamic_preserved_patch_fraction": float(robust["dynamic_preserved_patch_fraction"]),
        "fixed_stride_preserved_chunk_fraction": float(
            robust["fixed_stride_preserved_chunk_fraction"]
        ),
        "boundary_resync_gain": float(robust["boundary_resync_gain"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run byte-latent-patch-and-entropy-chunker evaluation bundle."
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
