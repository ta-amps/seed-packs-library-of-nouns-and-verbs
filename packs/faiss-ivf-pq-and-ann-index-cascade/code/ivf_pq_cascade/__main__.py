"""CLI entry point for faiss-ivf-pq-and-ann-index-cascade."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .grid import load_default_grid_spec
from .ivf_pq import benchmark_ivf_pq_regimes, generate_clustered_corpus


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()

    if "vectors" in bundle and "queries" in bundle:
        vectors = [list(v) for v in bundle["vectors"]]
        queries = [list(q) for q in bundle["queries"]]
        doc_ids = list(bundle["doc_ids"]) if "doc_ids" in bundle else None
    else:
        corpus = generate_clustered_corpus(bundle.get("synthetic_corpus"), grid_spec=cfg)
        vectors = corpus["vectors"]
        queries = corpus["queries"]
        doc_ids = corpus["doc_ids"]

    report = benchmark_ivf_pq_regimes(
        vectors,
        queries,
        doc_ids=doc_ids,
        top_k=bundle.get("top_k"),
        regimes=bundle.get("regimes"),
        spec=cfg,
    )
    fast = report["regimes"]["fast_compact"]
    high = report["regimes"]["high_recall"]

    return {
        "num_vectors": report["num_vectors"],
        "dim": report["dim"],
        "num_queries": report["num_queries"],
        "top_k": report["top_k"],
        "fast_compact_pq_bytes": fast["pq_code_bytes_per_vector"],
        "fast_compact_compression_vs_float64": fast["compression_ratio_vs_float64"],
        "fast_compact_compression_vs_float32": fast["compression_ratio_vs_float32"],
        "fast_compact_recall_at_k": fast["recall_at_k"],
        "fast_compact_mean_adc_scanned": fast["mean_adc_scanned"],
        "fast_compact_mean_exact_reranked": fast["mean_exact_reranked"],
        "high_recall_pq_bytes": high["pq_code_bytes_per_vector"],
        "high_recall_compression_vs_float64": high["compression_ratio_vs_float64"],
        "high_recall_compression_vs_float32": high["compression_ratio_vs_float32"],
        "high_recall_recall_at_k": high["recall_at_k"],
        "high_recall_mean_adc_scanned": high["mean_adc_scanned"],
        "high_recall_mean_exact_reranked": high["mean_exact_reranked"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run faiss-ivf-pq-and-ann-index-cascade bundle evaluation."
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
