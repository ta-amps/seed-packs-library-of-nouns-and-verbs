"""Conversation history provision deduplication and redundancy-penalized submodular 0/1 knapsack."""

from __future__ import annotations

import math
import re
from typing import Any

from .engine import ThreeTierTriggerEngine
from .grid import resolve_grid_cell

PROVISION_MARKER_RE = re.compile(r"\[PROVISION:\s*([A-Za-z0-9_.:-]+)@v(\d+)\]")
ERROR_MARKER_RE = re.compile(r"\[ERROR_SIG:\s*([A-Za-z0-9_.:-]+)\]")


class ConversationDedupAndSubmodularKnapsack:
    """Deduplicates provisions across conversation turns and packs survivors via scaled integer DP."""

    def __init__(
        self,
        grid_overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.cell, self.constants = resolve_grid_cell(grid_overrides, regime=regime, spec=spec)
        self._vectorizer = ThreeTierTriggerEngine(grid_overrides, regime=regime, spec=spec)

    @staticmethod
    def format_provision_marker(provision_id: str, version: int) -> str:
        return f"[PROVISION: {provision_id}@v{version}]"

    @staticmethod
    def extract_history_markers(conversation_history: list[str]) -> tuple[set[str], dict[str, int], dict[str, int]]:
        """Return (all_seen_keys, last_provision_turn_by_key, last_error_turn_by_sig)."""
        seen_keys: set[str] = set()
        last_prov_turn: dict[str, int] = {}
        last_err_turn: dict[str, int] = {}
        for turn_idx, message in enumerate(conversation_history):
            for match in PROVISION_MARKER_RE.finditer(message):
                prov_id, ver_str = match.groups()
                key = f"{prov_id}@v{int(ver_str)}"
                seen_keys.add(key)
                last_prov_turn[key] = turn_idx
            for err_match in ERROR_MARKER_RE.finditer(message):
                sig = err_match.group(1)
                last_err_turn[sig] = turn_idx
        return seen_keys, last_prov_turn, last_err_turn

    def filter_eligible_provisions(
        self,
        provisions: list[dict[str, Any]],
        conversation_history: list[str],
        *,
        current_error_signature: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        """Deduplicate candidate provisions according to cadence mode and history markers."""
        seen_keys, last_prov_turn, last_err_turn = self.extract_history_markers(conversation_history)
        survivors: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []

        for prov in provisions:
            pid = str(prov["provision_id"])
            ver = int(prov.get("version", 1))
            versioned_key = f"{pid}@v{ver}"
            mode = str(prov.get("dedup_mode", "once_per_conversation"))

            if mode == "once_per_conversation":
                if versioned_key in seen_keys:
                    skipped.append({"provision_id": pid, "reason": "already_injected_in_conversation"})
                    continue
                survivors.append(prov)
            elif mode == "every_turn":
                survivors.append(prov)
            elif mode == "on_error_signature":
                req_sig = str(prov.get("error_signature", "")).strip()
                active_sig = (current_error_signature or "").strip()
                if not active_sig or (req_sig and active_sig != req_sig):
                    skipped.append({"provision_id": pid, "reason": "error_signature_not_active"})
                    continue
                if versioned_key in last_prov_turn:
                    prev_prov_idx = last_prov_turn[versioned_key]
                    prev_err_idx = last_err_turn.get(active_sig, -1)
                    if prev_err_idx >= 0 and prev_prov_idx >= prev_err_idx:
                        skipped.append({"provision_id": pid, "reason": "error_signature_already_shimmed"})
                        continue
                survivors.append(prov)
            else:
                raise ValueError(f"unsupported dedup_mode: {mode}")

        return survivors, skipped

    def _estimate_tokens_and_chars(self, prov: dict[str, Any]) -> tuple[int, int, str]:
        pid = str(prov["provision_id"])
        ver = int(prov.get("version", 1))
        marker = self.format_provision_marker(pid, ver)
        body = str(prov.get("text", "")).strip()
        rendered = f"{marker}\n{body}" if body else marker
        char_len = len(rendered)
        chars_per_tok = int(self.constants["chars_per_token"])
        explicit_tokens = prov.get("tokens")
        if explicit_tokens is not None:
            tok_cost = max(1, int(explicit_tokens))
        else:
            tok_cost = max(1, math.ceil(float(char_len) / float(chars_per_tok)))
        return tok_cost, char_len, rendered

    def pack_provisions(
        self,
        provisions: list[dict[str, Any]],
        conversation_history: list[str],
        *,
        current_error_signature: str | None = None,
        token_budget_override: int | None = None,
        max_total_chars_override: int | None = None,
    ) -> dict[str, Any]:
        """Deduplicate and pack provisions via redundancy-penalized scaled integer 0/1 DP."""
        round_d = int(self.constants["round_digits"])
        budget_tokens = int(token_budget_override if token_budget_override is not None else self.cell["token_budget"])
        max_chars = int(max_total_chars_override if max_total_chars_override is not None else self.cell["max_total_chars"])
        alpha = float(self.cell["redundancy_alpha"])
        dp_scale = int(self.cell["knapsack_dp_scale"])

        survivors, skipped = self.filter_eligible_provisions(
            provisions,
            conversation_history,
            current_error_signature=current_error_signature,
        )

        # Rank survivors deterministically by raw utility desc so higher-utility items anchor redundancy discounting
        ordered = sorted(
            survivors,
            key=lambda item: (-float(item.get("utility", 0.0)), str(item["provision_id"])),
        )
        vecs = [self._vectorizer.build_sparse_vector(str(p.get("text", ""))) for p in ordered]

        candidates: list[dict[str, Any]] = []
        for idx, prov in enumerate(ordered):
            raw_u = max(0.0, float(prov.get("utility", 0.0)))
            max_sim = 0.0
            for prior_idx in range(idx):
                sim = self._vectorizer.sparse_cosine(vecs[idx], vecs[prior_idx])
                if sim > max_sim:
                    max_sim = sim
            penalized_u = max(0.0, raw_u * (1.0 - alpha * max_sim))
            tok_cost, char_len, rendered = self._estimate_tokens_and_chars(prov)
            if tok_cost > budget_tokens or char_len > max_chars:
                skipped.append({"provision_id": str(prov["provision_id"]), "reason": "exceeds_budget_single"})
                continue
            scaled_u = int(round(penalized_u * float(dp_scale)))
            candidates.append(
                {
                    "provision_id": str(prov["provision_id"]),
                    "version": int(prov.get("version", 1)),
                    "raw_utility": round(raw_u, round_d),
                    "max_similarity_to_higher": round(max_sim, round_d),
                    "penalized_utility": round(penalized_u, round_d),
                    "scaled_utility": scaled_u,
                    "tokens": tok_cost,
                    "chars": char_len,
                    "rendered": rendered,
                }
            )

        # Exact 0/1 DP tracking Pareto-undominated (char_used -> (scaled_u, chosen_indices)) per token weight
        # dp[w] maps char_sum -> (scaled_utility, tuple_of_candidate_indices)
        dp: list[dict[int, tuple[int, tuple[int, ...]]]] = [{} for _ in range(budget_tokens + 1)]
        dp[0][0] = (0, ())

        for c_idx, cand in enumerate(candidates):
            w_tok = int(cand["tokens"])
            w_chr = int(cand["chars"])
            val_u = int(cand["scaled_utility"])
            for cur_tok in range(budget_tokens - w_tok, -1, -1):
                if not dp[cur_tok]:
                    continue
                nxt_tok = cur_tok + w_tok
                snapshot = list(dp[cur_tok].items())
                for cur_chr, state_pair in snapshot:
                    cur_u, chosen_idxs = state_pair
                    nxt_chr = cur_chr + w_chr
                    if nxt_chr > max_chars:
                        continue
                    nxt_u = cur_u + val_u
                    nxt_idxs = chosen_idxs + (c_idx,)
                    existing = dp[nxt_tok].get(nxt_chr)
                    if existing is None or nxt_u > existing[0]:
                        dp[nxt_tok][nxt_chr] = (nxt_u, nxt_idxs)

                # Prune dominated char states inside dp[nxt_tok]
                if len(dp[nxt_tok]) > 1:
                    best_u_so_far = -1
                    pruned: dict[int, tuple[int, tuple[int, ...]]] = {}
                    for c_sum in sorted(dp[nxt_tok]):
                        u_score, idxs_tuple = dp[nxt_tok][c_sum]
                        if u_score > best_u_so_far:
                            pruned[c_sum] = (u_score, idxs_tuple)
                            best_u_so_far = u_score
                    dp[nxt_tok] = pruned

        best_scaled = -1
        best_tokens = 0
        best_chars = 0
        best_indices: tuple[int, ...] = ()
        for tok_used, chr_map in enumerate(dp):
            for chr_used, state_pair in chr_map.items():
                u_val, idxs = state_pair
                if u_val > best_scaled or (u_val == best_scaled and tok_used < best_tokens):
                    best_scaled = u_val
                    best_tokens = tok_used
                    best_chars = chr_used
                    best_indices = idxs

        selected = [candidates[i] for i in best_indices]
        selected_ids = [item["provision_id"] for item in selected]
        for idx, cand in enumerate(candidates):
            if idx not in best_indices:
                skipped.append({"provision_id": cand["provision_id"], "reason": "knapsack_suboptimal"})

        total_penalized_u = sum(float(item["penalized_utility"]) for item in selected)
        return {
            "selected_provision_ids": selected_ids,
            "selected_provisions": selected,
            "injected_context": "\n\n".join(item["rendered"] for item in selected),
            "total_tokens": best_tokens,
            "total_chars": best_chars,
            "token_budget": budget_tokens,
            "max_total_chars": max_chars,
            "total_penalized_utility": round(total_penalized_u, round_d),
            "skipped": skipped,
        }
