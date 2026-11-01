"""Strict JSON parser/canonicalizer, HTML entity & em-dash guard, and balanced caption wrapper."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from .aho_corasick import AhoCorasickAutomaton, load_default_grid_spec

RAW_ENTITY_REGEX = re.compile(r"&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);")
CLAUSE_PUNCT_SUFFIXES = (",", ":", ";")


class StrictJsonAndCopyFormatter:
    """Enforces strict RFC-safe JSON invariants, zero em-dashes/HTML entities and balanced captions."""

    def __init__(self, *, spec: dict[str, Any] | None = None) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        fm = cfg["formatter"]

        self._safe_int_bits = int(fm["ieee754_safe_int_bits"])
        self.max_safe_integer = (1 << self._safe_int_bits) - 1
        self._em_dash_char = chr(int(fm["em_dash_codepoint"]))
        self._em_dash_replacement = str(fm["em_dash_replacement"])

        self.caption_max_chars_per_line = int(fm["caption_max_chars_per_line"])
        self.caption_max_lines = int(fm["caption_max_lines"])
        self.caption_min_words_per_line = int(fm["caption_min_words_per_line"])
        self._clause_break_bonus = int(fm["clause_break_bonus"])
        self._dangling_end_words = frozenset(str(w).lower() for w in fm["dangling_end_words"])

        self._entity_ac = AhoCorasickAutomaton(case_insensitive=True)
        for ent in fm["html_entities"]:
            self._entity_ac.add_pattern(str(ent), rule_id="raw_html_entity", word_boundary=False)
        self._entity_ac.build()

    def _collect_unsafe_integers(self, value: Any, out: list[int]) -> None:
        if isinstance(value, int) and not isinstance(value, bool):
            if abs(value) > self.max_safe_integer:
                out.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                self._collect_unsafe_integers(item, out)
        elif isinstance(value, list):
            for item in value:
                self._collect_unsafe_integers(item, out)

    def parse_and_canonicalize_json(self, raw_json: str) -> dict[str, Any]:
        """Parse JSON strictly, rejecting duplicate keys, NaN/Infinity and >IEEE-754 safe integers."""
        duplicate_keys: list[str] = []
        non_finite_constants: list[str] = []

        def _pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            obj: dict[str, Any] = {}
            for k, v in pairs:
                if k in obj:
                    duplicate_keys.append(k)
                obj[k] = v
            return obj

        def _parse_constant(token: str) -> int:
            non_finite_constants.append(str(token))
            return 0

        try:
            parsed = json.loads(
                raw_json,
                object_pairs_hook=_pairs_hook,
                parse_constant=_parse_constant,
            )
        except json.JSONDecodeError as exc:
            return {
                "valid": False,
                "syntax_error": str(exc),
                "duplicate_keys": [],
                "non_finite_constants": [],
                "unsafe_integers": [],
                "canonical_json": None,
            }

        unsafe_ints: list[int] = []
        self._collect_unsafe_integers(parsed, unsafe_ints)
        valid = (
            len(duplicate_keys) == 0
            and len(non_finite_constants) == 0
            and len(unsafe_ints) == 0
        )
        canonical = (
            json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            if valid
            else None
        )
        return {
            "valid": valid,
            "syntax_error": None,
            "duplicate_keys": duplicate_keys,
            "non_finite_constants": non_finite_constants,
            "unsafe_integers": [str(x) for x in unsafe_ints],
            "canonical_json": canonical,
        }

    def strict_loads(self, raw_json: str) -> Any:
        """Load JSON or raise ValueError on duplicate keys, NaN/Infinity or unsafe integers."""
        res = self.parse_and_canonicalize_json(raw_json)
        if not res["valid"] or res["canonical_json"] is None:
            raise ValueError(f"Strict JSON validation failed: {res}")
        return json.loads(res["canonical_json"])

    def audit_plain_copy(self, text: str) -> dict[str, Any]:
        """Detect raw HTML entity leaks (&mdash;, &rarr;, &nbsp;, etc.) and U+2014 em-dashes."""
        ac_hits = self._entity_ac.scan(text)
        regex_hits = [m.group(0) for m in RAW_ENTITY_REGEX.finditer(text)]
        entity_leaks = list(dict.fromkeys([str(h["matched_text"]) for h in ac_hits] + regex_hits))
        em_dash_count = text.count(self._em_dash_char)
        sanitized = text.replace(self._em_dash_char, self._em_dash_replacement)
        return {
            "passed": len(entity_leaks) == 0 and em_dash_count == 0,
            "html_entity_leaks": entity_leaks,
            "em_dash_count": em_dash_count,
            "sanitized_text": " ".join(sanitized.split()),
        }

    def _is_dangling_break_word(self, word: str) -> bool:
        if word.endswith(CLAUSE_PUNCT_SUFFIXES):
            return False
        clean = word.strip(".,:;!?()[]\"'").lower()
        return clean in self._dangling_end_words

    def _search_lines(
        self,
        words: list[str],
        *,
        max_chars: int,
        lines_remaining: int,
        min_words: int,
    ) -> tuple[float, list[str]] | None:
        full_line = " ".join(words)
        if len(words) >= min_words and len(full_line) <= max_chars:
            return (0.0, [full_line])
        if lines_remaining <= 1:
            return None

        best: tuple[float, list[str]] | None = None
        max_split = len(words) - min_words
        for split_idx in range(min_words, max_split + 1):
            head_words = words[:split_idx]
            head_line = " ".join(head_words)
            if len(head_line) > max_chars:
                break
            last_word = head_words[-1]
            if self._is_dangling_break_word(last_word):
                continue
            tail_res = self._search_lines(
                words[split_idx:],
                max_chars=max_chars,
                lines_remaining=lines_remaining - 1,
                min_words=min_words,
            )
            if tail_res is None:
                continue
            tail_score, tail_lines = tail_res
            candidate_lines = [head_line, *tail_lines]
            lengths = [len(ln) for ln in candidate_lines]
            spread = float(max(lengths) - min(lengths))
            clause_bonus = float(self._clause_break_bonus) if last_word.endswith(CLAUSE_PUNCT_SUFFIXES) else 0.0
            total_cost = spread + tail_score - clause_bonus
            if best is None or total_cost < best[0]:
                best = (total_cost, candidate_lines)
        return best

    def wrap_balanced_caption(
        self,
        text: str,
        *,
        max_chars_per_line: int | None = None,
        max_lines: int | None = None,
    ) -> dict[str, Any]:
        """Wrap plain-text captions into balanced lines without 1-word orphans or trailing prepositions."""
        max_chars = int(max_chars_per_line if max_chars_per_line is not None else self.caption_max_chars_per_line)
        line_cap = int(max_lines if max_lines is not None else self.caption_max_lines)
        copy_audit = self.audit_plain_copy(text)

        words = text.split()
        if not words:
            return {
                "valid": copy_audit["passed"],
                "lines": [],
                "reason": None if copy_audit["passed"] else "copy_violation",
                "copy_audit": copy_audit,
            }

        single = " ".join(words)
        if len(single) <= max_chars:
            has_orphan = len(words) < self.caption_min_words_per_line
            valid = copy_audit["passed"] and not has_orphan
            return {
                "valid": valid,
                "lines": [single],
                "reason": None if valid else ("orphan_line" if has_orphan else "copy_violation"),
                "copy_audit": copy_audit,
            }

        found = self._search_lines(
            words,
            max_chars=max_chars,
            lines_remaining=line_cap,
            min_words=self.caption_min_words_per_line,
        )
        if found is None:
            return {
                "valid": False,
                "lines": [],
                "reason": "exceeds_line_bounds_or_no_balanced_split",
                "copy_audit": copy_audit,
            }

        _, wrapped_lines = found
        return {
            "valid": copy_audit["passed"],
            "lines": wrapped_lines,
            "reason": None if copy_audit["passed"] else "copy_violation",
            "copy_audit": copy_audit,
        }
