"""Grid-governed BlockedBloomFilter, CuckooFilter and StaticXorFingerprintFilter."""

from __future__ import annotations

import base64
from collections import deque
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

SPEC_PATH = Path(__file__).resolve().with_name("default_grid_spec.json")


def load_default_grid_spec() -> dict[str, Any]:
    """Load externalized configuration grid specification for probabilistic filters and sketches."""
    return dict(json.loads(SPEC_PATH.read_text(encoding="utf-8")))


def _to_bytes(key: str | bytes) -> bytes:
    if isinstance(key, bytes):
        return key
    return str(key).encode("utf-8")


def _digest_words(
    raw: bytes,
    *,
    algo: str,
    digest_bytes: int,
    word_bytes: int,
    seed: int = 0,
) -> tuple[int, int, int, int]:
    seed_prefix = int(seed).to_bytes(word_bytes, "little", signed=False) if seed >= 0 else b""
    if algo == "sha256":
        digest = hashlib.sha256(seed_prefix + raw).digest()
    else:
        digest = hashlib.blake2b(seed_prefix + raw, digest_size=digest_bytes).digest()
    p1 = word_bytes
    p2 = p1 + word_bytes
    p3 = p2 + word_bytes
    p4 = p3 + word_bytes
    w0 = int.from_bytes(digest[0:p1], "little")
    w1 = int.from_bytes(digest[p1:p2], "little")
    w2 = int.from_bytes(digest[p2:p3], "little")
    w3 = int.from_bytes(digest[p3:p4], "little")
    return w0, w1, w2, w3


class BlockedBloomFilter:
    """Cache-line partitioned Bloom filter using Kirsch-Mitzenmacher double hashing."""

    def __init__(
        self,
        *,
        num_blocks: int | None = None,
        block_bits: int | None = None,
        num_hashes: int | None = None,
        digest_algorithm: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        hc = cfg["hash_constants"]
        bb = cfg["blocked_bloom"]
        self._digest_algo = str(digest_algorithm if digest_algorithm is not None else hc["digest_algorithm"])
        self._digest_bytes = int(hc["digest_bytes"])
        self._word_bytes = int(hc["word_bytes"])
        self._bits_per_byte = int(hc["bits_per_byte"])
        self._poisson_tail_terms = int(bb["poisson_tail_terms"])
        self._poisson_lambda_cutoff = float(bb["poisson_lambda_cutoff"])
        self._round_digits = int(bb["round_digits"])

        self.num_blocks = max(1, int(num_blocks if num_blocks is not None else bb["num_blocks"]))
        self.block_bits = max(1, int(block_bits if block_bits is not None else bb["block_bits"]))
        self.num_hashes = max(1, int(num_hashes if num_hashes is not None else bb["num_hashes"]))
        self._blocks: list[int] = [0 for _ in range(self.num_blocks)]
        self.items_added = 0

    def _probe_coordinates(self, key: str | bytes) -> tuple[int, list[int]]:
        w0, w1, w2, _ = _digest_words(
            _to_bytes(key),
            algo=self._digest_algo,
            digest_bytes=self._digest_bytes,
            word_bytes=self._word_bytes,
        )
        block_idx = w0 % self.num_blocks
        h1 = w1 % self.block_bits
        # Odd non-zero step guarantees wide intra-block stride under Kirsch-Mitzenmacher
        h2 = ((w2 << 1) | 1) % self.block_bits
        if h2 == 0:
            h2 = 1
        bit_positions = [(h1 + i * h2) % self.block_bits for i in range(self.num_hashes)]
        return block_idx, bit_positions

    def add(self, key: str | bytes) -> None:
        """Insert key into its single cache-line block."""
        block_idx, bit_positions = self._probe_coordinates(key)
        mask = self._blocks[block_idx]
        for pos in bit_positions:
            mask |= 1 << pos
        self._blocks[block_idx] = mask
        self.items_added += 1

    def contains(self, key: str | bytes) -> bool:
        """One-sided membership test with exact 0% false-negative rate on inserted keys."""
        block_idx, bit_positions = self._probe_coordinates(key)
        block_val = self._blocks[block_idx]
        for pos in bit_positions:
            if (block_val & (1 << pos)) == 0:
                return False
        return True

    def __contains__(self, key: str | bytes) -> bool:
        return self.contains(key)

    def union(self, other: BlockedBloomFilter) -> BlockedBloomFilter:
        """Return bitwise union of two compatible BlockedBloomFilter instances."""
        if (
            self.num_blocks != other.num_blocks
            or self.block_bits != other.block_bits
            or self.num_hashes != other.num_hashes
            or self._digest_algo != other._digest_algo
        ):
            raise ValueError("BlockedBloomFilter parameters must match for bitwise union")
        combined = BlockedBloomFilter(
            num_blocks=self.num_blocks,
            block_bits=self.block_bits,
            num_hashes=self.num_hashes,
            digest_algorithm=self._digest_algo,
        )
        combined._blocks = [a | b for a, b in zip(self._blocks, other._blocks)]
        combined.items_added = self.items_added + other.items_added
        return combined

    def merge(self, other: BlockedBloomFilter) -> BlockedBloomFilter:
        """Alias for union() combining two compatible BlockedBloomFilter bitsets."""
        return self.union(other)

    def byte_size(self) -> int:
        total_bits = self.num_blocks * self.block_bits
        return (total_bits + self._bits_per_byte - 1) // self._bits_per_byte

    def theoretical_fpr(self, expected_items: int | None = None) -> float:
        """Poisson-weighted cache-line block false-positive probability estimate."""
        n = self.items_added if expected_items is None else max(0, int(expected_items))
        if n == 0:
            return 0.0
        lam = float(n) / float(self.num_blocks)
        m = float(self.block_bits)
        k = float(self.num_hashes)
        if lam > self._poisson_lambda_cutoff:
            return round((1.0 - math.exp(-k * lam / m)) ** k, self._round_digits)
        prob_weight = math.exp(-lam)
        fpr_sum = 0.0
        max_terms = max(self._poisson_tail_terms, int(lam + self._poisson_tail_terms))
        for c in range(0, max_terms):
            if c > 0:
                prob_weight *= lam / float(c)
                block_fpr = (1.0 - ((1.0 - 1.0 / m) ** (k * float(c)))) ** k
                fpr_sum += prob_weight * block_fpr
        return round(min(1.0, max(0.0, fpr_sum)), self._round_digits)

    def estimate_empirical_fpr(self, negative_keys: Iterable[str | bytes]) -> float:
        """Measure empirical false-positive rate over known-absent keys."""
        total = 0
        false_positives = 0
        for key in negative_keys:
            total += 1
            if self.contains(key):
                false_positives += 1
        if total == 0:
            return 0.0
        return round(float(false_positives) / float(total), self._round_digits)


class CuckooFilter:
    """Bucketized fingerprint table with partial-key cuckoo hashing and O(1) delete."""

    def __init__(
        self,
        *,
        capacity: int | None = None,
        bucket_power: int | None = None,
        bucket_size: int | None = None,
        fingerprint_bits: int | None = None,
        max_kicks: int | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        hc = cfg["hash_constants"]
        cf = cfg["cuckoo_filter"]
        self._digest_algo = str(hc["digest_algorithm"])
        self._digest_bytes = int(hc["digest_bytes"])
        self._word_bytes = int(hc["word_bytes"])
        self._bits_per_byte = int(hc["bits_per_byte"])
        self._header_field_bits = int(cf["header_field_bits"])
        self._min_bucket_power = int(cf["min_bucket_power"])
        self._target_load_factor = float(cf["target_load_factor"])

        self.bucket_size = max(1, int(bucket_size if bucket_size is not None else cf["bucket_size"]))
        self.fingerprint_bits = max(1, int(fingerprint_bits if fingerprint_bits is not None else cf["fingerprint_bits"]))
        self.max_kicks = max(1, int(max_kicks if max_kicks is not None else cf["max_kicks"]))

        if bucket_power is not None:
            power = max(self._min_bucket_power, int(bucket_power))
        elif capacity is not None and int(capacity) > 0:
            needed_slots = float(capacity) / self._target_load_factor
            needed_buckets = max(1, int(math.ceil(needed_slots / float(self.bucket_size))))
            power = self._min_bucket_power
            while (1 << power) < needed_buckets:
                power += 1
        else:
            power = max(self._min_bucket_power, int(cf["bucket_power"]))

        self.bucket_power = power
        self.num_buckets = 1 << self.bucket_power
        self._bucket_mask = self.num_buckets - 1
        self._fp_modulus = (1 << self.fingerprint_bits) - 1
        self._buckets: list[list[int]] = [[] for _ in range(self.num_buckets)]
        self.count = 0

    def _fingerprint_delta(self, fp: int) -> int:
        fp_bytes = int(fp).to_bytes(self._word_bytes, "little", signed=False)
        w0, _, _, _ = _digest_words(
            fp_bytes,
            algo=self._digest_algo,
            digest_bytes=self._digest_bytes,
            word_bytes=self._word_bytes,
        )
        # Odd step ensures i2 != i1 while preserving XOR involution: (i1 ^ d) ^ d == i1
        return ((w0 << 1) | 1) & self._bucket_mask

    def _index_and_fp(self, key: str | bytes) -> tuple[int, int, int]:
        w0, w1, _, _ = _digest_words(
            _to_bytes(key),
            algo=self._digest_algo,
            digest_bytes=self._digest_bytes,
            word_bytes=self._word_bytes,
        )
        fp = (w1 % self._fp_modulus) + 1
        i1 = w0 & self._bucket_mask
        i2 = (i1 ^ self._fingerprint_delta(fp)) & self._bucket_mask
        return fp, i1, i2

    def insert(self, key: str | bytes) -> bool:
        """Insert key fingerprint via partial-key cuckoo hashing."""
        fp, i1, i2 = self._index_and_fp(key)
        if len(self._buckets[i1]) < self.bucket_size:
            self._buckets[i1].append(fp)
            self.count += 1
            return True
        if len(self._buckets[i2]) < self.bucket_size:
            self._buckets[i2].append(fp)
            self.count += 1
            return True

        cur_idx = i1 if ((fp + self.count) & 1) == 0 else i2
        cur_fp = fp
        for kick in range(self.max_kicks):
            slot = (kick + cur_fp + cur_idx) % self.bucket_size
            evicted = self._buckets[cur_idx][slot]
            self._buckets[cur_idx][slot] = cur_fp
            cur_fp = evicted
            cur_idx = (cur_idx ^ self._fingerprint_delta(cur_fp)) & self._bucket_mask
            if len(self._buckets[cur_idx]) < self.bucket_size:
                self._buckets[cur_idx].append(cur_fp)
                self.count += 1
                return True
        return False

    def contains(self, key: str | bytes) -> bool:
        """Check whether key fingerprint resides in either candidate bucket."""
        fp, i1, i2 = self._index_and_fp(key)
        return (fp in self._buckets[i1]) or (fp in self._buckets[i2])

    def __contains__(self, key: str | bytes) -> bool:
        return self.contains(key)

    def delete(self, key: str | bytes) -> bool:
        """Delete one matching key fingerprint in O(1) bucket reads without rebuilding."""
        fp, i1, i2 = self._index_and_fp(key)
        if fp in self._buckets[i1]:
            self._buckets[i1].remove(fp)
            self.count -= 1
            return True
        if fp in self._buckets[i2]:
            self._buckets[i2].remove(fp)
            self.count -= 1
            return True
        return False

    def load_factor(self) -> float:
        total_slots = self.num_buckets * self.bucket_size
        return float(self.count) / float(total_slots)

    def to_bytes(self) -> bytes:
        """Bit-pack all bucket slots into a compact binary representation."""
        field_bytes = self._header_field_bits // self._bits_per_byte
        out = bytearray()
        for header_val in (self.bucket_power, self.bucket_size, self.fingerprint_bits, self.count):
            out.extend(int(header_val).to_bytes(field_bytes, "big"))

        buf = 0
        buf_bits = 0
        byte_mask = (1 << self._bits_per_byte) - 1
        for bucket in self._buckets:
            for slot_idx in range(self.bucket_size):
                fp = bucket[slot_idx] if slot_idx < len(bucket) else 0
                buf = (buf << self.fingerprint_bits) | fp
                buf_bits += self.fingerprint_bits
                while buf_bits >= self._bits_per_byte:
                    buf_bits -= self._bits_per_byte
                    out.append((buf >> buf_bits) & byte_mask)
                    buf &= (1 << buf_bits) - 1
        if buf_bits > 0:
            shift = self._bits_per_byte - buf_bits
            out.append((buf << shift) & byte_mask)
        return bytes(out)

    @classmethod
    def from_bytes(cls, raw: bytes, *, spec: dict[str, Any] | None = None) -> CuckooFilter:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        bits_per_byte = int(cfg["hash_constants"]["bits_per_byte"])
        field_bytes = int(cfg["cuckoo_filter"]["header_field_bits"]) // bits_per_byte
        p1 = field_bytes
        p2 = p1 + field_bytes
        p3 = p2 + field_bytes
        p4 = p3 + field_bytes
        bucket_power = int.from_bytes(raw[0:p1], "big")
        bucket_size = int.from_bytes(raw[p1:p2], "big")
        fingerprint_bits = int.from_bytes(raw[p2:p3], "big")
        stored_count = int.from_bytes(raw[p3:p4], "big")

        filt = cls(
            bucket_power=bucket_power,
            bucket_size=bucket_size,
            fingerprint_bits=fingerprint_bits,
            spec=cfg,
        )
        fp_mask = (1 << fingerprint_bits) - 1
        buf = 0
        buf_bits = 0
        cursor = p4
        reconstructed = 0
        for b_idx in range(filt.num_buckets):
            for _ in range(bucket_size):
                while buf_bits < fingerprint_bits and cursor < len(raw):
                    buf = (buf << bits_per_byte) | raw[cursor]
                    buf_bits += bits_per_byte
                    cursor += 1
                buf_bits -= fingerprint_bits
                fp = (buf >> buf_bits) & fp_mask
                buf &= (1 << buf_bits) - 1
                if fp != 0:
                    filt._buckets[b_idx].append(fp)
                    reconstructed += 1
        filt.count = stored_count if stored_count == reconstructed else reconstructed
        return filt

    def to_base64(self) -> str:
        return base64.b64encode(self.to_bytes()).decode("ascii")

    @classmethod
    def from_base64(cls, encoded: str, *, spec: dict[str, Any] | None = None) -> CuckooFilter:
        return cls.from_bytes(base64.b64decode(encoded.encode("ascii")), spec=spec)


class StaticXorFingerprintFilter:
    """Deterministic peeling-order 3-wise Xor fingerprint filter (~9-10 bits/key, 0% false negatives)."""

    def __init__(
        self,
        keys: Iterable[str | bytes],
        *,
        fingerprint_bits: int | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        hc = cfg["hash_constants"]
        xf = cfg["xor_filter"]
        self._digest_algo = str(hc["digest_algorithm"])
        self._digest_bytes = int(hc["digest_bytes"])
        self._word_bytes = int(hc["word_bytes"])
        self._round_digits = int(xf["round_digits"])

        self.fingerprint_bits = max(1, int(fingerprint_bits if fingerprint_bits is not None else xf["fingerprint_bits"]))
        self._fp_mask = (1 << self.fingerprint_bits) - 1
        num_segments = int(xf["num_segments"])
        size_multiplier = float(xf["size_multiplier"])
        segment_padding = int(xf["segment_padding"])
        min_seg = int(xf["min_segment_length"])
        base_seed = int(xf["base_seed"])
        max_retries = int(xf["max_seed_retries"])

        unique_keys = list(dict.fromkeys(_to_bytes(k) for k in keys))
        self.key_count = len(unique_keys)
        raw_total = int(math.floor(size_multiplier * float(self.key_count)))
        self.segment_length = max(min_seg, (raw_total // num_segments) + segment_padding)
        self.table_size = self.segment_length * num_segments
        self.seed = base_seed
        self.seed_attempts = 0
        self.table: list[int] = [0 for _ in range(self.table_size)]

        if self.key_count > 0:
            self._build_peeling_table(unique_keys, base_seed=base_seed, max_retries=max_retries)

    def _hashes_for_key(self, raw_key: bytes, seed: int) -> tuple[int, int, int, int]:
        w0, w1, w2, w3 = _digest_words(
            raw_key,
            algo=self._digest_algo,
            digest_bytes=self._digest_bytes,
            word_bytes=self._word_bytes,
            seed=seed,
        )
        seg = self.segment_length
        seg1 = seg
        seg2 = seg + seg
        h0 = w0 % seg
        h1 = seg1 + (w1 % seg)
        h2 = seg2 + (w2 % seg)
        fp = w3 & self._fp_mask
        return h0, h1, h2, fp

    def _build_peeling_table(self, unique_keys: list[bytes], *, base_seed: int, max_retries: int) -> None:
        n = len(unique_keys)
        m = self.table_size
        for attempt in range(max_retries):
            cur_seed = base_seed + attempt
            entries: list[tuple[int, int, int, int]] = []
            degree = [0 for _ in range(m)]
            xor_set = [0 for _ in range(m)]

            for k_idx, raw_key in enumerate(unique_keys):
                h0, h1, h2, fp = self._hashes_for_key(raw_key, cur_seed)
                entries.append((h0, h1, h2, fp))
                for vertex in (h0, h1, h2):
                    degree[vertex] += 1
                    xor_set[vertex] ^= k_idx

            queue: deque[int] = deque(v for v in range(m) if degree[v] == 1)
            peel_stack: list[tuple[int, int]] = []
            while queue:
                v = queue.popleft()
                if degree[v] != 1:
                    continue
                k_idx = xor_set[v]
                peel_stack.append((k_idx, v))
                h0, h1, h2, _ = entries[k_idx]
                for u in (h0, h1, h2):
                    xor_set[u] ^= k_idx
                    degree[u] -= 1
                    if degree[u] == 1:
                        queue.append(u)

            if len(peel_stack) == n:
                table = [0 for _ in range(m)]
                for k_idx, solo_vertex in reversed(peel_stack):
                    h0, h1, h2, fp = entries[k_idx]
                    table[solo_vertex] = fp ^ table[h0] ^ table[h1] ^ table[h2]
                self.seed = cur_seed
                self.seed_attempts = attempt + 1
                self.table = table
                return

        raise RuntimeError("StaticXorFingerprintFilter hypergraph peeling exceeded max_seed_retries")

    def contains(self, key: str | bytes) -> bool:
        """Query membership in 3 array reads via table[h0] ^ table[h1] ^ table[h2] == fp."""
        if self.key_count == 0:
            return False
        h0, h1, h2, fp = self._hashes_for_key(_to_bytes(key), self.seed)
        return (self.table[h0] ^ self.table[h1] ^ self.table[h2]) == fp

    def __contains__(self, key: str | bytes) -> bool:
        return self.contains(key)

    def bits_per_key(self) -> float:
        """Total fingerprint array bits divided by static key count."""
        if self.key_count == 0:
            return 0.0
        total_bits = self.table_size * self.fingerprint_bits
        return round(float(total_bits) / float(self.key_count), self._round_digits)
