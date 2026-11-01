"""Iterative RPO preference pair curator with NLL collapse guard, length-ratio filter and 3-key dedup."""

from __future__ import annotations

import copy
import hashlib
import math
import re
from typing import Any

from .grid import NodeGrid, load_default_grid_spec


def _normalize_text(text: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return " ".join(tokens)


def _structural_skeleton(text: str) -> str:
    lowered = text.lower()
    masked_digits = re.sub(r"\d+", "#", lowered)
    tokens = re.findall(r"[a-z#]+", masked_digits)
    return " ".join(tokens)


class IterativeRpoPairCurator:
    """Curates (prompt, chosen_verified, rejected_tombstone) pairs with Iterative RPO objective scoring."""

    def __init__(
        self,
        *,
        dpo_beta: float | None = None,
        rpo_nll_alpha: float | None = None,
        max_length_ratio: float | None = None,
        min_chosen_logp_drift_per_token: float | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        grid = NodeGrid(cfg)
        num = cfg["numerics"]
        rc = cfg["rpo_curator"]

        self._eps = float(num["epsilon"])
        self._round_digits = int(num["round_digits"])
        self._softplus_clip = float(num["softplus_Clip"])
        self._dedup_hash_chars = int(rc["dedup_hash_chars"])
        self._structural_key_count = int(rc["structural_dedup_key_count"])

        clamped = grid.clamp_cell({
            "dpo_beta": dpo_beta if dpo_beta is not None else rc["default_dpo_beta"],
            "rpo_nll_alpha": rpo_nll_alpha if rpo_nll_alpha is not None else rc["default_rpo_alpha"],
            "max_length_ratio": (
                max_length_ratio if max_length_ratio is not None else rc["default_max_length_ratio"]
            ),
        })
        self.dpo_beta = float(clamped["dpo_beta"])
        self.rpo_nll_alpha = float(clamped["rpo_nll_alpha"])
        self.max_length_ratio = float(clamped["max_length_ratio"])
        self.min_chosen_logp_drift_per_token = float(
            min_chosen_logp_drift_per_token
            if min_chosen_logp_drift_per_token is not None
            else rc["min_chosen_logp_drift_per_token"]
        )

    def _softplus(self, x: float) -> float:
        if x > self._softplus_clip:
            return x
        if x < -self._softplus_clip:
            return math.exp(x)
        if x > 0.0:
            return x + math.log(1.0 + math.exp(-x))
        return math.log(1.0 + math.exp(x))

    @staticmethod
    def _token_count(text: str, explicit_count: int | None = None) -> int:
        if explicit_count is not None and int(explicit_count) > 0:
            return int(explicit_count)
        return max(1, len(text.split()))

    def three_key_fingerprints(
        self,
        prompt: str,
        chosen_verified: str,
        rejected_tombstone: str,
    ) -> tuple[str, str, str]:
        """Compute 3 structural deduplication keys: prompt, chosen skeleton and joint pair transition."""
        p_norm = _normalize_text(prompt)
        c_skel = _structural_skeleton(chosen_verified)
        r_norm = _normalize_text(rejected_tombstone)

        k_prompt = hashlib.sha256(f"prompt:{p_norm}".encode("utf-8")).hexdigest()[: self._dedup_hash_chars]
        k_chosen = hashlib.sha256(f"chosen:{c_skel}".encode("utf-8")).hexdigest()[: self._dedup_hash_chars]
        k_pair = hashlib.sha256(
            f"pair:{p_norm}||{c_skel}||{r_norm}".encode("utf-8")
        ).hexdigest()[: self._dedup_hash_chars]
        return k_prompt, k_chosen, k_pair

    def score_pair(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Compute DPO logistic margin, per-token NLL_chosen regularizer and Iterative RPO objective."""
        prompt = str(candidate["prompt"])
        chosen = str(candidate["chosen_verified"])
        rejected = str(candidate["rejected_tombstone"])

        c_tokens = self._token_count(chosen, candidate.get("chosen_token_count"))
        r_tokens = self._token_count(rejected, candidate.get("rejected_token_count"))

        pi_logp_c = float(candidate["policy_logp_chosen"])
        ref_logp_c = float(candidate["ref_logp_chosen"])
        pi_logp_r = float(candidate["policy_logp_rejected"])
        ref_logp_r = float(candidate["ref_logp_rejected"])

        chosen_implicit_reward = self.dpo_beta * (pi_logp_c - ref_logp_c)
        rejected_implicit_reward = self.dpo_beta * (pi_logp_r - ref_logp_r)
        dpo_margin = chosen_implicit_reward - rejected_implicit_reward
        dpo_loss = self._softplus(-dpo_margin)

        nll_chosen = max(0.0, -pi_logp_c) / float(c_tokens)
        rpo_loss = dpo_loss + self.rpo_nll_alpha * nll_chosen
        rpo_score = dpo_margin - self.rpo_nll_alpha * nll_chosen

        chosen_drift_per_token = (pi_logp_c - ref_logp_c) / float(c_tokens)
        logp_collapsed = chosen_drift_per_token < self.min_chosen_logp_drift_per_token

        longer = max(c_tokens, r_tokens)
        shorter = max(1, min(c_tokens, r_tokens))
        length_ratio = float(longer) / float(shorter)

        k_prompt, k_chosen, k_pair = self.three_key_fingerprints(prompt, chosen, rejected)

        return {
            "pair_id": str(candidate["pair_id"]),
            "dpo_margin": round(dpo_margin, self._round_digits),
            "dpo_loss": round(dpo_loss, self._round_digits),
            "nll_chosen_per_token": round(nll_chosen, self._round_digits),
            "rpo_loss": round(rpo_loss, self._round_digits),
            "rpo_score": round(rpo_score, self._round_digits),
            "chosen_logp_drift_per_token": round(chosen_drift_per_token, self._round_digits),
            "chosen_logp_collapsed": logp_collapsed,
            "length_ratio": round(length_ratio, self._round_digits),
            "dedup_keys": [k_prompt, k_chosen, k_pair],
        }

    def curate_pairs(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        """Filter and rank candidate pairs by provenance, length ratio, chosen collapse and 3-key dedup."""
        seen_keys: list[set[str]] = [set() for _ in range(self._structural_key_count)]
        curated: list[dict[str, Any]] = []
        rejected_records: list[dict[str, Any]] = []
        reason_counts: dict[str, int] = {
            "unverified_provenance": 0,
            "length_ratio_bias": 0,
            "chosen_logp_collapse": 0,
            "non_positive_dpo_margin": 0,
            "structural_duplicate": 0,
        }

        for cand in candidates:
            scored = self.score_pair(cand)
            verified_ok = bool(cand.get("chosen_verified_pass", True)) and bool(
                cand.get("rejected_tombstone_fail", True)
            )
            if not verified_ok:
                reason_counts["unverified_provenance"] += 1
                rejected_records.append({**scored, "rejected_reason": "unverified_provenance"})
                continue

            if scored["length_ratio"] > self.max_length_ratio:
                reason_counts["length_ratio_bias"] += 1
                rejected_records.append({**scored, "rejected_reason": "length_ratio_bias"})
                continue

            if scored["chosen_logp_collapsed"]:
                reason_counts["chosen_logp_collapse"] += 1
                rejected_records.append({**scored, "rejected_reason": "chosen_logp_collapse"})
                continue

            if scored["dpo_margin"] <= 0.0:
                reason_counts["non_positive_dpo_margin"] += 1
                rejected_records.append({**scored, "rejected_reason": "non_positive_dpo_margin"})
                continue

            keys = scored["dedup_keys"]
            is_dup = any(keys[idx] in seen_keys[idx] for idx in range(self._structural_key_count))
            if is_dup:
                reason_counts["structural_duplicate"] += 1
                rejected_records.append({**scored, "rejected_reason": "structural_duplicate"})
                continue

            for idx in range(self._structural_key_count):
                seen_keys[idx].add(keys[idx])
            curated.append(scored)

        curated.sort(key=lambda item: (item["rpo_loss"], -item["rpo_score"], item["pair_id"]))
        mean_margin = (
            sum(item["dpo_margin"] for item in curated) / float(len(curated)) if curated else 0.0
        )
        mean_rpo_loss = (
            sum(item["rpo_loss"] for item in curated) / float(len(curated)) if curated else 0.0
        )

        return {
            "admitted_pairs": curated,
            "admitted_ids": [item["pair_id"] for item in curated],
            "admitted_count": len(curated),
            "rejected_count": len(rejected_records),
            "rejection_reasons": reason_counts,
            "mean_dpo_margin": round(mean_margin, self._round_digits),
            "mean_rpo_loss": round(mean_rpo_loss, self._round_digits),
        }
