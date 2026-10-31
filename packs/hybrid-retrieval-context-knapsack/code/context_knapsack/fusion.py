"""Okapi BM25 + dense cosine similarity + Reciprocal Rank Fusion (k=60)."""

from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric/underscore tokenizer."""
    return TOKEN_RE.findall(text.lower())


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Compute cosine similarity in [-1.0, 1.0], returning 0.0 on zero norms."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(float(a) * float(a) for a in vec_a))
    norm_b = math.sqrt(sum(float(b) * float(b) for b in vec_b))
    if norm_a <= 1e-12 or norm_b <= 1e-12:
        return 0.0
    return dot / (norm_a * norm_b)


def bm25_scores(
    query: str,
    documents: Sequence[Mapping[str, Any]],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> dict[str, float]:
    """Compute Okapi BM25 scores for documents keyed by `id` with `text`."""
    q_terms = tokenize(query)
    n_docs = len(documents)
    if n_docs == 0 or not q_terms:
        return {str(doc["id"]): 0.0 for doc in documents}

    doc_tokens: dict[str, list[str]] = {}
    df: dict[str, int] = {}
    total_len = 0
    for doc in documents:
        doc_id = str(doc["id"])
        toks = tokenize(str(doc.get("text", "")))
        doc_tokens[doc_id] = toks
        total_len += len(toks)
        for term in set(toks):
            df[term] = df.get(term, 0) + 1

    avgdl = max(1.0, total_len / n_docs)
    scores: dict[str, float] = {}
    for doc in documents:
        doc_id = str(doc["id"])
        toks = doc_tokens[doc_id]
        dl = len(toks)
        tf_map: dict[str, int] = {}
        for tok in toks:
            tf_map[tok] = tf_map.get(tok, 0) + 1
        score = 0.0
        for term in q_terms:
            tf = tf_map.get(term, 0)
            if tf == 0:
                continue
            n_q = df.get(term, 0)
            idf = math.log(1.0 + (n_docs - n_q + 0.5) / (n_q + 0.5))
            denom = tf + k1 * (1.0 - b + b * (dl / avgdl))
            score += idf * ((tf * (k1 + 1.0)) / denom)
        scores[doc_id] = round(score, 8)
    return scores


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[str]],
    *,
    rrf_k: int = 60,
    weights: Sequence[float] | None = None,
) -> dict[str, float]:
    """Fuse multiple ranked ID lists via weighted Reciprocal Rank Fusion (default k=60)."""
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights length must match ranked_lists length")

    fused: dict[str, float] = {}
    for weight, id_list in zip(weights, ranked_lists):
        for rank_idx, doc_id in enumerate(id_list, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + float(weight) / float(rrf_k + rank_idx)
    return {doc_id: round(score, 8) for doc_id, score in fused.items()}


def hybrid_rrf_rank(
    query: str,
    query_embedding: Sequence[float],
    candidates: Sequence[Mapping[str, Any]],
    *,
    rrf_k: int = 60,
    bm25_k1: float = 1.5,
    bm25_b: float = 0.75,
) -> list[dict[str, Any]]:
    """Rank candidate chunks by fusing BM25 lexical ranks and dense cosine ranks via RRF."""
    if not candidates:
        return []

    lexical = bm25_scores(query, candidates, k1=bm25_k1, b=bm25_b)
    dense = {
        str(c["id"]): round(cosine_similarity(query_embedding, c.get("embedding", [])), 8)
        for c in candidates
    }

    lex_order = [
        str(c["id"])
        for c in sorted(candidates, key=lambda item: (-lexical[str(item["id"])], str(item["id"])))
    ]
    dense_order = [
        str(c["id"])
        for c in sorted(candidates, key=lambda item: (-dense[str(item["id"])], str(item["id"])))
    ]
    fused = reciprocal_rank_fusion([lex_order, dense_order], rrf_k=rrf_k)

    lex_rank = {doc_id: idx for idx, doc_id in enumerate(lex_order, start=1)}
    dense_rank = {doc_id: idx for idx, doc_id in enumerate(dense_order, start=1)}

    results: list[dict[str, Any]] = []
    for cand in candidates:
        cid = str(cand["id"])
        results.append(
            {
                **dict(cand),
                "bm25_score": lexical[cid],
                "dense_cosine": dense[cid],
                "bm25_rank": lex_rank[cid],
                "dense_rank": dense_rank[cid],
                "rrf_score": fused[cid],
            }
        )
    results.sort(key=lambda item: (-item["rrf_score"], -item["bm25_score"], str(item["id"])))
    return results
