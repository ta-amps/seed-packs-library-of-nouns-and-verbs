"""Hybrid Okapi BM25 + facet/stack Reciprocal Rank Fusion (k=60) search over decomposed repositories."""

from __future__ import annotations

import math
import re
from typing import Any, Sequence

TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _record_text(rec: dict[str, Any]) -> str:
    parts = [
        str(rec.get("repo", "")).replace("/", " ").replace("-", " "),
        str(rec.get("domain", "")),
        str(rec.get("track", "")),
        " ".join(rec.get("meta_stack", [])),
        str(rec.get("primary_language", "")),
        str(rec.get("summary", "")),
        " ".join(t.get("name", "") + " " + t.get("verb_category", "") for t in rec.get("tasks", [])),
        " ".join(o.get("object_id", "") + " " + o.get("noun_category", "") for o in rec.get("task_objects", [])),
    ]
    return " ".join(parts)


class BM25Index:
    """Standard-library Okapi BM25 index (`k1=1.5, b=0.75`)."""

    def __init__(self, records: Sequence[dict[str, Any]], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.records = list(records)
        self.k1 = k1
        self.b = b
        self.doc_tokens: list[dict[str, int]] = []
        self.doc_lens: list[int] = []
        self.df: dict[str, int] = {}

        for rec in self.records:
            toks = tokenize(_record_text(rec))
            counts: dict[str, int] = {}
            for tok in toks:
                counts[tok] = counts.get(tok, 0) + 1
            self.doc_tokens.append(counts)
            self.doc_lens.append(len(toks))
            for tok in counts:
                self.df[tok] = self.df.get(tok, 0) + 1

        n_docs = len(self.records)
        self.avg_dl = (sum(self.doc_lens) / n_docs) if n_docs else 1.0

    def rank(self, query: str) -> list[tuple[str, float]]:
        q_tokens = tokenize(query)
        n_docs = len(self.records)
        if not q_tokens or n_docs == 0:
            return [(str(r["repo"]), 0.0) for r in self.records]

        scored: list[tuple[str, float]] = []
        for idx, rec in enumerate(self.records):
            tf_map = self.doc_tokens[idx]
            dl = self.doc_lens[idx]
            score = 0.0
            for qt in q_tokens:
                tf = tf_map.get(qt, 0)
                if tf == 0:
                    continue
                df = self.df.get(qt, 0)
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                denom = tf + self.k1 * (1.0 - self.b + self.b * (dl / max(1e-9, self.avg_dl)))
                score += idf * (tf * (self.k1 + 1.0)) / denom
            scored.append((str(rec["repo"]), round(score, 6)))

        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored


def score_facets(
    records: Sequence[dict[str, Any]],
    *,
    preferred_stack: Sequence[str] = (),
    preferred_domain: str | None = None,
    preferred_track: str | None = None,
    required_verb_categories: Sequence[str] = (),
    require_tests: bool = False,
) -> list[tuple[str, float]]:
    """Score records by structured Meta stack tags, domain, track, verb signature and test presence."""
    want_stack = {s.lower() for s in preferred_stack}
    want_verbs = set(required_verb_categories)
    scored: list[tuple[str, float]] = []

    for rec in records:
        score = 0.0
        rec_stack = {s.lower() for s in rec.get("meta_stack", [])}
        if want_stack:
            overlap = len(want_stack & rec_stack)
            union = len(want_stack | rec_stack)
            score += 2.0 * (overlap / max(1, union))
        if preferred_domain and preferred_domain.lower() in str(rec.get("domain", "")).lower():
            score += 1.5
        if preferred_track and preferred_track.lower() == str(rec.get("track", "")).lower():
            score += 1.0
        if want_verbs:
            present_verbs = {t.get("verb_category") for t in rec.get("tasks", [])}
            score += 1.5 * (len(want_verbs & present_verbs) / len(want_verbs))
        if require_tests and rec.get("tests_present"):
            score += 0.5
        if rec.get("mcp_adopted"):
            score += 0.25
        scored.append((str(rec["repo"]), round(score, 6)))

    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored


def reciprocal_rank_fusion(ranked_lists: Sequence[Sequence[tuple[str, float]]], *, k: int = 60) -> list[tuple[str, float]]:
    """Fuse multiple `(doc_id, score)` ranked lists via Reciprocal Rank Fusion `sum(1 / (k + rank))`."""
    if k <= 0:
        raise ValueError("RRF parameter k must be positive")
    fused: dict[str, float] = {}
    for rlist in ranked_lists:
        for rank_idx, (doc_id, raw_score) in enumerate(rlist, start=1):
            # Only award positive signal ranks when the ranker produced > 0 score (or if all 0, still deterministic)
            if raw_score <= 0.0:
                fused.setdefault(doc_id, 0.0)
                continue
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank_idx)
    out = [(doc_id, round(val, 6)) for doc_id, val in fused.items()]
    out.sort(key=lambda item: (-item[1], item[0]))
    return out


def hybrid_search(
    records: Sequence[dict[str, Any]],
    query: str,
    *,
    preferred_stack: Sequence[str] = (),
    preferred_domain: str | None = None,
    preferred_track: str | None = None,
    required_verb_categories: Sequence[str] = (),
    require_tests: bool = False,
    rrf_k: int = 60,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Run hybrid BM25 + facet/stack RRF (`k=60`) search and return top enriched matches."""
    by_repo = {str(r["repo"]): r for r in records}
    bm25_ranks = BM25Index(records).rank(query)
    facet_ranks = score_facets(
        records,
        preferred_stack=preferred_stack,
        preferred_domain=preferred_domain,
        preferred_track=preferred_track,
        required_verb_categories=required_verb_categories,
        require_tests=require_tests,
    )
    bm25_map = dict(bm25_ranks)
    facet_map = dict(facet_ranks)
    fused = reciprocal_rank_fusion([bm25_ranks, facet_ranks], k=rrf_k)

    results: list[dict[str, Any]] = []
    for repo_id, rrf_score in fused[: max(1, top_k)]:
        rec = by_repo[repo_id]
        results.append({
            "repo": repo_id,
            "rrf_score": rrf_score,
            "bm25_score": round(bm25_map.get(repo_id, 0.0), 4),
            "facet_score": round(facet_map.get(repo_id, 0.0), 4),
            "domain": rec["domain"],
            "track": rec["track"],
            "meta_stack": rec["meta_stack"],
            "task_count": len(rec["tasks"]),
            "task_object_count": len(rec["task_objects"]),
            "summary": rec["summary"],
        })
    return results
