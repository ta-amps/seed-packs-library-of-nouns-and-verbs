"""Three-tier deterministic trigger compiler and evaluator with Role-Filler Frame isomorphism."""

from __future__ import annotations

import fnmatch
import hashlib
import math
import re
from typing import Any

from .grid import resolve_grid_cell

WORD_RE = re.compile(r"[a-z0-9_]+")


class ThreeTierTriggerEngine:
    """Evaluates trigger rules across Tier-1 bitmask/veto, Tier-2 frame-augmented TF cosine, and Tier-3 governance."""

    def __init__(
        self,
        grid_overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.cell, self.constants = resolve_grid_cell(grid_overrides, regime=regime, spec=spec)

    def _stem(self, token: str) -> str:
        min_len = int(self.constants["min_stem_length"])
        if len(token) < min_len:
            return token
        for suffix in self.constants["stem_suffixes"]:
            sfx = str(suffix)
            if token.endswith(sfx) and len(token) - len(sfx) >= int(self.constants["min_token_length"]):
                return token[: len(token) - len(sfx)]
        return token

    def _canonical_concept(self, token: str) -> str:
        syn_map = self.constants["concept_synonyms"]
        stemmed = self._stem(token)
        if token in syn_map:
            return str(syn_map[token])
        if stemmed in syn_map:
            return str(syn_map[stemmed])
        return stemmed

    def compute_trigram_bitmask(self, text: str) -> int:
        """Compute deterministic character n-gram bitmask of grid-configured width."""
        cleaned = re.sub(r"\s+", " ", text.lower()).strip()
        n_size = int(self.cell["char_ngram_size"])
        width = int(self.cell["trigram_bitmask_width"])
        slice_chars = int(self.constants["digest_slice_chars"])
        radix = int(self.constants["hex_radix"])
        if len(cleaned) < n_size:
            if not cleaned:
                return 0
            digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:slice_chars]
            return 1 << (int(digest, radix) % width)
        mask = 0
        limit = len(cleaned) - n_size + 1
        for idx in range(limit):
            gram = cleaned[idx : idx + n_size]
            digest = hashlib.sha256(gram.encode("utf-8")).hexdigest()[:slice_chars]
            bit_pos = int(digest, radix) % width
            mask |= 1 << bit_pos
        return mask

    def build_sparse_vector(self, text: str) -> dict[str, float]:
        """Build L2-normalized log(1+tf) sparse vector over stems, concept synonyms, and char n-grams."""
        lowered = text.lower()
        tokens = WORD_RE.findall(lowered)
        counts: dict[str, int] = {}
        for tok in tokens:
            if len(tok) < int(self.constants["min_token_length"]):
                continue
            stem_feat = f"stem:{self._stem(tok)}"
            counts[stem_feat] = counts.get(stem_feat, 0) + 1
            concept_feat = f"concept:{self._canonical_concept(tok)}"
            counts[concept_feat] = counts.get(concept_feat, 0) + 1
        compact = re.sub(r"\s+", " ", lowered).strip()
        n_size = int(self.cell["char_ngram_size"])
        if len(compact) >= n_size:
            for idx in range(len(compact) - n_size + 1):
                c_feat = f"cng:{compact[idx : idx + n_size]}"
                counts[c_feat] = counts.get(c_feat, 0) + 1
        if not counts:
            return {}
        weights = {feat: math.log(1.0 + float(tf)) for feat, tf in counts.items()}
        norm_sq = sum(val * val for val in weights.values())
        if norm_sq <= 0.0:
            return {}
        inv_norm = 1.0 / math.sqrt(norm_sq)
        return {feat: val * inv_norm for feat, val in weights.items()}

    @staticmethod
    def sparse_cosine(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        if not vec_a or not vec_b:
            return 0.0
        if len(vec_a) > len(vec_b):
            vec_a, vec_b = vec_b, vec_a
        return sum(val * vec_b.get(feat, 0.0) for feat, val in vec_a.items())

    def _normalize_slot_value(self, raw_slot: str) -> set[str]:
        tokens = WORD_RE.findall(raw_slot.lower())
        return {self._canonical_concept(tok) for tok in tokens if tok}

    def compute_frame_isomorphism(
        self,
        query_frame: dict[str, Any] | None,
        rule_frame: dict[str, Any] | None,
    ) -> tuple[float, int, int]:
        """Compute structural Role-Filler Frame bonus across (verb_frame, object_slot, error_code_slot)."""
        if not query_frame or not rule_frame:
            return 0.0, 0, 0
        defined_slots = 0
        matched_slots = 0
        conflicted = False
        for slot_name in self.constants["role_frame_slots"]:
            r_raw = str(rule_frame.get(slot_name, "")).strip()
            if not r_raw:
                continue
            defined_slots += 1
            q_raw = str(query_frame.get(slot_name, "")).strip()
            if not q_raw:
                continue
            r_norm = self._normalize_slot_value(r_raw)
            q_norm = self._normalize_slot_value(q_raw)
            if r_norm and q_norm and (r_norm & q_norm):
                matched_slots += 1
            else:
                conflicted = True
        if defined_slots == 0 or conflicted:
            return 0.0, matched_slots, defined_slots
        ratio = float(matched_slots) / float(defined_slots)
        bonus = ratio * float(self.cell["frame_isomorphism_bonus"])
        return bonus, matched_slots, defined_slots

    def evaluate_rule(self, query: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a single trigger rule across Tiers 1, 2, and 3."""
        round_d = int(self.constants["round_digits"])
        query_text = str(query.get("text", ""))
        lowered_query = query_text.lower()
        query_tokens = set(WORD_RE.findall(lowered_query))
        tool_name = str(query.get("tool_name", ""))

        # Tier 1: Hard exclude_keywords anti-trigger veto
        for excl in rule.get("exclude_keywords", []):
            excl_low = str(excl).lower()
            if excl_low in query_tokens or excl_low in lowered_query:
                return {
                    "rule_id": str(rule["rule_id"]),
                    "matched": False,
                    "rejected_tier": "tier1_exclude_veto",
                    "intent_action": "abstain",
                    "score": 0.0,
                    "estimated_tokens": 0,
                }

        # Tier 1: Tool glob filter
        tool_globs = [str(g) for g in rule.get("tool_globs", [])]
        if tool_globs and not any(fnmatch.fnmatchcase(tool_name, pat) for pat in tool_globs):
            return {
                "rule_id": str(rule["rule_id"]),
                "matched": False,
                "rejected_tier": "tier1_tool_glob",
                "intent_action": "abstain",
                "score": 0.0,
                "estimated_tokens": 0,
            }

        # Tier 1: all_keywords & any_keywords
        all_kw = [str(k).lower() for k in rule.get("all_keywords", [])]
        if any(kw not in lowered_query for kw in all_kw):
            return {
                "rule_id": str(rule["rule_id"]),
                "matched": False,
                "rejected_tier": "tier1_all_keywords",
                "intent_action": "abstain",
                "score": 0.0,
                "estimated_tokens": 0,
            }
        any_kw = [str(k).lower() for k in rule.get("any_keywords", [])]
        if any_kw and not any(kw in lowered_query for kw in any_kw):
            return {
                "rule_id": str(rule["rule_id"]),
                "matched": False,
                "rejected_tier": "tier1_any_keywords",
                "intent_action": "abstain",
                "score": 0.0,
                "estimated_tokens": 0,
            }

        # Tier 1: Trigram bitmask fast-reject
        anchor_text = str(rule.get("trigram_anchor_text", "")).strip()
        if anchor_text:
            q_mask = self.compute_trigram_bitmask(query_text)
            r_mask = self.compute_trigram_bitmask(anchor_text)
            overlap = 1.0 if r_mask == 0 else float((q_mask & r_mask).bit_count()) / float(r_mask.bit_count())
            if overlap < float(self.cell["tier1_min_trigram_overlap"]):
                return {
                    "rule_id": str(rule["rule_id"]),
                    "matched": False,
                    "rejected_tier": "tier1_trigram_bitmask",
                    "intent_action": "abstain",
                    "score": round(overlap, round_d),
                    "estimated_tokens": 0,
                }

        # Tier 2: Sparse stem + char n-gram + concept-synonym TF cosine + Role-Filler Frame bonus
        q_vec = self.build_sparse_vector(query_text)
        r_vec = self.build_sparse_vector(str(rule.get("exemplar_text", "")))
        lex_cos = self.sparse_cosine(q_vec, r_vec)
        frame_bonus, matched_slots, defined_slots = self.compute_frame_isomorphism(
            query.get("role_frame"),
            rule.get("role_frame"),
        )
        combined = min(1.0, lex_cos + frame_bonus)
        if combined < float(self.cell["tier2_min_score"]):
            return {
                "rule_id": str(rule["rule_id"]),
                "matched": False,
                "rejected_tier": "tier2_similarity",
                "intent_action": "abstain",
                "lexical_cosine": round(lex_cos, round_d),
                "frame_bonus": round(frame_bonus, round_d),
                "score": round(combined, round_d),
                "estimated_tokens": 0,
            }

        # Tier 3: Governance lens check (verified required, zero quarantined)
        gov_status = str(rule.get("governance_status", "unverified"))
        if bool(self.cell["require_verified_governance"]):
            if gov_status == "quarantined":
                return {
                    "rule_id": str(rule["rule_id"]),
                    "matched": False,
                    "rejected_tier": "tier3_quarantined_governance",
                    "intent_action": "abstain",
                    "score": round(combined, round_d),
                    "estimated_tokens": 0,
                }
            if gov_status != "verified":
                return {
                    "rule_id": str(rule["rule_id"]),
                    "matched": False,
                    "rejected_tier": "tier3_unverified_governance",
                    "intent_action": "abstain",
                    "score": round(combined, round_d),
                    "estimated_tokens": 0,
                }

        # Tier 3: Confidence-calibrated intent rule (0-token respond_directly vs shim_context)
        direct_resp = rule.get("direct_response")
        if (
            direct_resp is not None
            and bool(query.get("allow_direct_response", True))
            and combined >= float(self.cell["tier3_direct_confidence_threshold"])
        ):
            return {
                "rule_id": str(rule["rule_id"]),
                "matched": True,
                "rejected_tier": None,
                "intent_action": "respond_directly",
                "direct_response": str(direct_resp),
                "lexical_cosine": round(lex_cos, round_d),
                "frame_bonus": round(frame_bonus, round_d),
                "matched_frame_slots": matched_slots,
                "defined_frame_slots": defined_slots,
                "score": round(combined, round_d),
                "estimated_tokens": 0,
            }

        if combined >= float(self.cell["tier3_shim_confidence_threshold"]):
            shim_tokens = int(rule.get("shim_tokens", 1))
            return {
                "rule_id": str(rule["rule_id"]),
                "matched": True,
                "rejected_tier": None,
                "intent_action": "shim_context",
                "provision_id": str(rule.get("provision_id", rule["rule_id"])),
                "lexical_cosine": round(lex_cos, round_d),
                "frame_bonus": round(frame_bonus, round_d),
                "matched_frame_slots": matched_slots,
                "defined_frame_slots": defined_slots,
                "score": round(combined, round_d),
                "estimated_tokens": shim_tokens,
            }

        return {
            "rule_id": str(rule["rule_id"]),
            "matched": False,
            "rejected_tier": "tier3_below_confidence",
            "intent_action": "abstain",
            "score": round(combined, round_d),
            "estimated_tokens": 0,
        }

    def evaluate_all(self, query: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
        """Evaluate all trigger rules and return matched vs rejected evaluations."""
        evaluations = [self.evaluate_rule(query, r) for r in rules]
        matched = sorted(
            [ev for ev in evaluations if ev["matched"]],
            key=lambda item: (-float(item["score"]), str(item["rule_id"])),
        )
        return {
            "matched": matched,
            "evaluations": evaluations,
        }
