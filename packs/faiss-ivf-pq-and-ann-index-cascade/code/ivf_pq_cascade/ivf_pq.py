"""ProductQuantizedIvfIndex with k-means++ Voronoi cells, uint8 PQ codes, ADC lookup and exact rerank."""

from __future__ import annotations

import copy
import random
from typing import Any

from .grid import NodeGrid, load_default_grid_spec
from .kmeans import kmeans_plus_plus_fit, nearest_centroid_index, squared_l2


def exact_knn(
    vectors: list[list[float]],
    doc_ids: list[str],
    query: list[float],
    *,
    top_k: int,
) -> list[str]:
    """Compute exact brute-force L2 top-k document identifiers for ground-truth Recall@k."""
    scored = [(squared_l2(query, vec), idx) for idx, vec in enumerate(vectors)]
    scored.sort(key=lambda item: (item[0], item[1]))
    return [doc_ids[idx] for _, idx in scored[:top_k]]


def generate_clustered_corpus(
    corpus_spec: dict[str, Any] | None = None,
    *,
    grid_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a deterministic clustered vector dataset and noisy cluster-sampled queries."""
    cfg = grid_spec if grid_spec is not None else load_default_grid_spec()
    defaults = dict(cfg["made_up_corpus_defaults"])
    if corpus_spec is not None:
        defaults.update(corpus_spec)

    num_vectors = int(defaults["num_vectors"])
    dim = int(defaults["dim"])
    num_clusters = int(defaults["num_clusters"])
    num_queries = int(defaults["num_queries"])
    center_scale = float(defaults["center_scale"])
    cluster_spread = float(defaults["cluster_spread"])
    query_noise = float(defaults["query_noise"])
    seed = int(defaults["seed"])
    round_digits = int(cfg["numerics"]["round_digits"])

    rng = random.Random(seed)
    centers = [
        [rng.uniform(-center_scale, center_scale) for _ in range(dim)]
        for _ in range(num_clusters)
    ]

    vectors: list[list[float]] = []
    doc_ids: list[str] = []
    for idx in range(num_vectors):
        center = centers[idx % num_clusters]
        vec = [round(c_val + rng.gauss(0.0, cluster_spread), round_digits) for c_val in center]
        vectors.append(vec)
        doc_ids.append(f"vec-{idx}")

    queries: list[list[float]] = []
    for q_idx in range(num_queries):
        anchor = vectors[(q_idx * num_clusters + q_idx) % num_vectors]
        q_vec = [round(v_val + rng.gauss(0.0, query_noise), round_digits) for v_val in anchor]
        queries.append(q_vec)

    return {
        "vectors": vectors,
        "doc_ids": doc_ids,
        "queries": queries,
    }


class ProductQuantizedIvfIndex:
    """Inverted File + Product Quantization (IVF-PQ) index with ADC lookup tables and top-R reranking."""

    def __init__(
        self,
        *,
        cell_overrides: dict[str, Any] | None = None,
        regime_name: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        grid = NodeGrid(cfg)
        num = cfg["numerics"]

        base_cell = grid.resolve_regime(regime_name) if regime_name is not None else grid.clamp_cell({})
        if cell_overrides is not None:
            merged = dict(base_cell)
            merged.update(cell_overrides)
            base_cell = grid.clamp_cell(merged)

        self.cell = base_cell
        self.cell_id = grid.cell_id(base_cell)
        self.nlist = int(base_cell["nlist"])
        self.nprobe = int(base_cell["nprobe"])
        self.subspaces_m = int(base_cell["subspaces_m"])
        self.subspace_centroids_k = int(base_cell["subspace_centroids_k"])
        self.use_exact_rerank = bool(base_cell["use_exact_rerank"])
        self.rerank_top_r = int(base_cell["rerank_top_r"])

        self._eps = float(num["epsilon"])
        self._round_digits = int(num["round_digits"])
        self._float64_bytes = int(num["float64_bytes"])
        self._float32_bytes = int(num["float32_bytes"])
        self._max_uint8 = int(num["max_uint8_centroids"])
        self._coarse_iters = int(num["coarse_kmeans_iters"])
        self._pq_iters = int(num["pq_kmeans_iters"])
        self._seed = int(num["default_seed"])

        if self.subspace_centroids_k < 1 or self.subspace_centroids_k > self._max_uint8:
            raise ValueError("subspace_centroids_k must fit inside uint8 code range")

        self.dim = 0
        self.sub_dim = 0
        self._vectors: list[list[float]] = []
        self._doc_ids: list[str] = []
        self.coarse_centroids: list[list[float]] = []
        self.pq_codebooks: list[list[list[float]]] = []
        self.inverted_lists: list[list[tuple[int, bytes]]] = []

    def fit(self, vectors: list[list[float]], doc_ids: list[str] | None = None) -> ProductQuantizedIvfIndex:
        """Train coarse Voronoi centroids + residual PQ sub-codebooks and index compact uint8 codes."""
        if not vectors:
            raise ValueError("vectors must be non-empty")
        dim = len(vectors[0])
        if dim == 0 or dim % self.subspaces_m != 0:
            raise ValueError(f"vector dimension {dim} must be divisible by subspaces_m={self.subspaces_m}")

        self.dim = dim
        self.sub_dim = dim // self.subspaces_m
        self._vectors = [list(v) for v in vectors]
        self._doc_ids = list(doc_ids) if doc_ids is not None else [f"vec-{i}" for i in range(len(vectors))]

        eff_nlist = min(self.nlist, len(self._vectors))
        self.coarse_centroids = kmeans_plus_plus_fit(
            self._vectors,
            eff_nlist,
            max_iters=self._coarse_iters,
            seed=self._seed,
            epsilon=self._eps,
        )

        coarse_assignments: list[int] = []
        residuals: list[list[float]] = []
        for vec in self._vectors:
            c_idx, _ = nearest_centroid_index(vec, self.coarse_centroids)
            coarse_assignments.append(c_idx)
            c_vec = self.coarse_centroids[c_idx]
            residuals.append([v_val - c_val for v_val, c_val in zip(vec, c_vec)])

        self.pq_codebooks = []
        for m_idx in range(self.subspaces_m):
            start = m_idx * self.sub_dim
            end = start + self.sub_dim
            sub_vecs = [res[start:end] for res in residuals]
            eff_k = min(self.subspace_centroids_k, len(sub_vecs))
            codebook_m = kmeans_plus_plus_fit(
                sub_vecs,
                eff_k,
                max_iters=self._pq_iters,
                seed=self._seed + m_idx + 1,
                epsilon=self._eps,
            )
            self.pq_codebooks.append(codebook_m)

        self.inverted_lists = [[] for _ in range(len(self.coarse_centroids))]
        for vec_idx, res in enumerate(residuals):
            code_ints: list[int] = []
            for m_idx in range(self.subspaces_m):
                start = m_idx * self.sub_dim
                end = start + self.sub_dim
                sub_res = res[start:end]
                q_idx, _ = nearest_centroid_index(sub_res, self.pq_codebooks[m_idx])
                code_ints.append(q_idx)
            pq_bytes = bytes(code_ints)
            self.inverted_lists[coarse_assignments[vec_idx]].append((vec_idx, pq_bytes))

        return self

    def memory_footprint(self) -> dict[str, Any]:
        """Compute exact PQ byte compression ratios vs dense float64 and float32 vectors."""
        raw_f64 = self.dim * self._float64_bytes
        raw_f32 = self.dim * self._float32_bytes
        pq_bytes = self.subspaces_m
        total_pq_payload_bytes = sum(
            len(code_bytes) for inv_list in self.inverted_lists for _, code_bytes in inv_list
        )
        return {
            "num_indexed_vectors": len(self._vectors),
            "dim": self.dim,
            "pq_code_bytes_per_vector": pq_bytes,
            "float64_bytes_per_vector": raw_f64,
            "float32_bytes_per_vector": raw_f32,
            "compression_ratio_vs_float64": round(float(raw_f64) / float(pq_bytes), self._round_digits),
            "compression_ratio_vs_float32": round(float(raw_f32) / float(pq_bytes), self._round_digits),
            "total_pq_payload_bytes": total_pq_payload_bytes,
        }

    def search(self, query: list[float], *, top_k: int) -> dict[str, Any]:
        """Search nprobe Voronoi cells with Asymmetric Distance Computation (ADC) + optional top-R rerank."""
        if not self.coarse_centroids:
            raise RuntimeError("index must be fitted before search")
        eff_probe = min(self.nprobe, len(self.coarse_centroids))
        coarse_ranked = sorted(
            ((squared_l2(query, c_vec), c_idx) for c_idx, c_vec in enumerate(self.coarse_centroids)),
            key=lambda item: (item[0], item[1]),
        )
        probed_cells = [c_idx for _, c_idx in coarse_ranked[:eff_probe]]

        adc_candidates: list[tuple[float, int]] = []
        for c_idx in probed_cells:
            c_vec = self.coarse_centroids[c_idx]
            q_residual = [q_val - c_val for q_val, c_val in zip(query, c_vec)]

            # Build M x K_sub Asymmetric Distance Computation lookup table
            lut: list[list[float]] = []
            for m_idx in range(self.subspaces_m):
                start = m_idx * self.sub_dim
                end = start + self.sub_dim
                q_sub = q_residual[start:end]
                codebook_m = self.pq_codebooks[m_idx]
                lut.append([squared_l2(q_sub, sub_cent) for sub_cent in codebook_m])

            for vec_idx, code_bytes in self.inverted_lists[c_idx]:
                approx_dist = 0.0
                for m_idx in range(self.subspaces_m):
                    approx_dist += lut[m_idx][code_bytes[m_idx]]
                adc_candidates.append((approx_dist, vec_idx))

        adc_candidates.sort(key=lambda item: (item[0], item[1]))

        if self.use_exact_rerank and self.rerank_top_r > 0:
            shortlist_cap = max(top_k, self.rerank_top_r)
            shortlist = adc_candidates[:shortlist_cap]
            reranked = [
                (squared_l2(query, self._vectors[vec_idx]), vec_idx)
                for _, vec_idx in shortlist
            ]
            reranked.sort(key=lambda item: (item[0], item[1]))
            final_pairs = reranked[:top_k]
            exact_evals = len(shortlist)
        else:
            final_pairs = adc_candidates[:top_k]
            exact_evals = 0

        return {
            "hits": [
                {
                    "doc_id": self._doc_ids[vec_idx],
                    "distance_sq": round(dist_val, self._round_digits),
                }
                for dist_val, vec_idx in final_pairs
            ],
            "probed_cells": probed_cells,
            "adc_scanned_count": len(adc_candidates),
            "exact_reranked_count": exact_evals,
        }


def benchmark_ivf_pq_regimes(
    vectors: list[list[float]],
    queries: list[list[float]],
    *,
    doc_ids: list[str] | None = None,
    top_k: int | None = None,
    regimes: list[str] | None = None,
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Benchmark memory compression and Recall@k across IVF-PQ configuration regimes."""
    cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
    round_digits = int(cfg["numerics"]["round_digits"])
    k_val = int(top_k if top_k is not None else cfg["numerics"]["default_top_k"])
    ids = list(doc_ids) if doc_ids is not None else [f"vec-{i}" for i in range(len(vectors))]
    regime_names = list(regimes) if regimes is not None else ["fast_compact", "high_recall"]

    ground_truth = [set(exact_knn(vectors, ids, q_vec, top_k=k_val)) for q_vec in queries]

    results: dict[str, dict[str, Any]] = {}
    for reg_name in regime_names:
        idx = ProductQuantizedIvfIndex(regime_name=reg_name, spec=cfg).fit(vectors, ids)
        mem = idx.memory_footprint()
        recall_sum = 0.0
        adc_sum = 0
        rerank_sum = 0

        for q_vec, gt_set in zip(queries, ground_truth):
            out = idx.search(q_vec, top_k=k_val)
            pred_ids = {hit["doc_id"] for hit in out["hits"]}
            recall_sum += float(len(pred_ids & gt_set)) / float(max(1, len(gt_set)))
            adc_sum += int(out["adc_scanned_count"])
            rerank_sum += int(out["exact_reranked_count"])

        q_count = float(max(1, len(queries)))
        results[reg_name] = {
            "cell_id": idx.cell_id,
            "pq_code_bytes_per_vector": mem["pq_code_bytes_per_vector"],
            "compression_ratio_vs_float64": mem["compression_ratio_vs_float64"],
            "compression_ratio_vs_float32": mem["compression_ratio_vs_float32"],
            "recall_at_k": round(recall_sum / q_count, round_digits),
            "mean_adc_scanned": round(float(adc_sum) / q_count, round_digits),
            "mean_exact_reranked": round(float(rerank_sum) / q_count, round_digits),
        }

    return {
        "num_vectors": len(vectors),
        "dim": len(vectors[0]),
        "num_queries": len(queries),
        "top_k": k_val,
        "regimes": results,
    }
