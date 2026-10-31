"""Exact 0/1 knapsack solver and redundancy-penalized token-budget context packer."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .dedup_and_sanitize import exact_shingle_jaccard
from .fusion import cosine_similarity

UTILITY_SCALE = 100_000


def solve_01_knapsack(
    items: Sequence[Mapping[str, Any]],
    token_budget: int,
    *,
    value_key: str = "utility",
    weight_key: str = "tokens",
) -> dict[str, Any]:
    """Solve exact integer-weight 0/1 knapsack via dynamic programming."""
    if token_budget < 0:
        raise ValueError("token_budget must be non-negative")

    valid_items: list[tuple[int, Mapping[str, Any], int, int]] = []
    for idx, item in enumerate(items):
        weight = int(item[weight_key])
        if weight <= 0 or weight > token_budget:
            continue
        scaled_val = max(0, int(round(float(item[value_key]) * UTILITY_SCALE)))
        valid_items.append((idx, item, weight, scaled_val))

    n = len(valid_items)
    if n == 0 or token_budget == 0:
        return {"selected_ids": [], "total_tokens": 0, "total_utility": 0.0}

    # dp[i][w] stores maximum scaled utility using prefix valid_items[:i] under budget w
    dp = [[0] * (token_budget + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        _, _, weight, val = valid_items[i - 1]
        prev_row = dp[i - 1]
        cur_row = dp[i]
        for w in range(token_budget + 1):
            best = prev_row[w]
            if weight <= w:
                cand = prev_row[w - weight] + val
                if cand > best:
                    best = cand
            cur_row[w] = best

    # Backtrack deterministically
    chosen_indices: list[int] = []
    rem = token_budget
    for i in range(n, 0, -1):
        if dp[i][rem] != dp[i - 1][rem]:
            orig_idx, _, weight, _ = valid_items[i - 1]
            chosen_indices.append(orig_idx)
            rem -= weight
    chosen_indices.reverse()

    selected_ids = [str(items[idx]["id"]) for idx in chosen_indices]
    total_tokens = sum(int(items[idx][weight_key]) for idx in chosen_indices)
    total_utility = round(sum(float(items[idx][value_key]) for idx in chosen_indices), 6)
    return {
        "selected_ids": selected_ids,
        "total_tokens": total_tokens,
        "total_utility": total_utility,
    }


def _chunk_overlap(chunk_a: Mapping[str, Any], chunk_b: Mapping[str, Any]) -> float:
    lex_sim = exact_shingle_jaccard(str(chunk_a.get("text", "")), str(chunk_b.get("text", "")), shingle_size=2)
    emb_a = chunk_a.get("embedding")
    emb_b = chunk_b.get("embedding")
    if isinstance(emb_a, Sequence) and isinstance(emb_b, Sequence) and emb_a and emb_b:
        dense_sim = max(0.0, cosine_similarity(emb_a, emb_b))
        return 0.5 * lex_sim + 0.5 * dense_sim
    return lex_sim


def pack_context_knapsack(
    chunks: Sequence[Mapping[str, Any]],
    *,
    token_budget: int,
    redundancy_lambda: float = 0.35,
    utility_key: str = "rrf_score",
) -> dict[str, Any]:
    """Pack sanitized chunks into a strict token budget using redundancy-penalized 0/1 knapsack.

    First computes marginal redundancy-adjusted utilities against higher-ranked non-redundant
    anchors (`u_i' = max(0, u_i * (1 - redundancy_lambda * max_{j < i} sim(i, j)))`), then solves
    the exact 0/1 dynamic-programming knapsack over `(tokens_i, u_i')` so high-value compact
    combinations beat a single bloated chunk while penalizing redundant coverage.
    """
    if token_budget < 0:
        raise ValueError("token_budget must be non-negative")

    adjusted_items: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        base_u = float(chunk.get(utility_key, chunk.get("utility", 0.0)))
        max_prior_sim = 0.0
        for prior in chunks[:idx]:
            sim = _chunk_overlap(chunk, prior)
            if sim > max_prior_sim:
                max_prior_sim = sim
        penalty_factor = max(0.0, 1.0 - redundancy_lambda * max_prior_sim)
        adj_u = round(base_u * penalty_factor, 8)
        adjusted_items.append(
            {
                **dict(chunk),
                "base_utility": round(base_u, 8),
                "max_prior_overlap": round(max_prior_sim, 6),
                "adjusted_utility": adj_u,
            }
        )

    dp_res = solve_01_knapsack(
        adjusted_items,
        token_budget=token_budget,
        value_key="adjusted_utility",
        weight_key="tokens",
    )
    selected_set = set(dp_res["selected_ids"])
    packed_chunks = [item for item in adjusted_items if str(item["id"]) in selected_set]

    return {
        "token_budget": token_budget,
        "selected_ids": dp_res["selected_ids"],
        "total_tokens": dp_res["total_tokens"],
        "budget_utilization": round(dp_res["total_tokens"] / float(token_budget), 4) if token_budget > 0 else 0.0,
        "total_adjusted_utility": dp_res["total_utility"],
        "packed_chunks": packed_chunks,
    }
