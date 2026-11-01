"""Deterministic standard-library k-means++ initializer and Lloyd clustering."""

from __future__ import annotations

import random


def squared_l2(vec_a: list[float] | tuple[float, ...], vec_b: list[float] | tuple[float, ...]) -> float:
    """Compute exact squared Euclidean distance without exponent literals."""
    total = 0.0
    for a_val, b_val in zip(vec_a, vec_b):
        diff = a_val - b_val
        total += diff * diff
    return total


def nearest_centroid_index(
    vec: list[float] | tuple[float, ...],
    centroids: list[list[float]],
) -> tuple[int, float]:
    """Return (best_index, best_squared_distance) among centroids."""
    best_idx = 0
    best_dist = squared_l2(vec, centroids[0])
    for idx in range(1, len(centroids)):
        dist = squared_l2(vec, centroids[idx])
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx, best_dist


def kmeans_plus_plus_fit(
    vectors: list[list[float]],
    num_clusters: int,
    *,
    max_iters: int,
    seed: int,
    epsilon: float,
) -> list[list[float]]:
    """Fit deterministic k-means++ centroids in R^d."""
    if not vectors:
        raise ValueError("vectors must be non-empty")
    n_vecs = len(vectors)
    dim = len(vectors[0])
    k_eff = max(1, min(num_clusters, n_vecs))
    rng = random.Random(seed)

    first_idx = rng.randrange(n_vecs)
    centroids: list[list[float]] = [list(vectors[first_idx])]
    min_sq_dists = [squared_l2(vec, centroids[0]) for vec in vectors]

    for _ in range(1, k_eff):
        total_weight = sum(min_sq_dists)
        chosen_idx = 0
        if total_weight <= epsilon:
            chosen_idx = rng.randrange(n_vecs)
        else:
            target = rng.random() * total_weight
            running = 0.0
            chosen_idx = n_vecs - 1
            for idx, weight in enumerate(min_sq_dists):
                running += weight
                if running >= target:
                    chosen_idx = idx
                    break
        new_c = list(vectors[chosen_idx])
        centroids.append(new_c)
        for idx, vec in enumerate(vectors):
            d_new = squared_l2(vec, new_c)
            if d_new < min_sq_dists[idx]:
                min_sq_dists[idx] = d_new

    for _ in range(max_iters):
        sums = [[0.0] * dim for _ in range(k_eff)]
        counts = [0] * k_eff
        assign_dists = [0.0] * n_vecs

        for v_idx, vec in enumerate(vectors):
            c_idx, c_dist = nearest_centroid_index(vec, centroids)
            counts[c_idx] += 1
            assign_dists[v_idx] = c_dist
            acc = sums[c_idx]
            for d_idx in range(dim):
                acc[d_idx] += vec[d_idx]

        max_shift = 0.0
        for c_idx in range(k_eff):
            if counts[c_idx] == 0:
                farthest_idx = max(range(n_vecs), key=lambda idx: assign_dists[idx])
                updated = list(vectors[farthest_idx])
                assign_dists[farthest_idx] = 0.0
            else:
                inv_count = 1.0 / float(counts[c_idx])
                updated = [val * inv_count for val in sums[c_idx]]
            shift = squared_l2(centroids[c_idx], updated)
            if shift > max_shift:
                max_shift = shift
            centroids[c_idx] = updated

        if max_shift <= epsilon:
            break

    return centroids
