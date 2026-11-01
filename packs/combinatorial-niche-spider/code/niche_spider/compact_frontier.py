"""Compact Cuckoo + HyperLogLog spider frontier tracker with O(1) 404 gone deletion."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable
import zlib

FRONTIER_GRID_PATH = Path(__file__).resolve().with_name("default_frontier_grid.json")


def load_frontier_grid_spec() -> dict[str, Any]:
    """Load declarative grid configuration for CompactSpiderFrontier."""
    return dict(json.loads(FRONTIER_GRID_PATH.read_text(encoding="utf-8")))


class CompactSpiderFrontier:
    """Mutable spider frontier sketch combining Cuckoo O(1) delete with HyperLogLog cardinality."""

    def __init__(
        self,
        *,
        capacity: int | None = None,
        bucket_power: int | None = None,
        bucket_size: int | None = None,
        fingerprint_bits: int | None = None,
        hll_precision: int | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_frontier_grid_spec())
        hc = cfg["hash_constants"]
        cf = cfg["cuckoo"]
        hl = cfg["hll"]

        self._digest_bytes = int(hc["digest_bytes"])
        self._word_bytes = int(hc["word_bytes"])
        self._bits_per_byte = int(hc["bits_per_byte"])
        self._hash64_bits = int(hc["hash64_bits"])
        self._header_field_bits = int(cf["header_field_bits"])
        self._zlib_level = int(cf["zlib_level"])

        self.bucket_size = max(1, int(bucket_size if bucket_size is not None else cf["bucket_size"]))
        self.fingerprint_bits = max(1, int(fingerprint_bits if fingerprint_bits is not None else cf["fingerprint_bits"]))
        self.max_kicks = max(1, int(cf["max_kicks"]))
        min_power = int(cf["min_bucket_power"])
        load_target = float(cf["target_load_factor"])

        if bucket_power is not None:
            power = max(min_power, int(bucket_power))
        elif capacity is not None and int(capacity) > 0:
            needed_slots = float(capacity) / load_target
            needed_buckets = max(1, int(math.ceil(needed_slots / float(self.bucket_size))))
            power = min_power
            while (1 << power) < needed_buckets:
                power += 1
        else:
            power = max(min_power, int(cf["default_bucket_power"]))

        self.bucket_power = power
        self.num_buckets = 1 << self.bucket_power
        self._bucket_mask = self.num_buckets - 1
        self._fp_modulus = (1 << self.fingerprint_bits) - 1
        self._buckets: list[list[int]] = [[] for _ in range(self.num_buckets)]
        self.count = 0

        self.hll_precision = max(1, int(hll_precision if hll_precision is not None else hl["precision"]))
        self.hll_num_registers = 1 << self.hll_precision
        self._hll_reg_mask = self.hll_num_registers - 1
        self._hll_registers: list[int] = [0 for _ in range(self.hll_num_registers)]
        self._hll_updates = 0
        self._alpha_16 = float(hl["alpha_16"])
        self._alpha_32 = float(hl["alpha_32"])
        self._alpha_64 = float(hl["alpha_64"])
        self._alpha_inf_numer = float(hl["alpha_inf_numer"])
        self._alpha_inf_denom = float(hl["alpha_inf_denom"])
        self._linear_factor = float(hl["linear_counting_factor"])
        self._small_16 = int(hl["small_16"])
        self._small_32 = int(hl["small_32"])
        self._small_64 = int(hl["small_64"])
        self._round_digits = int(hl["round_digits"])

    def _words(self, raw: bytes) -> tuple[int, int, int]:
        digest = hashlib.blake2b(raw, digest_size=self._digest_bytes).digest()
        wb = self._word_bytes
        p1 = wb
        p2 = p1 + wb
        p3 = p2 + wb
        w0 = int.from_bytes(digest[0:p1], "little")
        w1 = int.from_bytes(digest[p1:p2], "little")
        w2 = int.from_bytes(digest[p2:p3], "little")
        return w0, w1, w2

    def _fp_delta(self, fp: int) -> int:
        fp_bytes = int(fp).to_bytes(self._word_bytes, "little", signed=False)
        w0, _, _ = self._words(fp_bytes)
        return ((w0 << 1) | 1) & self._bucket_mask

    def _coords(self, target: str) -> tuple[int, int, int, int]:
        w0, w1, w2 = self._words(str(target).encode("utf-8"))
        fp = (w1 % self._fp_modulus) + 1
        i1 = w0 & self._bucket_mask
        i2 = (i1 ^ self._fp_delta(fp)) & self._bucket_mask
        return fp, i1, i2, w2

    def _observe_hll(self, h64: int) -> None:
        self._hll_updates += 1
        reg_idx = h64 & self._hll_reg_mask
        w_bits = h64 >> self.hll_precision
        rem_bits = self._hash64_bits - self.hll_precision
        rho = (rem_bits + 1) if w_bits == 0 else (rem_bits - w_bits.bit_length() + 1)
        if rho > self._hll_registers[reg_idx]:
            self._hll_registers[reg_idx] = rho

    def insert(self, target: str) -> bool:
        """Insert target fingerprint into Cuckoo table (preserving multiset delete safety) and update HLL."""
        fp, i1, i2, h64 = self._coords(target)
        self._observe_hll(h64)
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
            cur_idx = (cur_idx ^ self._fp_delta(cur_fp)) & self._bucket_mask
            if len(self._buckets[cur_idx]) < self.bucket_size:
                self._buckets[cur_idx].append(cur_fp)
                self.count += 1
                return True
        return False

    def contains(self, target: str) -> bool:
        """Check whether target is currently active in the Cuckoo frontier."""
        fp, i1, i2, _ = self._coords(target)
        return (fp in self._buckets[i1]) or (fp in self._buckets[i2])

    def __contains__(self, target: str) -> bool:
        return self.contains(target)

    def delete(self, target: str) -> bool:
        """Delete exact target fingerprint in O(1)."""
        fp, i1, i2, _ = self._coords(target)
        if fp in self._buckets[i1]:
            self._buckets[i1].remove(fp)
            self.count -= 1
            return True
        if fp in self._buckets[i2]:
            self._buckets[i2].remove(fp)
            self.count -= 1
            return True
        return False

    def remove_gone(self, target: str) -> bool:
        """Prune a 404 gone target (handling bare org/repo or prefixed repo:org/repo) in O(1)."""
        clean = str(target)
        removed = self.delete(clean)
        if not removed and ":" not in clean:
            removed = self.delete(f"repo:{clean}")
        return removed

    def _alpha(self) -> float:
        m = self.hll_num_registers
        if m <= self._small_16:
            return self._alpha_16
        if m <= self._small_32:
            return self._alpha_32
        if m <= self._small_64:
            return self._alpha_64
        return self._alpha_inf_numer / (1.0 + self._alpha_inf_denom / float(m))

    def estimate_cardinality(self) -> float:
        """Return HyperLogLog distinct target cardinality observed across spider waves."""
        if self._hll_updates == 0:
            return 0.0
        m = float(self.hll_num_registers)
        inv_sum = sum(1.0 / float(1 << reg) for reg in self._hll_registers)
        raw_est = self._alpha() * m * m / inv_sum
        zeros = sum(1 for reg in self._hll_registers if reg == 0)
        if raw_est <= self._linear_factor * m and zeros > 0:
            return round(m * math.log(m / float(zeros)), self._round_digits)
        return round(raw_est, self._round_digits)

    def raw_bitpacked_bytes(self) -> bytes:
        """Uncompressed bit-packed Cuckoo slots + HLL register array."""
        field_bytes = self._header_field_bits // self._bits_per_byte
        out = bytearray()
        for val in (
            self.bucket_power,
            self.bucket_size,
            self.fingerprint_bits,
            self.count,
            self.hll_precision,
            self._hll_updates,
        ):
            out.extend(int(val).to_bytes(field_bytes, "big"))
        out.extend(bytes(self._hll_registers))

        buf = 0
        buf_bits = 0
        byte_mask = (1 << self._bits_per_byte) - 1
        for bucket in self._buckets:
            for s_idx in range(self.bucket_size):
                fp = bucket[s_idx] if s_idx < len(bucket) else 0
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

    def to_bytes(self) -> bytes:
        """Deflate-packed binary representation of Cuckoo + HLL frontier state."""
        return zlib.compress(self.raw_bitpacked_bytes(), level=self._zlib_level)

    @classmethod
    def from_bytes(cls, packed: bytes, *, spec: dict[str, Any] | None = None) -> CompactSpiderFrontier:
        cfg = copy.deepcopy(spec if spec is not None else load_frontier_grid_spec())
        raw = zlib.decompress(packed)
        bits_per_byte = int(cfg["hash_constants"]["bits_per_byte"])
        field_bytes = int(cfg["cuckoo"]["header_field_bits"]) // bits_per_byte

        p1 = field_bytes
        p2 = p1 + field_bytes
        p3 = p2 + field_bytes
        p4 = p3 + field_bytes
        p5 = p4 + field_bytes
        p6 = p5 + field_bytes

        bucket_power = int.from_bytes(raw[0:p1], "big")
        bucket_size = int.from_bytes(raw[p1:p2], "big")
        fingerprint_bits = int.from_bytes(raw[p2:p3], "big")
        stored_count = int.from_bytes(raw[p3:p4], "big")
        hll_precision = int.from_bytes(raw[p4:p5], "big")
        hll_updates = int.from_bytes(raw[p5:p6], "big")

        frontier = cls(
            bucket_power=bucket_power,
            bucket_size=bucket_size,
            fingerprint_bits=fingerprint_bits,
            hll_precision=hll_precision,
            spec=cfg,
        )
        hll_end = p6 + frontier.hll_num_registers
        frontier._hll_registers = list(raw[p6:hll_end])
        frontier._hll_updates = hll_updates

        fp_mask = (1 << fingerprint_bits) - 1
        buf = 0
        buf_bits = 0
        cursor = hll_end
        reconstructed = 0
        for b_idx in range(frontier.num_buckets):
            for _ in range(bucket_size):
                while buf_bits < fingerprint_bits and cursor < len(raw):
                    buf = (buf << bits_per_byte) | raw[cursor]
                    buf_bits += bits_per_byte
                    cursor += 1
                buf_bits -= fingerprint_bits
                fp = (buf >> buf_bits) & fp_mask
                buf &= (1 << buf_bits) - 1
                if fp != 0:
                    frontier._buckets[b_idx].append(fp)
                    reconstructed += 1
        frontier.count = stored_count if stored_count == reconstructed else reconstructed
        return frontier

    def to_hex(self) -> str:
        return self.to_bytes().hex()

    @classmethod
    def from_hex(cls, hex_str: str, *, spec: dict[str, Any] | None = None) -> CompactSpiderFrontier:
        return cls.from_bytes(bytes.fromhex(hex_str.strip()), spec=spec)

    def to_base64(self) -> str:
        return base64.b64encode(self.to_bytes()).decode("ascii")

    @classmethod
    def from_base64(cls, b64_str: str, *, spec: dict[str, Any] | None = None) -> CompactSpiderFrontier:
        return cls.from_bytes(base64.b64decode(b64_str.encode("ascii")), spec=spec)


def compress_frontier_sketch(
    targets: Iterable[str],
    *,
    gone_targets: Iterable[str] = (),
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compress a spider target list into a Cuckoo+HLL sketch and report byte reduction ratios."""
    cfg = copy.deepcopy(spec if spec is not None else load_frontier_grid_spec())
    round_digits = int(cfg["metrics"]["ratio_round_digits"])
    target_list = [str(t) for t in targets]
    raw_json_bytes = len(json.dumps(target_list, separators=(",", ":")).encode("utf-8"))

    frontier = CompactSpiderFrontier(capacity=max(1, len(target_list)), spec=cfg)
    for t in target_list:
        frontier.insert(t)
    pruned = 0
    for g in gone_targets:
        if frontier.remove_gone(str(g)):
            pruned += 1

    packed_bytes = frontier.to_bytes()
    b64_str = base64.b64encode(packed_bytes).decode("ascii")
    raw_bitpacked_len = len(frontier.raw_bitpacked_bytes())
    packed_len = max(1, len(packed_bytes))
    b64_len = max(1, len(b64_str))

    return {
        "item_count": len(target_list),
        "pruned_gone_count": pruned,
        "active_count": frontier.count,
        "raw_json_bytes": raw_json_bytes,
        "raw_bitpacked_bytes": raw_bitpacked_len,
        "packed_bytes": len(packed_bytes),
        "base64_bytes": len(b64_str),
        "byte_reduction_ratio": round(float(raw_json_bytes) / float(packed_len), round_digits),
        "base64_reduction_ratio": round(float(raw_json_bytes) / float(b64_len), round_digits),
        "estimated_cardinality": frontier.estimate_cardinality(),
        "sketch_base64": b64_str,
        "sketch_hex": packed_bytes.hex(),
    }
