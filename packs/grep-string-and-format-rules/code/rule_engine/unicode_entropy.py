"""Unicode Trojan Source/invisible/Tag-smuggling scanner, SHA-256 name guard and entropy masker."""

from __future__ import annotations

import copy
import hashlib
import math
import re
from typing import Any
import unicodedata

from .aho_corasick import load_default_grid_spec

WORD_TOKEN_RE = re.compile(r"[a-z0-9]+")
COMPOUND_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)+")
ENTROPY_CANDIDATE_RE = re.compile(r"[A-Za-z0-9+/=!@#$%^&*_.\-~]+")
HEX_LOWER_CHARS = frozenset("0123456789abcdef")


def _in_ranges(cp: int, ranges: list[tuple[int, int]]) -> bool:
    for low, high in ranges:
        if low <= cp <= high:
            return True
    return False


class UnicodeAndEntropySecurityScanner:
    """Scans text for non-NFC forms, Trojan bidi, hidden tags, hashed names and high-entropy secrets."""

    def __init__(
        self,
        *,
        blocked_name_hashes: set[str] | frozenset[str] | None = None,
        entropy_bits_threshold: float | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        us = cfg["unicode_security"]

        self._trojan_bidi_ranges = [(int(r[0]), int(r[1])) for r in us["trojan_bidi_ranges"]]
        self._zero_width_ranges = [(int(r[0]), int(r[1])) for r in us["zero_width_ranges"]]
        self._mid_text_bom = int(us["mid_text_bom_codepoint"])
        self._variation_ranges = [(int(r[0]), int(r[1])) for r in us["variation_selector_ranges"]]

        tag_lo, tag_hi = us["tag_block_range"]
        self._tag_block_range = (int(tag_lo), int(tag_hi))
        ascii_lo, ascii_hi = us["tag_ascii_range"]
        self._tag_ascii_range = (int(ascii_lo), int(ascii_hi))
        self._tag_base_offset = int(us["tag_base_offset"])
        self._hex_width = int(us["hex_format_width"])

        self._entropy_min_len = int(us["entropy_min_token_len"])
        self._entropy_min_classes = int(us["entropy_min_char_classes"])
        self.entropy_bits_threshold = float(
            entropy_bits_threshold if entropy_bits_threshold is not None else us["entropy_bits_threshold"]
        )
        self._entropy_round = int(us["entropy_round_digits"])
        self._exempt_hex_min = int(us["exempt_hex_min_len"])
        self._exempt_hex_max = int(us["exempt_hex_max_len"])
        self._mask_chars = int(us["mask_prefix_chars"])

        default_hashes = {str(h).strip().lower() for h in us.get("blocked_name_sha256", [])}
        extra_hashes = {str(h).strip().lower() for h in (blocked_name_hashes or set())}
        self._blocked_name_hashes = frozenset(default_hashes | extra_hashes)

    def _format_cp(self, cp: int) -> str:
        return f"U+{cp:0{self._hex_width}X}"

    def scan_unicode(self, text: str) -> dict[str, Any]:
        """Check NFC normalization and detect bidi overrides, zero-width, variation selectors and Tag smuggling."""
        is_nfc = unicodedata.is_normalized("NFC", text)
        nfc_text = unicodedata.normalize("NFC", text)

        trojan_bidi: list[dict[str, Any]] = []
        zero_width: list[dict[str, Any]] = []
        variation_selectors: list[dict[str, Any]] = []
        tag_chars: list[dict[str, Any]] = []
        decoded_tag_chars: list[str] = []

        tag_lo, tag_hi = self._tag_block_range
        ascii_lo, ascii_hi = self._tag_ascii_range

        for idx, ch in enumerate(text):
            cp = ord(ch)
            if _in_ranges(cp, self._trojan_bidi_ranges):
                trojan_bidi.append({"index": idx, "codepoint": self._format_cp(cp)})
            elif _in_ranges(cp, self._zero_width_ranges) or (idx > 0 and cp == self._mid_text_bom):
                zero_width.append({"index": idx, "codepoint": self._format_cp(cp)})
            elif _in_ranges(cp, self._variation_ranges):
                variation_selectors.append({"index": idx, "codepoint": self._format_cp(cp)})
            elif tag_lo <= cp <= tag_hi:
                tag_chars.append({"index": idx, "codepoint": self._format_cp(cp)})
                if ascii_lo <= cp <= ascii_hi:
                    decoded_tag_chars.append(chr(cp - self._tag_base_offset))

        return {
            "is_nfc": is_nfc,
            "nfc_normalized_text": nfc_text,
            "trojan_bidi_hits": trojan_bidi,
            "zero_width_hits": zero_width,
            "variation_selector_hits": variation_selectors,
            "tag_smuggling_hits": tag_chars,
            "decoded_tag_payload": "".join(decoded_tag_chars),
        }

    def scan_blocked_name_hashes(
        self,
        text: str,
        *,
        additional_hashes: set[str] | frozenset[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Check normalized words and hyphen/underscore compounds against SHA-256 blocklist digests."""
        active_hashes = (
            self._blocked_name_hashes | {str(h).strip().lower() for h in additional_hashes}
            if additional_hashes
            else self._blocked_name_hashes
        )
        if not active_hashes:
            return []

        lowered = text.lower()
        candidates: set[str] = set(WORD_TOKEN_RE.findall(lowered))
        for comp in COMPOUND_TOKEN_RE.findall(lowered):
            candidates.add(comp.replace("_", "-"))

        hits: list[dict[str, Any]] = []
        for tok in sorted(candidates):
            digest = hashlib.sha256(tok.encode("utf-8")).hexdigest()
            if digest in active_hashes:
                keep = min(len(tok), self._mask_chars)
                hits.append({
                    "rule_id": "blocked_private_name_hash",
                    "masked_token": f"{tok[:keep]}...(len={len(tok)})",
                    "matched_sha256_prefix": digest[: self._mask_chars],
                })
        return hits

    @staticmethod
    def shannon_entropy_bits(token: str) -> float:
        """Compute Shannon entropy in bits per character."""
        n = len(token)
        if n <= 1:
            return 0.0
        counts: dict[str, int] = {}
        for ch in token:
            counts[ch] = counts.get(ch, 0) + 1
        inv_n = 1.0 / float(n)
        entropy = 0.0
        for cnt in counts.values():
            p = float(cnt) * inv_n
            entropy -= p * math.log2(p)
        return entropy

    def is_exempt_lowercase_hex_digest(self, token: str) -> bool:
        """Exempt 32..64-char lowercase hex content-addressed digests (MD5, Git SHA-1, SHA-256)."""
        n = len(token)
        if not (self._exempt_hex_min <= n <= self._exempt_hex_max):
            return False
        return all(ch in HEX_LOWER_CHARS for ch in token)

    def scan_and_mask_high_entropy_tokens(self, text: str) -> dict[str, Any]:
        """Detect and mask mixed-class high-entropy tokens while exempting lowercase hex pins."""
        findings: list[dict[str, Any]] = []
        exempted_hex_count = 0
        out_parts: list[str] = []
        last_idx = 0

        for match in ENTROPY_CANDIDATE_RE.finditer(text):
            raw_tok = match.group(0)
            stripped = raw_tok.strip(".,:;()[]{}'\"~")
            if not stripped:
                continue
            lead_trim = raw_tok.find(stripped)
            tok_start = match.start() + lead_trim
            tok_end = tok_start + len(stripped)

            if self.is_exempt_lowercase_hex_digest(stripped):
                exempted_hex_count += 1
                continue

            if len(stripped) < self._entropy_min_len:
                continue

            has_lower = any(c.islower() for c in stripped)
            has_upper = any(c.isupper() for c in stripped)
            has_digit = any(c.isdigit() for c in stripped)
            has_symbol = any(not c.isalnum() for c in stripped)
            char_classes = int(has_lower) + int(has_upper) + int(has_digit) + int(has_symbol)
            if char_classes < self._entropy_min_classes:
                continue

            ent = self.shannon_entropy_bits(stripped)
            if ent >= self.entropy_bits_threshold:
                keep = min(len(stripped), self._mask_chars)
                masked = f"{stripped[:keep]}...<REDACTED_HIGH_ENTROPY>"
                out_parts.append(text[last_idx:tok_start])
                out_parts.append(masked)
                last_idx = tok_end
                findings.append({
                    "masked_token": f"{stripped[:keep]}...({len(stripped)} chars)",
                    "entropy_bits_per_char": round(ent, self._entropy_round),
                    "char_classes": char_classes,
                    "start": tok_start,
                    "end": tok_end,
                })

        out_parts.append(text[last_idx:])
        return {
            "high_entropy_hits": findings,
            "exempted_hex_digest_count": exempted_hex_count,
            "masked_text": "".join(out_parts),
        }

    def scan_all(self, text: str) -> dict[str, Any]:
        """Run full Unicode safety, SHA-256 name-hash and Shannon-entropy security scan."""
        uni = self.scan_unicode(text)
        names = self.scan_blocked_name_hashes(text)
        ent = self.scan_and_mask_high_entropy_tokens(text)
        return {
            "unicode": uni,
            "blocked_name_hits": names,
            "entropy": ent,
        }
