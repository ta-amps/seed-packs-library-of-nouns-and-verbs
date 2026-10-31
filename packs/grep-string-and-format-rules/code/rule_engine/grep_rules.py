"""Portable grep rule runner, outbound negation checker, secret prefix scanner and copy guards."""

from __future__ import annotations

import copy
import re
from typing import Any

from .aho_corasick import AhoCorasickAutomaton, load_default_grid_spec

LOOKBEHIND_RE = re.compile(r"\(\?<[=!]")
NAMED_GROUP_RE = re.compile(r"\(\?P[<a-zA-Z=]")
INLINE_FLAG_RE = re.compile(r"\(\?[aiLmsux]+")
BACKREF_RE = re.compile(r"\\[1-9]")
PY_ANCHOR_RE = re.compile(r"\\[AZ]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;!?\n])\s+")
HOME_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users)/([A-Za-z0-9._-]+)/")


def _word_or_phrase_pattern(terms: list[str]) -> re.Pattern[str]:
    escaped = sorted((re.escape(t) for t in terms if t), key=len, reverse=True)
    joined = "|".join(escaped)
    return re.compile(rf"(?i)(?<![A-Za-z0-9_])(?:{joined})(?![A-Za-z0-9_])")


class PortableGrepRuleRunner:
    """Declarative ECMA-262 portable grep engine with negation, secret, path and stamp guards."""

    def __init__(self, *, spec: dict[str, Any] | None = None) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        gr = cfg["grep_rules"]

        self.secret_prefixes: list[str] = [str(p) for p in gr["secret_prefixes"]]
        self._secret_min_total_len = int(gr["secret_min_total_len"])
        self._akia_prefix = str(gr["akia_prefix"])
        self._akia_exact_len = int(gr["akia_exact_len"])
        self._mask_prefix_chars = int(gr["mask_prefix_chars"])
        self._home_replacement = str(gr["home_path_replacement"])

        self._outbound_re = _word_or_phrase_pattern([str(w) for w in gr["outbound_effect_words"]])
        self._negation_re = _word_or_phrase_pattern([str(w) for w in gr["negation_cues"]])

        self._prefix_ac = AhoCorasickAutomaton(case_insensitive=False)
        for pref in self.secret_prefixes:
            self._prefix_ac.add_pattern(pref, rule_id=f"secret_prefix:{pref}", word_boundary=False)
        self._prefix_ac.build()

        self._accusatory_ac = AhoCorasickAutomaton(case_insensitive=True)
        for term in gr["accusatory_terms"]:
            self._accusatory_ac.add_pattern(str(term), rule_id="accusatory_copy", word_boundary=True)
        self._accusatory_ac.build()

        self._stamp_ac = AhoCorasickAutomaton(case_insensitive=True)
        for stamp in gr["blocked_visible_stamps"]:
            self._stamp_ac.add_pattern(str(stamp), rule_id="non_functional_stamp", word_boundary=True)
        self._stamp_ac.build()

    @staticmethod
    def validate_ecmascript_portable(pattern: str) -> dict[str, Any]:
        """Verify regex avoids lookbehinds, Python named groups, inline flags and backreferences."""
        reasons: list[str] = []
        if LOOKBEHIND_RE.search(pattern):
            reasons.append("lookbehind_not_portable")
        if NAMED_GROUP_RE.search(pattern):
            reasons.append("python_named_group_not_portable")
        if INLINE_FLAG_RE.search(pattern):
            reasons.append("inline_flag_not_portable")
        if BACKREF_RE.search(pattern):
            reasons.append("backreference_not_portable")
        if PY_ANCHOR_RE.search(pattern):
            reasons.append("python_anchor_not_portable")
        try:
            re.compile(pattern)
        except re.error as exc:
            reasons.append(f"invalid_regex_syntax:{exc}")
        return {
            "portable": len(reasons) == 0,
            "reasons": reasons,
        }

    def _mask_token(self, token: str) -> str:
        keep = min(len(token), self._mask_prefix_chars)
        return f"{token[:keep]}...({len(token)} chars)"

    def scan_outbound_effects(self, text: str) -> list[dict[str, Any]]:
        """Flag outbound effect verbs unless negated within the same sentence."""
        violations: list[dict[str, Any]] = []
        for sentence in SENTENCE_SPLIT_RE.split(text):
            stripped = sentence.strip()
            if not stripped:
                continue
            hit = self._outbound_re.search(stripped)
            if hit and not self._negation_re.search(stripped):
                violations.append({
                    "rule_id": "unnegated_outbound_effect",
                    "matched_word": hit.group(0),
                    "sentence": stripped,
                })
        return violations

    def scan_secret_prefixes(self, text: str) -> list[dict[str, Any]]:
        """Detect credential tokens starting with configured secret prefixes and mask matches."""
        findings: list[dict[str, Any]] = []
        covered_until = -1
        n = len(text)

        for hit in self._prefix_ac.scan(text):
            start = int(hit["start"])
            pref = str(hit["pattern"])
            if start < covered_until:
                continue
            if start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
                continue

            cursor = start + len(pref)
            while cursor < n and (text[cursor].isalnum() or text[cursor] in "_-"):
                cursor += 1
            token = text[start:cursor]

            if pref == self._akia_prefix:
                is_secret = len(token) == self._akia_exact_len and token.isalnum() and token.isupper()
            else:
                is_secret = len(token) >= self._secret_min_total_len

            if is_secret:
                covered_until = cursor
                findings.append({
                    "rule_id": str(hit["rule_id"]),
                    "prefix": pref,
                    "masked_match": self._mask_token(token),
                    "start": start,
                    "end": cursor,
                })
        return findings

    def scrub_home_paths(self, text: str) -> dict[str, Any]:
        """Detect and scrub local /home/<user>/ and /Users/<user>/ filesystem paths."""
        findings: list[dict[str, Any]] = []
        for match in HOME_PATH_RE.finditer(text):
            findings.append({
                "rule_id": "local_home_path",
                "masked_path": self._home_replacement,
                "start": match.start(),
                "end": match.end(),
            })
        scrubbed = HOME_PATH_RE.sub(self._home_replacement, text)
        return {
            "path_leak_count": len(findings),
            "findings": findings,
            "scrubbed_text": scrubbed,
        }

    def scan_public_good_accusatory_copy(self, text: str) -> list[dict[str, Any]]:
        """Flag accusatory phrasing so public-good reports stay factual and receipt-grounded."""
        return self._accusatory_ac.scan(text, enforce_word_boundary=True)

    def scan_visible_stamps(self, text: str) -> list[dict[str, Any]]:
        """Reject visible non-functional placeholder stamps in user-facing surfaces."""
        return self._stamp_ac.scan(text, enforce_word_boundary=True)

    def evaluate_declarative_rules(
        self,
        text: str,
        rules: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate ECMA-262 portability of declarative grep rules and evaluate them over text."""
        portability_errors: list[dict[str, Any]] = []
        rule_hits: list[dict[str, Any]] = []

        for rule in rules:
            rid = str(rule["id"])
            pat = str(rule["pattern"])
            neg_exempt = bool(rule.get("negation_exempt", False))
            port = self.validate_ecmascript_portable(pat)
            if not port["portable"]:
                portability_errors.append({
                    "rule_id": rid,
                    "reasons": port["reasons"],
                })
                continue

            compiled = re.compile(pat)
            if neg_exempt:
                for sentence in SENTENCE_SPLIT_RE.split(text):
                    stripped = sentence.strip()
                    if not stripped:
                        continue
                    m = compiled.search(stripped)
                    if m and not self._negation_re.search(stripped):
                        rule_hits.append({
                            "rule_id": rid,
                            "matched_text": m.group(0),
                            "sentence": stripped,
                        })
            else:
                for m in compiled.finditer(text):
                    rule_hits.append({
                        "rule_id": rid,
                        "matched_text": m.group(0),
                        "start": m.start(),
                        "end": m.end(),
                    })

        return {
            "portability_errors": portability_errors,
            "rule_hits": rule_hits,
        }

    def audit_text(
        self,
        text: str,
        *,
        declarative_rules: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Run unified outbound, secret-prefix, home-path, accusatory-copy and stamp checks."""
        outbound = self.scan_outbound_effects(text)
        secrets = self.scan_secret_prefixes(text)
        paths = self.scrub_home_paths(text)
        accusatory = self.scan_public_good_accusatory_copy(text)
        stamps = self.scan_visible_stamps(text)
        decl = self.evaluate_declarative_rules(text, declarative_rules or [])
        return {
            "outbound_violations": outbound,
            "secret_prefix_hits": secrets,
            "home_path_scrub": paths,
            "accusatory_copy_hits": accusatory,
            "visible_stamp_hits": stamps,
            "declarative_evaluation": decl,
        }
