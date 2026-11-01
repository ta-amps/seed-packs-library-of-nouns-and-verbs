"""Deterministic reference evaluators for the 6 swappable learners (advice_only=True, keep_baseline_valid=True)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .grid import resolve_grid_cell

WORD_RE = re.compile(r"[a-z0-9_]+")


class SwappableLearnerAdvisors:
    """Reference evaluators for 6 swappable learners; disabling any advisor leaves baseline execution valid."""

    def __init__(
        self,
        grid_overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.cell, self.constants = resolve_grid_cell(grid_overrides, regime=regime, spec=spec)

    def _stamp_advice(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "advice_only": True,
            "keep_baseline_valid": True,
            **payload,
        }

    def phrasing_acceptance_uplift(self, stats: dict[str, Any]) -> dict[str, Any]:
        """Learner 1: empirical-Bayes phrasing acceptance uplift vs baseline brief wording."""
        round_d = int(self.constants["round_digits"])
        prior_s = float(self.cell["bayes_prior_strength"])
        prior_m = float(self.cell["bayes_prior_mean"])
        min_samples = int(self.cell["learner_min_samples"])
        min_uplift = float(self.cell["learner_min_uplift"])

        b_trials = max(0, int(stats.get("baseline_trials", 0)))
        b_accepts = max(0, int(stats.get("baseline_accepts", 0)))
        c_trials = max(0, int(stats.get("candidate_trials", 0)))
        c_accepts = max(0, int(stats.get("candidate_accepts", 0)))

        b_shrunk = (prior_s * prior_m + float(b_accepts)) / (prior_s + float(b_trials))
        c_shrunk = (prior_s * prior_m + float(c_accepts)) / (prior_s + float(c_trials))
        uplift = c_shrunk - b_shrunk
        adopt = b_trials >= min_samples and c_trials >= min_samples and uplift >= min_uplift
        return self._stamp_advice(
            {
                "learner_id": "phrasing_acceptance_uplift",
                "shrunk_uplift": round(uplift, round_d),
                "recommendation": "adopt_candidate_phrasing" if adopt else "keep_baseline_phrasing",
            }
        )

    def searchability_scent_ranker(
        self,
        candidates: list[dict[str, Any]],
        target_queries: list[str],
    ) -> dict[str, Any]:
        """Learner 2: retrieval scent scorer ranking noun titles/summaries by query coverage and brevity."""
        round_d = int(self.constants["round_digits"])
        target_words = max(1, int(self.cell["scent_brevity_target_words"]))
        query_term_sets = [set(WORD_RE.findall(q.lower())) for q in target_queries if q.strip()]

        doc_freq: dict[str, int] = {}
        cand_tokens: list[tuple[str, list[str], set[str]]] = []
        for cand in candidates:
            cid = str(cand["candidate_id"])
            words = WORD_RE.findall(str(cand.get("text", "")).lower())
            uniq = set(words)
            for tok in uniq:
                doc_freq[tok] = doc_freq.get(tok, 0) + 1
            cand_tokens.append((cid, words, uniq))

        total_docs = max(1, len(candidates))
        ranked: list[dict[str, Any]] = []
        for cid, words, uniq in cand_tokens:
            if not query_term_sets:
                coverage = 0.0
            else:
                cov_sum = 0.0
                for q_set in query_term_sets:
                    if not q_set:
                        continue
                    hits = sum(
                        1.0 / float(doc_freq.get(tok, total_docs))
                        for tok in (q_set & uniq)
                    )
                    cov_sum += hits / float(len(q_set))
                coverage = cov_sum / float(len(query_term_sets))
            excess_words = max(0, len(words) - target_words)
            brevity = float(target_words) / float(target_words + excess_words)
            score = coverage * brevity
            ranked.append(
                {
                    "candidate_id": cid,
                    "scent_score": round(score, round_d),
                }
            )

        ranked.sort(key=lambda item: (-float(item["scent_score"]), str(item["candidate_id"])))
        return self._stamp_advice(
            {
                "learner_id": "searchability_scent_ranker",
                "top_candidate_id": ranked[0]["candidate_id"] if ranked else None,
                "ranked": ranked,
            }
        )

    def shim_injection_matched_uplift(self, matched_strata: list[dict[str, Any]]) -> dict[str, Any]:
        """Learner 3: difficulty-stratified matched uplift discounting extra shim token tax."""
        round_d = int(self.constants["round_digits"])
        tax_weight = float(self.cell["learner_token_tax_weight"])
        min_uplift = float(self.cell["learner_min_uplift"])
        tokens_unit = float(self.constants["tokens_per_cost_unit"])

        total_weight = sum(max(1, int(s.get("pairs", 1))) for s in matched_strata)
        if not matched_strata or total_weight <= 0:
            return self._stamp_advice(
                {
                    "learner_id": "shim_injection_matched_uplift",
                    "net_uplift": 0.0,
                    "recommendation": "keep_baseline_no_shim",
                }
            )

        weighted_gain = 0.0
        weighted_extra_tokens = 0.0
        for stratum in matched_strata:
            n_pairs = float(max(1, int(stratum.get("pairs", 1))))
            gain = float(stratum.get("shimmed_pass_rate", 0.0)) - float(stratum.get("unshimmed_pass_rate", 0.0))
            extra_tok = max(0.0, float(stratum.get("extra_shim_tokens", 0.0)))
            weighted_gain += n_pairs * gain
            weighted_extra_tokens += n_pairs * extra_tok

        mean_gain = weighted_gain / float(total_weight)
        mean_extra_units = (weighted_extra_tokens / float(total_weight)) / tokens_unit
        net_uplift = mean_gain - tax_weight * mean_extra_units
        return self._stamp_advice(
            {
                "learner_id": "shim_injection_matched_uplift",
                "net_uplift": round(net_uplift, round_d),
                "recommendation": "retain_shim" if net_uplift >= min_uplift else "prune_shim",
            }
        )

    def decomposition_split_breakeven(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Learner 4: evaluate whether splitting into k subtasks beats single-step execution."""
        round_d = int(self.constants["round_digits"])
        per_slice_tax = float(self.cell["decomposition_per_slice_tax"])
        min_uplift = float(self.cell["learner_min_uplift"])

        single_prob = max(0.0, min(1.0, float(spec.get("single_pass_prob", 0.0))))
        subtask_prob = max(0.0, min(1.0, float(spec.get("subtask_pass_prob", 0.0))))
        subtask_count = max(1, int(spec.get("subtask_count", 1)))

        chain_prob = subtask_prob ** subtask_count
        net_split_value = chain_prob - float(subtask_count - 1) * per_slice_tax
        delta = net_split_value - single_prob
        return self._stamp_advice(
            {
                "learner_id": "decomposition_split_breakeven",
                "net_split_delta": round(delta, round_d),
                "recommendation": "split_into_dag" if delta >= min_uplift else "keep_single_verb",
            }
        )

    def pairwise_taste_bradley_terry(self, comparisons: list[dict[str, Any]]) -> dict[str, Any]:
        """Learner 5: smoothed iterative Bradley-Terry ranker over pairwise winner/loser judgments."""
        round_d = int(self.constants["round_digits"])
        iters = int(self.constants["bradley_terry_iterations"])
        pseudo = float(self.constants["bradley_terry_pseudo_wins"])

        items_set: set[str] = set()
        for comp in comparisons:
            items_set.add(str(comp["winner"]))
            items_set.add(str(comp["loser"]))
        items = sorted(items_set)
        if not items:
            return self._stamp_advice(
                {
                    "learner_id": "pairwise_taste_bradley_terry",
                    "top_item": None,
                    "scores": {},
                }
            )

        strengths = {item: 1.0 / float(len(items)) for item in items}
        wins_by_item = {item: pseudo for item in items}
        matchups: dict[tuple[str, str], float] = {}
        for comp in comparisons:
            w_id = str(comp["winner"])
            l_id = str(comp["loser"])
            if w_id == l_id:
                continue
            wins_by_item[w_id] += 1.0
            pair_key = (w_id, l_id) if w_id < l_id else (l_id, w_id)
            matchups[pair_key] = matchups.get(pair_key, 0.0) + 1.0

        # Add weak complete-graph prior pseudo-comparisons so disconnected pairs stay well-conditioned
        for idx_a, item_a in enumerate(items):
            for item_b in items[idx_a + 1 :]:
                pair_key = (item_a, item_b)
                matchups[pair_key] = matchups.get(pair_key, 0.0) + (pseudo + pseudo)

        for _ in range(iters):
            updated: dict[str, float] = {}
            for item_i in items:
                denom = 0.0
                for item_j in items:
                    if item_i == item_j:
                        continue
                    pair_key = (item_i, item_j) if item_i < item_j else (item_j, item_i)
                    n_ij = matchups.get(pair_key, 0.0)
                    s_sum = strengths[item_i] + strengths[item_j]
                    if s_sum > 0.0:
                        denom += n_ij / s_sum
                updated[item_i] = wins_by_item[item_i] / denom if denom > 0.0 else strengths[item_i]
            total_s = sum(updated.values())
            if total_s > 0.0:
                strengths = {k: val / total_s for k, val in updated.items()}

        ordered = sorted(items, key=lambda name: (-strengths[name], name))
        return self._stamp_advice(
            {
                "learner_id": "pairwise_taste_bradley_terry",
                "top_item": ordered[0],
                "ranking": ordered,
                "scores": {k: round(strengths[k], round_d) for k in ordered},
            }
        )

    def rights_cleared_training_manifest(self, traces: list[dict[str, Any]]) -> dict[str, Any]:
        """Learner 6: block contributor-restricted/non-public/secret traces and split by task_family_id."""
        allowed_licenses = set(str(lic) for lic in self.constants["allowed_training_licenses"])
        slice_chars = int(self.constants["digest_slice_chars"])
        radix = int(self.constants["hex_radix"])
        modulus = int(self.constants["split_modulus"])
        holdout_cut = int(self.constants["holdout_buckets"])

        train_ids: list[str] = []
        holdout_ids: list[str] = []
        train_families: set[str] = set()
        holdout_families: set[str] = set()
        blocked: list[dict[str, str]] = []

        for trace in traces:
            tid = str(trace["trace_id"])
            family_id = str(trace.get("task_family_id", tid))
            if bool(trace.get("contributor_restricted", False)):
                blocked.append({"trace_id": tid, "reason": "contributor_restricted"})
                continue
            if bool(trace.get("contains_secrets", False)):
                blocked.append({"trace_id": tid, "reason": "contains_secrets"})
                continue
            if str(trace.get("privacy_tier", "internal")) != "public":
                blocked.append({"trace_id": tid, "reason": "non_public_privacy_tier"})
                continue
            if str(trace.get("license", "")) not in allowed_licenses:
                blocked.append({"trace_id": tid, "reason": "unapproved_license"})
                continue

            bucket = int(hashlib.sha256(family_id.encode("utf-8")).hexdigest()[:slice_chars], radix) % modulus
            if bucket < holdout_cut:
                holdout_ids.append(tid)
                holdout_families.add(family_id)
            else:
                train_ids.append(tid)
                train_families.add(family_id)

        family_overlap = sorted(train_families & holdout_families)
        return self._stamp_advice(
            {
                "learner_id": "rights_cleared_training_manifest",
                "train_trace_ids": sorted(train_ids),
                "holdout_trace_ids": sorted(holdout_ids),
                "blocked_trace_ids": [b["trace_id"] for b in blocked],
                "blocked_details": blocked,
                "family_overlap_count": len(family_overlap),
            }
        )
