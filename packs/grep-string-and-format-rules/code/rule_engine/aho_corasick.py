"""Single-pass O(|text| + matches) Aho-Corasick multi-pattern literal automaton."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

SPEC_PATH = Path(__file__).resolve().with_name("default_grid_spec.json")


def load_default_grid_spec() -> dict[str, Any]:
    """Load externalized declarative configuration grid specification for rule_engine."""
    return dict(json.loads(SPEC_PATH.read_text(encoding="utf-8")))


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


@dataclass
class _AcNode:
    transitions: dict[str, int] = field(default_factory=dict)
    fail: int = 0
    outputs: list[tuple[str, str, bool]] = field(default_factory=list)


class AhoCorasickAutomaton:
    """Trie + failure-link + output-link multi-pattern scanner running in O(|text| + matches)."""

    def __init__(self, *, case_insensitive: bool = False) -> None:
        self.case_insensitive = bool(case_insensitive)
        self._nodes: list[_AcNode] = [_AcNode()]
        self._built = False
        self.pattern_count = 0

    def add_pattern(
        self,
        pattern: str,
        *,
        rule_id: str | None = None,
        word_boundary: bool = False,
    ) -> None:
        """Insert a non-empty literal pattern into the trie prior to BFS failure-link compilation."""
        if not pattern:
            raise ValueError("AhoCorasickAutomaton pattern must be non-empty")
        if self._built:
            raise RuntimeError("Cannot add patterns after automaton has been compiled")
        norm = pattern.lower() if self.case_insensitive else pattern
        state = 0
        for ch in norm:
            nxt = self._nodes[state].transitions.get(ch)
            if nxt is None:
                nxt = len(self._nodes)
                self._nodes.append(_AcNode())
                self._nodes[state].transitions[ch] = nxt
            state = nxt
        rid = str(rule_id if rule_id is not None else pattern)
        self._nodes[state].outputs.append((rid, pattern, bool(word_boundary)))
        self.pattern_count += 1

    def build(self) -> AhoCorasickAutomaton:
        """Compile BFS failure links and merge suffix output links in linear O(sum(|pattern|)) time."""
        if self._built:
            return self
        queue: deque[int] = deque()
        root_transitions = self._nodes[0].transitions
        for nxt in root_transitions.values():
            self._nodes[nxt].fail = 0
            queue.append(nxt)

        while queue:
            cur = queue.popleft()
            cur_fail = self._nodes[cur].fail
            for ch, child in self._nodes[cur].transitions.items():
                queue.append(child)
                fallback = cur_fail
                while fallback != 0 and ch not in self._nodes[fallback].transitions:
                    fallback = self._nodes[fallback].fail
                fail_target = self._nodes[fallback].transitions.get(ch, 0)
                self._nodes[child].fail = fail_target
                if self._nodes[fail_target].outputs:
                    self._nodes[child].outputs.extend(self._nodes[fail_target].outputs)

        self._built = True
        return self

    def scan(self, text: str, *, enforce_word_boundary: bool = False) -> list[dict[str, Any]]:
        """Scan text in one pass, returning ordered match spans."""
        if not self._built:
            self.build()
        haystack = text.lower() if self.case_insensitive else text
        text_len = len(text)
        state = 0
        matches: list[dict[str, Any]] = []

        for idx, ch in enumerate(haystack):
            while state != 0 and ch not in self._nodes[state].transitions:
                state = self._nodes[state].fail
            state = self._nodes[state].transitions.get(ch, 0)
            outputs = self._nodes[state].outputs
            if not outputs:
                continue
            for rule_id, orig_pat, pat_wb in outputs:
                pat_len = len(orig_pat)
                start = idx - pat_len + 1
                end = idx + 1
                if enforce_word_boundary or pat_wb:
                    if _is_word_char(orig_pat[0]) and start > 0 and _is_word_char(text[start - 1]):
                        continue
                    if _is_word_char(orig_pat[-1]) and end < text_len and _is_word_char(text[end]):
                        continue
                matches.append({
                    "rule_id": rule_id,
                    "pattern": orig_pat,
                    "matched_text": text[start:end],
                    "start": start,
                    "end": end,
                })
        return matches
