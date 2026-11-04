"""CLI entry point for dora-spinquant-and-adapter-merging."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .dora_and_ties import SubspaceInterferenceAndMergeRouter, WeightDecomposedLoraAnalyzer
from .grid import load_default_grid_spec
from .spinquant import FastWalshHadamardOutlierRotator


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()

    rotator = FastWalshHadamardOutlierRotator(
        rotation_seed=int(bundle.get("rotation_seed", cfg["spinquant"]["default_rotation_seed"])),
        quant_bits=int(bundle.get("quant_bits", cfg["spinquant"]["default_quant_bits"])),
        spec=cfg,
    )
    if "channel_matrix" in bundle:
        matrix = [[float(x) for x in row] for row in bundle["channel_matrix"]]
    else:
        matrix = rotator.generate_heavy_tailed_channel_matrix(
            rows=int(bundle.get("made_up_rows", cfg["spinquant"]["made_up_rows"])),
            cols=int(bundle.get("made_up_cols", cfg["spinquant"]["made_up_cols"])),
            outlier_channels=int(
                bundle.get("made_up_outlier_channels", cfg["spinquant"]["made_up_outlier_channels"])
            ),
            outlier_scale=float(
                bundle.get("made_up_outlier_scale", cfg["spinquant"]["made_up_outlier_scale"])
            ),
            seed=int(bundle.get("made_up_seed", cfg["spinquant"]["made_up_seed"])),
        )
    quant_report = rotator.evaluate_quantization(matrix)

    dora = WeightDecomposedLoraAnalyzer(spec=cfg)
    dora_input = bundle["dora_probe"]
    dora_report = dora.analyze_low_rank_update(
        base_weights=[[float(x) for x in row] for row in dora_input["base_weights"]],
        lora_b=[[float(x) for x in row] for row in dora_input["lora_b"]],
        lora_a=[[float(x) for x in row] for row in dora_input["lora_a"]],
        lora_scale=float(dora_input["lora_scale"]) if "lora_scale" in dora_input else None,
    )

    router = SubspaceInterferenceAndMergeRouter(spec=cfg)
    orthogonal_pair = [
        [[float(x) for x in row] for row in mat] for mat in bundle["orthogonal_adapters"]
    ]
    conflicting_pair = [
        [[float(x) for x in row] for row in mat] for mat in bundle["conflicting_adapters"]
    ]
    orth_route = router.route_adapters(orthogonal_pair)
    conf_route = router.route_adapters(conflicting_pair)

    return {
        "unrotated_max_to_rms": quant_report["unrotated_max_to_rms"],
        "rotated_max_to_rms": quant_report["rotated_max_to_rms"],
        "unrotated_excess_kurtosis": quant_report["unrotated_excess_kurtosis"],
        "rotated_excess_kurtosis": quant_report["rotated_excess_kurtosis"],
        "unrotated_quant_mse": quant_report["unrotated_quant_mse"],
        "rotated_quant_mse": quant_report["rotated_quant_mse"],
        "mse_reduction_factor": quant_report["mse_reduction_factor"],
        "dora_directional_cosine_delta": dora_report["mean_directional_cosine_delta"],
        "dora_relative_magnitude_delta": dora_report["mean_relative_magnitude_delta"],
        "dora_directional_to_magnitude_ratio": dora_report["directional_to_magnitude_ratio"],
        "orthogonal_frobenius_cosine": orth_route["max_abs_frobenius_cosine"],
        "orthogonal_sign_conflict_density": orth_route["sign_conflict_density"],
        "orthogonal_route": orth_route["recommended_strategy"],
        "conflicting_frobenius_cosine": conf_route["max_abs_frobenius_cosine"],
        "conflicting_sign_conflict_density": conf_route["sign_conflict_density"],
        "conflicting_route": conf_route["recommended_strategy"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run dora-spinquant-and-adapter-merging bundle evaluation."
    )
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    cfg = load_default_grid_spec()
    indent = int(cfg["formatting"]["json_indent"])
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
