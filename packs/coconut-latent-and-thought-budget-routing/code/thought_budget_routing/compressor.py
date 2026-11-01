"""LatentStateSketchCompressor and OverthinkingLoopDetector for multi-turn reasoning traces."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from .grid import resolve_grid_cell

FILLER_STOPWORDS: frozenset[str] = frozenset(
    {
        "about",
        "actually",
        "again",
        "also",
        "and",
        "another",
        "are",
        "basically",
        "because",
        "been",
        "before",
        "being",
        "both",
        "but",
        "carefully",
        "certainly",
        "checking",
        "considering",
        "could",
        "currently",
        "definitely",
        "does",
        "double",
        "elaborate",
        "essentially",
        "even",
        "examining",
        "exploring",
        "first",
        "for",
        "from",
        "furthermore",
        "generally",
        "going",
        "have",
        "having",
        "here",
        "honestly",
        "however",
        "importantly",
        "initially",
        "into",
        "just",
        "keep",
        "let",
        "like",
        "look",
        "looking",
        "make",
        "maybe",
        "meanwhile",
        "might",
        "more",
        "moreover",
        "most",
        "much",
        "naturally",
        "need",
        "nevertheless",
        "next",
        "notably",
        "now",
        "obviously",
        "once",
        "only",
        "other",
        "overall",
        "perhaps",
        "pondering",
        "possibly",
        "practically",
        "previously",
        "probably",
        "really",
        "rechecking",
        "reconsidering",
        "reflecting",
        "reiterating",
        "remember",
        "repeating",
        "restating",
        "reviewing",
        "same",
        "second",
        "seemingly",
        "seems",
        "should",
        "simply",
        "since",
        "some",
        "speaking",
        "specifically",
        "still",
        "such",
        "suppose",
        "sure",
        "tentatively",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "therefore",
        "these",
        "they",
        "thing",
        "think",
        "thinking",
        "this",
        "thoroughly",
        "those",
        "though",
        "thought",
        "through",
        "thus",
        "truly",
        "trying",
        "turn",
        "ultimately",
        "understanding",
        "very",
        "wait",
        "well",
        "were",
        "what",
        "when",
        "where",
        "whereas",
        "whether",
        "which",
        "while",
        "with",
        "wonder",
        "wondering",
        "would",
    }
)

WORD_RE = re.compile(r"[A-Za-z0-9_.:<>=!-]+")
FACT_ASSIGN_RE = re.compile(r"\b([a-z][a-z0-9_]*)=([A-Za-z0-9_.:-]+)\b")
RELATIONAL_CONSTRAINT_RE = re.compile(r"\b([a-z][a-z0-9_]*\s*(?:<=|>=|==|!=)\s*[A-Za-z0-9_.-]+)")
TAGGED_LINE_RE = re.compile(r"\b(CONSTRAINT|OBLIGATION|RESOLVED):\s*([^.,;\n]+)")


def count_tokens(text: str) -> int:
    """Count lexical and symbolic reasoning tokens in a string."""
    return len(WORD_RE.findall(text))


class LatentStateSketchCompressor:
    """Compresses verbose multi-turn reasoning traces into invariant + continuous latent checkpoints."""

    def __init__(
        self,
        overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.grid, self.cell, self.constants = resolve_grid_cell(overrides, regime=regime, spec=spec)
        self.dims = int(self.cell["latent_vector_dims"])
        self.sha_len = int(self.constants["sha256_hex_length"])
        self.hash_slice_len = int(self.constants["hash_byte_slice_len"])
        self.sign_modulus = int(self.constants["sign_bit_modulus"])
        self.min_token_chars = int(self.constants["min_token_chars"])
        self.min_compression_target = float(self.constants["min_compression_ratio_target"])
        self.round_digits = int(self.constants["round_digits"])
        self.sha_re = re.compile(rf"\b[0-9a-f]{{{self.sha_len}}}\b")

    def encode_latent_vector(self, text: str, extra_features: list[str] | None = None) -> list[float]:
        """Project salient non-filler reasoning tokens into an L2-normalized continuous sketch vector."""
        vec = [0.0] * self.dims
        raw_words = [w.lower().strip(".,:;!?()[]{}") for w in WORD_RE.findall(text)]
        features = [
            w
            for w in raw_words
            if len(w) >= self.min_token_chars and w not in FILLER_STOPWORDS
        ]
        if extra_features:
            features.extend(f.lower() for f in extra_features if f)

        for feat in features:
            digest = hashlib.sha256(feat.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[: self.hash_slice_len], "big") % self.dims
            sign = 1.0 if (digest[self.hash_slice_len] % self.sign_modulus) == 0 else -1.0
            vec[bucket] += sign

        norm = math.sqrt(sum(v * v for v in vec))
        if norm <= 0.0:
            return vec
        return [round(v / norm, self.round_digits) for v in vec]

    @staticmethod
    def extract_turn_invariants(
        turn: dict[str, Any] | str, sha_re: re.Pattern[str]
    ) -> dict[str, Any]:
        """Extract structured state facts, binding constraints, obligations and SHA-256 digests."""
        if isinstance(turn, str):
            prose = turn
            explicit_facts: dict[str, Any] = {}
            explicit_constraints: list[str] = []
            explicit_obligations: list[str] = []
            explicit_resolved: list[str] = []
            explicit_hashes: list[str] = []
        else:
            prose = str(turn.get("thought", turn.get("text", "")))
            explicit_facts = dict(turn.get("facts", {}))
            explicit_constraints = [str(x).strip() for x in turn.get("constraints", [])]
            explicit_obligations = [str(x).strip() for x in turn.get("obligations", [])]
            explicit_resolved = [str(x).strip() for x in turn.get("resolved_obligations", [])]
            explicit_hashes = [str(x).strip().lower() for x in turn.get("verified_hashes", [])]

        facts: dict[str, str] = {str(k): str(v) for k, v in explicit_facts.items()}
        for k, v in FACT_ASSIGN_RE.findall(prose):
            facts[k] = v

        constraints: list[str] = list(explicit_constraints)
        obligations: list[str] = list(explicit_obligations)
        resolved: list[str] = list(explicit_resolved)

        for tag, body in TAGGED_LINE_RE.findall(prose):
            cleaned = body.strip()
            if tag == "CONSTRAINT":
                constraints.append(cleaned)
            elif tag == "OBLIGATION":
                obligations.append(cleaned)
            elif tag == "RESOLVED":
                resolved.append(cleaned)

        for rel_expr in RELATIONAL_CONSTRAINT_RE.findall(prose):
            normalized = " ".join(rel_expr.split())
            if normalized not in constraints:
                constraints.append(normalized)

        hashes: list[str] = list(explicit_hashes)
        for digest in sha_re.findall(prose.lower()):
            if digest not in hashes:
                hashes.append(digest)

        return {
            "prose": prose,
            "facts": facts,
            "constraints": constraints,
            "obligations": obligations,
            "resolved": resolved,
            "hashes": hashes,
        }

    def compress_trace(
        self,
        turns: list[dict[str, Any] | str],
        *,
        ground_truth: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compress a multi-turn trace into a compact invariant + latent-vector checkpoint."""
        state_facts: dict[str, str] = {}
        binding_constraints: list[str] = []
        open_obligations: list[str] = []
        resolved_obligations: list[str] = []
        verified_hashes: list[str] = []
        all_prose_segments: list[str] = []

        raw_token_count = 0
        for turn in turns:
            extracted = self.extract_turn_invariants(turn, self.sha_re)
            prose = extracted["prose"]
            all_prose_segments.append(prose)
            raw_token_count += count_tokens(prose)
            if isinstance(turn, dict):
                for key in ("constraints", "obligations", "resolved_obligations", "verified_hashes"):
                    for item in turn.get(key, []):
                        raw_token_count += count_tokens(str(item))
                for k, v in dict(turn.get("facts", {})).items():
                    raw_token_count += count_tokens(f"{k}={v}")

            state_facts.update(extracted["facts"])
            for c in extracted["constraints"]:
                if c and c not in binding_constraints:
                    binding_constraints.append(c)
            for ob in extracted["obligations"]:
                if ob and ob not in open_obligations and ob not in resolved_obligations:
                    open_obligations.append(ob)
            for res in extracted["resolved"]:
                if res and res not in resolved_obligations:
                    resolved_obligations.append(res)
                if res in open_obligations:
                    open_obligations.remove(res)
            for h in extracted["hashes"]:
                if h and h not in verified_hashes:
                    verified_hashes.append(h)

        invariant_features = (
            [f"{k}={v}" for k, v in sorted(state_facts.items())]
            + binding_constraints
            + open_obligations
            + verified_hashes
        )
        latent_vec = self.encode_latent_vector(" ".join(all_prose_segments), invariant_features)
        latent_digest = hashlib.sha256(
            json.dumps(latent_vec, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[: self.grid.sha256_prefix_chars]

        compact_lines: list[str] = [f"LATENT[{latent_digest}]"]
        if state_facts:
            compact_lines.append(
                "FACTS[" + ";".join(f"{k}={v}" for k, v in sorted(state_facts.items())) + "]"
            )
        if binding_constraints:
            compact_lines.append("CONSTRAINTS[" + ";".join(binding_constraints) + "]")
        if open_obligations:
            compact_lines.append("OBLIGATIONS[" + ";".join(open_obligations) + "]")
        if verified_hashes:
            compact_lines.append("HASHES[" + ";".join(verified_hashes) + "]")

        checkpoint_wire = " ".join(compact_lines)
        compressed_token_count = max(1, count_tokens(checkpoint_wire))
        compression_ratio = round(raw_token_count / compressed_token_count, self.round_digits)

        checkpoint = {
            "state_facts": state_facts,
            "binding_constraints": binding_constraints,
            "open_obligations": open_obligations,
            "resolved_obligations": resolved_obligations,
            "verified_hashes": verified_hashes,
            "latent_state_vector": latent_vec,
            "latent_sketch_id": latent_digest,
            "wire_summary": checkpoint_wire,
        }

        recall_metrics = self._evaluate_recall(checkpoint, ground_truth)
        return {
            "checkpoint": checkpoint,
            "raw_token_count": raw_token_count,
            "compressed_token_count": compressed_token_count,
            "compression_ratio": compression_ratio,
            "meets_compression_target": compression_ratio >= self.min_compression_target,
            **recall_metrics,
        }

    def _evaluate_recall(
        self, checkpoint: dict[str, Any], ground_truth: dict[str, Any] | None
    ) -> dict[str, float]:
        if not ground_truth:
            return {
                "binding_constraint_recall": 1.0,
                "open_obligation_recall": 1.0,
                "verified_hash_recall": 1.0,
            }

        def _set_recall(expected: list[str], observed: list[str]) -> float:
            if not expected:
                return 1.0
            hits = sum(1 for item in expected if item in observed)
            return round(hits / len(expected), self.round_digits)

        return {
            "binding_constraint_recall": _set_recall(
                [str(x) for x in ground_truth.get("binding_constraints", [])],
                checkpoint["binding_constraints"],
            ),
            "open_obligation_recall": _set_recall(
                [str(x) for x in ground_truth.get("open_obligations", [])],
                checkpoint["open_obligations"],
            ),
            "verified_hash_recall": _set_recall(
                [str(x).lower() for x in ground_truth.get("verified_hashes", [])],
                checkpoint["verified_hashes"],
            ),
        }


class OverthinkingLoopDetector:
    """Detects repetitive reasoning cycles and invariant stagnation across multi-turn steps."""

    def __init__(
        self,
        overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.grid, self.cell, self.constants = resolve_grid_cell(overrides, regime=regime, spec=spec)
        self.compressor = LatentStateSketchCompressor(overrides, regime=regime, spec=spec)
        self.cosine_threshold = float(self.cell["loop_cosine_threshold"])
        self.jaccard_threshold = float(self.cell["loop_shingle_jaccard_threshold"])
        self.stagnation_window = int(self.cell["stagnation_window"])
        self.shingle_size = int(self.constants["shingle_size"])
        self.min_token_chars = int(self.constants["min_token_chars"])
        self.round_digits = int(self.constants["round_digits"])

    def _content_shingles(self, text: str) -> set[tuple[str, ...]]:
        words = [
            w.lower().strip(".,:;!?()[]{}")
            for w in WORD_RE.findall(text)
            if len(w.strip(".,:;!?()[]{}")) >= self.min_token_chars
            and w.lower().strip(".,:;!?()[]{}") not in FILLER_STOPWORDS
        ]
        if not words:
            return set()
        if len(words) < self.shingle_size:
            return {tuple(words)}
        return {
            tuple(words[idx : idx + self.shingle_size])
            for idx in range(len(words) - self.shingle_size + 1)
        }

    @staticmethod
    def _cosine(vec_a: list[float], vec_b: list[float]) -> float:
        return sum(a * b for a, b in zip(vec_a, vec_b))

    @staticmethod
    def _jaccard(set_a: set[tuple[str, ...]], set_b: set[tuple[str, ...]]) -> float:
        union = set_a | set_b
        if not union:
            return 0.0
        return len(set_a & set_b) / len(union)

    def inspect_trace(self, steps: list[dict[str, Any] | str]) -> dict[str, Any]:
        """Scan reasoning steps for repetitive latent cycles with zero new invariants."""
        vectors: list[list[float]] = []
        shingles_list: list[set[tuple[str, ...]]] = []
        seen_invariants: set[str] = set()
        step_tokens: list[int] = []

        consecutive_repetitive = 0
        trigger_index = -1
        peak_cosine = 0.0
        peak_jaccard = 0.0

        for idx, step in enumerate(steps):
            extracted = self.compressor.extract_turn_invariants(step, self.compressor.sha_re)
            prose = extracted["prose"]
            step_tokens.append(count_tokens(prose))

            cur_invariants: set[str] = set()
            for k, v in extracted["facts"].items():
                cur_invariants.add(f"fact:{k}={v}")
            for c in extracted["constraints"]:
                cur_invariants.add(f"constraint:{c}")
            for ob in extracted["obligations"]:
                cur_invariants.add(f"obligation:{ob}")
            for res in extracted["resolved"]:
                cur_invariants.add(f"resolved:{res}")
            for h in extracted["hashes"]:
                cur_invariants.add(f"hash:{h}")

            new_invariants = cur_invariants - seen_invariants
            seen_invariants |= cur_invariants

            vec = self.compressor.encode_latent_vector(prose)
            sh = self._content_shingles(prose)

            if idx > 0 and trigger_index < 0:
                start = max(0, idx - self.stagnation_window)
                max_cos = max(self._cosine(vec, prev_v) for prev_v in vectors[start:idx])
                max_jac = max(self._jaccard(sh, prev_s) for prev_s in shingles_list[start:idx])
                peak_cosine = max(peak_cosine, max_cos)
                peak_jaccard = max(peak_jaccard, max_jac)

                repetitive = (
                    max_cos >= self.cosine_threshold or max_jac >= self.jaccard_threshold
                ) and len(new_invariants) == 0

                if repetitive:
                    consecutive_repetitive += 1
                    if consecutive_repetitive >= self.stagnation_window - 1:
                        trigger_index = idx
                else:
                    consecutive_repetitive = 0

            vectors.append(vec)
            shingles_list.append(sh)

        loop_detected = trigger_index >= 0
        tokens_saved = sum(step_tokens[trigger_index:]) if loop_detected else 0
        return {
            "loop_detected": loop_detected,
            "trigger_step_index": trigger_index,
            "recommended_action": "halt_and_emit_checkpoint" if loop_detected else "continue",
            "peak_latent_cosine": round(peak_cosine, self.round_digits),
            "peak_shingle_jaccard": round(peak_jaccard, self.round_digits),
            "tokens_saved_by_early_halt": tokens_saved,
        }
