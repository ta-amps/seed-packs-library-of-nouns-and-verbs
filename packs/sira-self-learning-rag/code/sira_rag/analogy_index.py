"""RaRftAnalogyIndex: structural problem-isomorphism tagging and single-shot hybrid retrieval."""

from __future__ import annotations

import math
import time
from collections import Counter
from typing import Any

from .noun_enricher import tokenize

STRUCTURAL_FRAMES_12: dict[str, dict[str, Any]] = {
    "split-sensitive-vs-public": {
        "description": "Keep private or PII records local while delegating public/statutory sub-tasks.",
        "pack_markers": frozenset({"private", "confidential", "privacy", "local", "donor", "split", "shelter", "handwritten", "victim", "masked"}),
        "query_markers": frozenset({"private", "confidential", "pii", "hipaa", "local", "split", "separate", "sensitive", "clinic", "patient", "shelter", "masked"}),
    },
    "exclusive-lease-fencing": {
        "description": "Single-claimant lease with monotonic fencing tokens, wire grant denial and handoff pins.",
        "pack_markers": frozenset({"lease", "fencing", "idempotency", "atomic", "preemption", "grant", "wire", "slice", "rejection", "handoff"}),
        "query_markers": frozenset({"lease", "fencing", "fence", "stale", "failover", "idempotent", "grid", "substation", "wire", "slice", "handoff"}),
    },
    "independent-two-step-review": {
        "description": "Separation of duties (drafter != reviewer / proposer != verifier) before sign-off.",
        "pack_markers": frozenset({"distinct_reviewer", "independent", "second", "opinion", "panel", "disagreements", "skeptic", "proposer", "verifier"}),
        "query_markers": frozenset({"independent", "reviewer", "pharmacist", "pharmacists", "disagree", "separation", "duties", "proposer", "verifier", "second", "opinion"}),
    },
    "cas-promotion": {
        "description": "Optimistic compare-and-set versioned state transition with conflict stop and rollback.",
        "pack_markers": frozenset({"compare_and_set", "update_slot", "rollback", "parity", "supersedes", "landed", "relink", "redirected"}),
        "query_markers": frozenset({"cas", "compare", "rollback", "promote", "supersede", "concurrent", "parity", "rollout", "firmware", "relink", "redirects"}),
    },
    "zero-token-memoized-reuse": {
        "description": "Zero-model deterministic rule execution or cached prior artifact pin reuse.",
        "pack_markers": frozenset({"reuse", "stored", "memoized", "triggers", "lookup", "replay", "break", "even", "prior", "alternatives"}),
        "query_markers": frozenset({"reuse", "memoize", "zero", "replay", "lookup", "prior", "alternatives", "break", "even", "existing"}),
    },
    "paired-bootstrap-holdout-gate": {
        "description": "Pre-registered holdout statistical CI promotion gate with n-gram disjointness.",
        "pack_markers": frozenset({"bootstrap", "holdout", "lora", "tuning", "disjointness", "jaccard", "champion", "twin", "scorer"}),
        "query_markers": frozenset({"bootstrap", "holdout", "lora", "adapter", "memorization", "champion", "twin", "rubric", "pre", "registered"}),
    },
    "budgeted-knapsack-selection": {
        "description": "Exact token/cost ceiling subset packing with MinHash/overlap deduplication.",
        "pack_markers": frozenset({"knapsack", "minhash", "rrf", "ceiling", "redundancy", "sanitized", "injected", "chunks"}),
        "query_markers": frozenset({"knapsack", "ceiling", "duplicate", "redundant", "injection", "chunks", "pallets", "cargo"}),
    },
    "purged-temporal-regime-audit": {
        "description": "Causal walk-forward split with embargo window and multiple-testing deflation.",
        "pack_markers": frozenset({"purged", "embargo", "walk", "regime", "deflated", "sharpe", "turnover", "leakage"}),
        "query_markers": frozenset({"lookahead", "embargo", "walk", "temporal", "leakage", "regime", "volatility", "biomarker", "backtest"}),
    },
    "multi-frame-temporal-invariant": {
        "description": "Windowed sequential frame/cut dwell, zoom stability, loudness and caption sync check.",
        "pack_markers": frozenset({"dwell", "crossfade", "lufs", "loudness", "burns", "wpm", "freezedetect", "lavfi", "easing", "ipa"}),
        "query_markers": frozenset({"dwell", "crossfade", "zoom", "drift", "loudness", "freezedetect", "lavfi", "easing", "ipa", "phoneme"}),
    },
    "adversarial-mutation-kill-check": {
        "description": "Validating a test or rubric by mutating known-good fixtures and injecting boundary cases.",
        "pack_markers": frozenset({"mutations", "kills", "operators", "trusted", "unicode", "nfc", "oracle", "canary"}),
        "query_markers": frozenset({"mutate", "mutation", "grader", "validator", "kill", "poisoned", "unicode", "nfc", "oracle"}),
    },
    "rate-paced-burst-fanout": {
        "description": "Token-bucket / backpressure-paced parallel worker swarm and credit cascade.",
        "pack_markers": frozenset({"tpm", "swarm", "baseten", "fireworks", "modal", "multilora", "cascade", "pareto", "harnesstax"}),
        "query_markers": frozenset({"burst", "swarm", "tpm", "bucket", "cascade", "credits", "serverless", "multilora", "pareto", "harnesstax"}),
    },
    "cited-verbatim-preservation": {
        "description": "Exact quote, slang, number and statutory/filing citation preservation with flags.",
        "pack_markers": frozenset({"slang", "verbatim", "statute", "ordinance", "cik", "gaap", "accession", "illegible", "retracted"}),
        "query_markers": frozenset({"verbatim", "dialect", "ordinance", "cik", "gaap", "accession", "illegible", "retracted", "citations"}),
    },
}


class _BM25Scorer:
    """Fast stdlib inverted-index Okapi BM25 scorer (k1=1.5, b=0.75)."""

    def __init__(self, docs_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.n_docs = max(1, len(docs_tokens))
        doc_counters = [Counter(toks) for toks in docs_tokens]
        doc_lens = [len(toks) for toks in docs_tokens]
        avg_dl = sum(doc_lens) / self.n_docs if doc_lens else 1.0
        df: Counter[str] = Counter()
        for c in doc_counters:
            for term in c:
                df[term] += 1
        idf = {
            term: math.log(1.0 + (self.n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }
        self.postings: dict[str, list[tuple[int, float]]] = {}
        for idx, counter in enumerate(doc_counters):
            norm = k1 * (1.0 - b + b * (doc_lens[idx] / max(1.0, avg_dl)))
            for term, tf in counter.items():
                w = idf[term] * (tf * (k1 + 1.0)) / (tf + norm)
                self.postings.setdefault(term, []).append((idx, w))

    def score_all(self, query_tokens: list[str]) -> list[float]:
        scores = [0.0] * self.n_docs
        seen: set[str] = set()
        for qt in query_tokens:
            if qt in seen:
                continue
            seen.add(qt)
            for idx, weight in self.postings.get(qt, ()):
                scores[idx] += weight
        return scores


def _cosine(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(val * vec_b.get(k, 0.0) for k, val in vec_a.items())
    if dot <= 0.0:
        return 0.0
    na = math.sqrt(sum(v * v for v in vec_a.values()))
    nb = math.sqrt(sum(v * v for v in vec_b.values()))
    return dot / (na * nb) if na and nb else 0.0


class RaRftAnalogyIndex:
    """Indexes enriched Seed Packs with RA-RFT structural isomorphism frames for 1-shot retrieval."""

    def __init__(self, enriched_packs: list[dict[str, Any]], rrf_k: int = 60) -> None:
        self.packs = enriched_packs
        self.rrf_k = rrf_k
        self.pack_ids = [p["pack_id"] for p in enriched_packs]

        # Baseline lexical index sees ONLY surface catalog text (pack_id, title, summary)
        baseline_tokens = [tokenize(p["surface_lexical_text"]) for p in enriched_packs]
        self.baseline_bm25 = _BM25Scorer(baseline_tokens)

        # SIRA enriched index sees discriminative terms + capability facets + PQEs
        sira_tokens = [tokenize(p["sira_enriched_text"]) for p in enriched_packs]
        self.sira_bm25 = _BM25Scorer(sira_tokens)

        # Compute RA-RFT structural isomorphism frame vector for each pack
        self.pack_frames: list[dict[str, float]] = []
        for p, toks in zip(enriched_packs, sira_tokens):
            tok_set = set(toks)
            io = p["io_signatures"]
            facets = set(p["capability_facets"])
            vec: dict[str, float] = {}
            for frame_id, spec in STRUCTURAL_FRAMES_12.items():
                overlap = len(tok_set & spec["pack_markers"])
                weight = min(1.0, overlap / 3.5)
                if frame_id == "independent-two-step-review" and "two_step_distinct_reviewer" in facets:
                    weight = min(1.0, weight + 0.50)
                elif frame_id == "cas-promotion" and "compare_and_set_mutation" in facets:
                    weight = min(1.0, weight + 0.55)
                elif frame_id == "zero-token-memoized-reuse" and "zero_model_deterministic" in facets:
                    weight = min(1.0, weight + 0.30)
                elif frame_id == "split-sensitive-vs-public" and "nonprofit_agent_kit" in facets:
                    weight = min(1.0, weight + 0.45)
                elif frame_id == "exclusive-lease-fencing" and "noun.recovery_playbook" in io["noun_categories"]:
                    weight = min(1.0, weight + 0.35)
                if weight >= 0.28:
                    vec[frame_id] = round(weight, 4)
            self.pack_frames.append(vec)

    def infer_query_frames(self, query: str, explicit_frames: list[str] | None = None) -> dict[str, float]:
        q_toks = set(tokenize(query))
        vec: dict[str, float] = {}
        for frame_id, spec in STRUCTURAL_FRAMES_12.items():
            hits = len(q_toks & spec["query_markers"])
            if hits > 0:
                vec[frame_id] = min(1.0, round(hits / 2.0, 4))
        for ef in explicit_frames or []:
            if ef in STRUCTURAL_FRAMES_12:
                vec[ef] = max(vec.get(ef, 0.0), 1.0)
        return vec

    def search_baseline_lexical(self, query: str, top_k: int = 5) -> dict[str, Any]:
        t0 = time.perf_counter()
        q_toks = tokenize(query)
        scores = self.baseline_bm25.score_all(q_toks)
        ranked = sorted(
            range(len(scores)),
            key=lambda i: (-scores[i], self.pack_ids[i]),
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "mode": "baseline_lexical",
            "ranked_packs": [self.pack_ids[i] for i in ranked[:top_k]],
            "top_score": round(scores[ranked[0]], 6) if ranked else 0.0,
            "latency_ms": round(elapsed_ms, 4),
        }

    def search_sira_only(self, query: str, top_k: int = 5) -> dict[str, Any]:
        t0 = time.perf_counter()
        q_toks = tokenize(query)
        scores = self.sira_bm25.score_all(q_toks)
        ranked = sorted(
            range(len(scores)),
            key=lambda i: (-scores[i], self.pack_ids[i]),
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "mode": "sira_enriched_single_shot",
            "ranked_packs": [self.pack_ids[i] for i in ranked[:top_k]],
            "top_score": round(scores[ranked[0]], 6) if ranked else 0.0,
            "latency_ms": round(elapsed_ms, 4),
        }

    def search_sira_rartf(
        self,
        query: str,
        explicit_frames: list[str] | None = None,
        shim_boost_packs: dict[str, float] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Single-shot SIRA + RA-RFT structural isomorphism + MR-Search shim hybrid search."""
        t0 = time.perf_counter()
        q_toks = tokenize(query)
        sira_scores = self.sira_bm25.score_all(q_toks)
        max_sira = max(sira_scores, default=0.0)
        q_frames = self.infer_query_frames(query, explicit_frames=explicit_frames)
        analogy_scores = [_cosine(q_frames, pf) for pf in self.pack_frames]

        sira_order = sorted(range(len(self.packs)), key=lambda i: (-sira_scores[i], self.pack_ids[i]))
        sira_rank = {idx: rank + 1 for rank, idx in enumerate(sira_order)}

        fused: list[tuple[float, int]] = []
        for idx, pack_id in enumerate(self.pack_ids):
            sira_norm = (sira_scores[idx] / max_sira) if max_sira > 0.0 else 0.0
            rrf_tie = (self.rrf_k + 1.0) / (self.rrf_k + sira_rank[idx])
            score = 0.72 * sira_norm + 0.22 * analogy_scores[idx] + 0.06 * rrf_tie
            if shim_boost_packs and pack_id in shim_boost_packs:
                score += shim_boost_packs[pack_id]
            fused.append((score, idx))

        fused.sort(key=lambda item: (-item[0], self.pack_ids[item[1]]))
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "mode": "sira_rartf_mrsearch_single_shot",
            "query_frames": q_frames,
            "ranked_packs": [self.pack_ids[idx] for _, idx in fused[:top_k]],
            "top_hybrid_score": round(fused[0][0], 6) if fused else 0.0,
            "latency_ms": round(elapsed_ms, 4),
        }
