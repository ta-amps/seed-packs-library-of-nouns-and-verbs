"""Multi-probe 128-bit SimHash LSH expander, recall benchmark and MinHash LSH decontaminator."""

from __future__ import annotations

import copy
import hashlib
import random
import re
from typing import Any

from .filters import load_default_grid_spec

WORD_RE = re.compile(r"[a-z0-9]+")


class MultiProbeSimHashLshExpander:
    """128-bit 8-band SimHash LSH multi-probe key expander solving Pigeonhole recall collapse."""

    def __init__(self, *, spec: dict[str, Any] | None = None) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        hc = cfg["hash_constants"]
        sh = cfg["simhash_lsh"]
        self._hex_radix = int(hc["hex_radix"])
        self._bits_per_byte = int(hc["bits_per_byte"])
        self.total_bits = int(sh["total_bits"])
        self.hex_chars = int(sh["hex_chars"])
        self.num_bands = int(sh["num_bands"])
        self.band_bits = int(sh["band_bits"])
        self.band_hex_chars = int(sh["band_hex_chars"])
        self._exact_radius = int(sh["exact_radius_bits"])
        self._single_bit_radius = int(sh["single_bit_radius"])
        self._double_bit_radius = int(sh["double_bit_radius"])
        self.default_probe_radius_bits = int(sh["default_probe_radius_bits"])
        self.max_two_bit_probes = int(sh["max_two_bit_probes"])
        self._shingle_char_width = int(sh["shingle_char_width"])
        self._digest_bytes = int(sh["simhash_digest_bytes"])
        self._buckets: dict[str, set[str]] = {}
        self._signatures: dict[str, str] = {}

    def compute_simhash128(self, text: str) -> str:
        """Compute deterministic 128-bit (32-hex-char) SimHash from character n-grams."""
        normalized = " ".join(WORD_RE.findall(text.lower()))
        width = self._shingle_char_width
        if len(normalized) <= width:
            grams = [normalized or "_"]
        else:
            grams = [normalized[i : i + width] for i in range(len(normalized) - width + 1)]

        weights = [0 for _ in range(self.total_bits)]
        for gram in grams:
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=self._digest_bytes).digest()
            val = int.from_bytes(digest, "big")
            for bit_idx in range(self.total_bits):
                if ((val >> bit_idx) & 1) == 1:
                    weights[bit_idx] += 1
                else:
                    weights[bit_idx] -= 1

        out_val = 0
        for bit_idx in range(self.total_bits):
            if weights[bit_idx] >= 0:
                out_val |= 1 << bit_idx
        return f"{out_val:0{self.hex_chars}x}"

    def hamming_distance_hex(self, hex_a: str, hex_b: str) -> int:
        """Exact bitwise Hamming distance between two 128-bit hex signatures."""
        val_a = int(hex_a.strip().lower(), self._hex_radix)
        val_b = int(hex_b.strip().lower(), self._hex_radix)
        return (val_a ^ val_b).bit_count()

    def _split_bands(self, simhash_hex: str) -> list[int]:
        clean = simhash_hex.strip().lower()
        if len(clean) != self.hex_chars:
            raise ValueError(f"Expected {self.hex_chars}-char lowercase hex SimHash")
        bands: list[int] = []
        step = self.band_hex_chars
        for b_idx in range(self.num_bands):
            start = b_idx * step
            chunk = clean[start : start + step]
            bands.append(int(chunk, self._hex_radix))
        return bands

    def _format_band_key(self, band_idx: int, band_val: int) -> str:
        return f"b{band_idx}:{band_val:0{self.band_hex_chars}x}"

    def expand_probe_keys(
        self,
        simhash_hex: str,
        *,
        probe_radius_bits: int | None = None,
        two_bit_budget: int | None = None,
    ) -> list[str]:
        """Generate 0-bit exact band keys (8) + 1-bit neighbors (128 -> 136 total) + budgeted 2-bit keys."""
        radius = self.default_probe_radius_bits if probe_radius_bits is None else max(0, int(probe_radius_bits))
        budget_2bit = self.max_two_bit_probes if two_bit_budget is None else max(0, int(two_bit_budget))
        bands = self._split_bands(simhash_hex)

        keys: list[str] = []
        # 0-bit exact band keys (8 keys)
        for b_idx, b_val in enumerate(bands):
            keys.append(self._format_band_key(b_idx, b_val))

        # 1-bit multi-probe band neighbors (8 * 16 = 128 keys -> 136 total)
        if radius >= self._single_bit_radius:
            for b_idx, b_val in enumerate(bands):
                for bit_pos in range(self.band_bits):
                    neighbor = b_val ^ (1 << bit_pos)
                    keys.append(self._format_band_key(b_idx, neighbor))

        # Round-robin 2-bit band probes capped by budget_2bit
        if radius >= self._double_bit_radius and budget_2bit > 0:
            emitted_2bit = 0
            for p1 in range(self.band_bits):
                for p2 in range(p1 + 1, self.band_bits):
                    flip_mask = (1 << p1) ^ (1 << p2)
                    for b_idx, b_val in enumerate(bands):
                        keys.append(self._format_band_key(b_idx, b_val ^ flip_mask))
                        emitted_2bit += 1
                        if emitted_2bit >= budget_2bit:
                            return keys
        return keys

    def index_signature(self, item_id: str, simhash_hex: str) -> None:
        """Index item under its 8 exact band keys (1x storage footprint)."""
        clean = simhash_hex.strip().lower()
        self._signatures[item_id] = clean
        for exact_key in self.expand_probe_keys(clean, probe_radius_bits=self._exact_radius):
            self._buckets.setdefault(exact_key, set()).add(item_id)

    def query_candidates(
        self,
        simhash_hex: str,
        *,
        probe_radius_bits: int | None = None,
        two_bit_budget: int | None = None,
    ) -> set[str]:
        """Retrieve candidate item_ids using multi-probe query expansion."""
        hits: set[str] = set()
        for key in self.expand_probe_keys(
            simhash_hex,
            probe_radius_bits=probe_radius_bits,
            two_bit_budget=two_bit_budget,
        ):
            bucket = self._buckets.get(key)
            if bucket:
                hits.update(bucket)
        return hits


def benchmark_simhash_recall(
    *,
    distances: list[int] | None = None,
    trials_per_distance: int | None = None,
    seed: int | None = None,
    two_bit_budget: int | None = None,
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure exact 0-bit vs 1-bit (136 keys) vs 2-bit multi-probe candidate recall across Hamming distances."""
    cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
    sh = cfg["simhash_lsh"]
    expander = MultiProbeSimHashLshExpander(spec=cfg)

    dist_list = list(distances if distances is not None else sh["benchmark_distances"])
    trials = max(1, int(trials_per_distance if trials_per_distance is not None else sh["benchmark_trials_per_distance"]))
    rng_seed = int(seed if seed is not None else sh["benchmark_seed"])
    round_digits = int(sh["round_digits"])
    exact_r = int(sh["exact_radius_bits"])
    one_r = int(sh["single_bit_radius"])
    two_r = int(sh["double_bit_radius"])
    budget_2 = int(two_bit_budget if two_bit_budget is not None else sh["max_two_bit_probes"])

    rng = random.Random(rng_seed)
    all_bit_positions = list(range(expander.total_bits))
    by_distance: dict[str, dict[str, float]] = {}

    for d in dist_list:
        d_clamped = max(0, min(expander.total_bits, int(d)))
        hits_0 = 0
        hits_1 = 0
        hits_2 = 0
        for _ in range(trials):
            base_int = rng.getrandbits(expander.total_bits)
            flips = rng.sample(all_bit_positions, d_clamped)
            mut_int = base_int
            for pos in flips:
                mut_int ^= 1 << pos
            base_hex = f"{base_int:0{expander.hex_chars}x}"
            mut_hex = f"{mut_int:0{expander.hex_chars}x}"

            target_exact = set(expander.expand_probe_keys(base_hex, probe_radius_bits=exact_r))
            q0 = expander.expand_probe_keys(mut_hex, probe_radius_bits=exact_r)
            q1 = expander.expand_probe_keys(mut_hex, probe_radius_bits=one_r)
            q2 = expander.expand_probe_keys(mut_hex, probe_radius_bits=two_r, two_bit_budget=budget_2)

            if any(k in target_exact for k in q0):
                hits_0 += 1
            if any(k in target_exact for k in q1):
                hits_1 += 1
            if any(k in target_exact for k in q2):
                hits_2 += 1

        denom = float(trials)
        by_distance[str(d_clamped)] = {
            "exact_0bit_recall": round(float(hits_0) / denom, round_digits),
            "multiprobe_1bit_recall": round(float(hits_1) / denom, round_digits),
            "multiprobe_2bit_recall": round(float(hits_2) / denom, round_digits),
        }

    # Explicit Pigeonhole worst-case check: 1 flipped bit in every single band (d = num_bands = 8)
    pigeonhole_base = 0
    pigeonhole_1_per_band = 0
    for b_idx in range(expander.num_bands):
        pigeonhole_1_per_band |= 1 << (b_idx * expander.band_bits)
    base_hex = f"{pigeonhole_base:0{expander.hex_chars}x}"
    adv_hex = f"{pigeonhole_1_per_band:0{expander.hex_chars}x}"
    base_keys = set(expander.expand_probe_keys(base_hex, probe_radius_bits=exact_r))
    adv_q0 = expander.expand_probe_keys(adv_hex, probe_radius_bits=exact_r)
    adv_q1 = expander.expand_probe_keys(adv_hex, probe_radius_bits=one_r)

    return {
        "exact_probe_key_count": len(adv_q0),
        "multiprobe_1bit_key_count": len(adv_q1),
        "pigeonhole_1flip_per_band_exact_hit": any(k in base_keys for k in adv_q0),
        "pigeonhole_1flip_per_band_1bit_hit": any(k in base_keys for k in adv_q1),
        "recall_by_hamming_distance": by_distance,
    }


class MinHashLshDecontaminator:
    """Deterministic k-word shingle MinHash + banded LSH holdout contamination detector."""

    def __init__(
        self,
        *,
        shingle_words: int | None = None,
        num_bands: int | None = None,
        rows_per_band: int | None = None,
        jaccard_threshold: float | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        hc = cfg["hash_constants"]
        mh = cfg["minhash_lsh"]
        self._word_bytes = int(hc["word_bytes"])
        self.shingle_words = max(1, int(shingle_words if shingle_words is not None else mh["shingle_words"]))
        self.num_bands = max(1, int(num_bands if num_bands is not None else mh["num_bands"]))
        self.rows_per_band = max(1, int(rows_per_band if rows_per_band is not None else mh["rows_per_band"]))
        self.num_perm = self.num_bands * self.rows_per_band
        self.jaccard_threshold = float(
            jaccard_threshold if jaccard_threshold is not None else mh["contamination_jaccard_threshold"]
        )
        self._round_digits = int(mh["round_digits"])

        prime_exp = int(mh["mersenne_prime_exp"])
        self._prime = (1 << prime_exp) - 1
        rng = random.Random(int(mh["coeff_seed"]))
        self._coeffs_a = [rng.randrange(1, self._prime) for _ in range(self.num_perm)]
        self._coeffs_b = [rng.randrange(0, self._prime) for _ in range(self.num_perm)]

        self._holdout_shingles: dict[str, set[str]] = {}
        self._holdout_sigs: dict[str, tuple[int, ...]] = {}
        self._band_buckets: dict[tuple[int, int], set[str]] = {}

    def extract_shingles(self, text: str) -> set[str]:
        tokens = WORD_RE.findall(text.lower())
        if not tokens:
            return {"_empty_"}
        if len(tokens) <= self.shingle_words:
            return {" ".join(tokens)}
        return {
            " ".join(tokens[i : i + self.shingle_words])
            for i in range(len(tokens) - self.shingle_words + 1)
        }

    def _hash_shingle(self, shingle: str) -> int:
        digest = hashlib.blake2b(shingle.encode("utf-8"), digest_size=self._word_bytes).digest()
        return int.from_bytes(digest, "little") % self._prime

    def minhash_signature(self, text: str) -> tuple[int, ...]:
        shingle_hashes = [self._hash_shingle(s) for s in self.extract_shingles(text)]
        p = self._prime
        sig: list[int] = []
        for a, b in zip(self._coeffs_a, self._coeffs_b):
            min_val = min(((a * h + b) % p) for h in shingle_hashes)
            sig.append(min_val)
        return tuple(sig)

    def _band_hashes(self, sig: tuple[int, ...]) -> list[tuple[int, int]]:
        r = self.rows_per_band
        out: list[tuple[int, int]] = []
        for b_idx in range(self.num_bands):
            start = b_idx * r
            band_slice = sig[start : start + r]
            raw = ",".join(str(x) for x in band_slice).encode("utf-8")
            band_digest = int.from_bytes(
                hashlib.blake2b(raw, digest_size=self._word_bytes).digest(),
                "little",
            )
            out.append((b_idx, band_digest))
        return out

    def index_holdout(self, holdout_id: str, text: str) -> None:
        """Register an evaluation holdout item into banded MinHash LSH tables."""
        shingles = self.extract_shingles(text)
        sig = self.minhash_signature(text)
        self._holdout_shingles[holdout_id] = shingles
        self._holdout_sigs[holdout_id] = sig
        for band_key in self._band_hashes(sig):
            self._band_buckets.setdefault(band_key, set()).add(holdout_id)

    def estimated_jaccard(self, sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
        matches = sum(1 for x, y in zip(sig_a, sig_b) if x == y)
        return round(float(matches) / float(len(sig_a)), self._round_digits)

    def exact_jaccard(self, shingles_a: set[str], shingles_b: set[str]) -> float:
        union_len = len(shingles_a | shingles_b)
        if union_len == 0:
            return 1.0
        return round(float(len(shingles_a & shingles_b)) / float(union_len), self._round_digits)

    def scan_candidates(self, candidates: list[dict[str, str]]) -> dict[str, Any]:
        """Check candidate training documents for near-duplicate holdout contamination."""
        contaminated: list[dict[str, Any]] = []
        clean_ids: list[str] = []

        for item in candidates:
            cand_id = str(item["id"])
            text = str(item["text"])
            cand_shingles = self.extract_shingles(text)
            cand_sig = self.minhash_signature(text)

            lsh_hits: set[str] = set()
            for band_key in self._band_hashes(cand_sig):
                bucket = self._band_buckets.get(band_key)
                if bucket:
                    lsh_hits.update(bucket)

            best_match_id = ""
            best_exact = 0.0
            best_est = 0.0
            for holdout_id in sorted(lsh_hits):
                est = self.estimated_jaccard(cand_sig, self._holdout_sigs[holdout_id])
                exact = self.exact_jaccard(cand_shingles, self._holdout_shingles[holdout_id])
                if exact > best_exact:
                    best_exact = exact
                    best_est = est
                    best_match_id = holdout_id

            if best_exact >= self.jaccard_threshold:
                contaminated.append({
                    "candidate_id": cand_id,
                    "matched_holdout_id": best_match_id,
                    "estimated_jaccard": best_est,
                    "exact_jaccard": best_exact,
                })
            else:
                clean_ids.append(cand_id)

        return {
            "checked_count": len(candidates),
            "contaminated_count": len(contaminated),
            "contaminated": contaminated,
            "clean_ids": clean_ids,
        }
