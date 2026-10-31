"""Conservative-update Count-Min Sketch, HeavyKeeper top-K tracker and HyperLogLog cardinality estimator."""

from __future__ import annotations

import copy
import math
from typing import Any

from .filters import _digest_words, _to_bytes, load_default_grid_spec


class ConservativeCountMinHeavyKeeperHll:
    """Streaming frequency, top-K elephant flow, and HyperLogLog distinct-cardinality sketch."""

    def __init__(
        self,
        *,
        cms_depth: int | None = None,
        cms_width: int | None = None,
        hk_depth: int | None = None,
        hk_width: int | None = None,
        hk_top_k: int | None = None,
        hll_precision: int | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        hc = cfg["hash_constants"]
        sk = cfg["streaming_sketch"]

        self._digest_algo = str(hc["digest_algorithm"])
        self._digest_bytes = int(hc["digest_bytes"])
        self._word_bytes = int(hc["word_bytes"])
        self._hash64_bits = int(hc["hash64_bits"])

        self.cms_depth = max(1, int(cms_depth if cms_depth is not None else sk["cms_depth"]))
        self.cms_width = max(1, int(cms_width if cms_width is not None else sk["cms_width"]))
        self.hk_depth = max(1, int(hk_depth if hk_depth is not None else sk["hk_depth"]))
        self.hk_width = max(1, int(hk_width if hk_width is not None else sk["hk_width"]))
        self.hk_top_k = max(1, int(hk_top_k if hk_top_k is not None else sk["hk_top_k"]))
        self.hk_decay_base = float(sk["hk_decay_base"])
        self._hk_fp_mask = (1 << int(sk["hk_fingerprint_bits"])) - 1
        self._coin_bits = int(sk["coin_resolution_bits"])
        self._coin_scale = float(1 << self._coin_bits)

        self.hll_precision = max(1, int(hll_precision if hll_precision is not None else sk["hll_precision"]))
        self.hll_num_registers = 1 << self.hll_precision
        self._hll_reg_mask = self.hll_num_registers - 1
        self._hll_alpha_16 = float(sk["hll_alpha_16"])
        self._hll_alpha_32 = float(sk["hll_alpha_32"])
        self._hll_alpha_64 = float(sk["hll_alpha_64"])
        self._hll_alpha_inf_numer = float(sk["hll_alpha_inf_numer"])
        self._hll_alpha_inf_denom = float(sk["hll_alpha_inf_denom"])
        self._hll_linear_factor = float(sk["hll_linear_counting_factor"])
        self._hll_small_16 = int(sk["hll_small_registers_16"])
        self._hll_small_32 = int(sk["hll_small_registers_32"])
        self._hll_small_64 = int(sk["hll_small_registers_64"])
        self._round_digits = int(sk["round_digits"])

        self._cms_table: list[list[int]] = [
            [0 for _ in range(self.cms_width)] for _ in range(self.cms_depth)
        ]
        # Each HeavyKeeper bucket stores [fingerprint, estimated_count]
        self._hk_buckets: list[list[tuple[int, int]]] = [
            [(0, 0) for _ in range(self.hk_width)] for _ in range(self.hk_depth)
        ]
        self._top_k_map: dict[str, int] = {}
        self._hll_registers: list[int] = [0 for _ in range(self.hll_num_registers)]
        self.total_updates = 0

    def _row_hash(self, raw: bytes, row: int) -> tuple[int, int]:
        w0, w1, _, _ = _digest_words(
            raw,
            algo=self._digest_algo,
            digest_bytes=self._digest_bytes,
            word_bytes=self._word_bytes,
            seed=row + 1,
        )
        return w0, w1

    def observe(self, key: str, count: int = 1) -> None:
        """Update Conservative Count-Min, HeavyKeeper top-K and HyperLogLog registers."""
        steps = max(1, int(count))
        raw = _to_bytes(key)

        # 1. Conservative-update Count-Min Sketch (never underestimates, minimizes overestimation)
        cms_cols = [self._row_hash(raw, r)[0] % self.cms_width for r in range(self.cms_depth)]
        cur_min = min(self._cms_table[r][cms_cols[r]] for r in range(self.cms_depth))
        target = cur_min + steps
        for r in range(self.cms_depth):
            col = cms_cols[r]
            if self._cms_table[r][col] < target:
                self._cms_table[r][col] = target

        # 2. HeavyKeeper exponential-decay elephant tracker
        for _ in range(steps):
            self.total_updates += 1
            max_matched = 0
            for r in range(self.hk_depth):
                w0, w1 = self._row_hash(raw, self.cms_depth + r)
                b_idx = w0 % self.hk_width
                fp = (w1 & self._hk_fp_mask) or 1
                cur_fp, cur_cnt = self._hk_buckets[r][b_idx]
                if cur_cnt == 0:
                    new_cnt = 1
                    self._hk_buckets[r][b_idx] = (fp, new_cnt)
                    max_matched = max(max_matched, new_cnt)
                elif cur_fp == fp:
                    new_cnt = cur_cnt + 1
                    self._hk_buckets[r][b_idx] = (fp, new_cnt)
                    max_matched = max(max_matched, new_cnt)
                else:
                    decay_prob = self.hk_decay_base ** (-float(cur_cnt))
                    coin_w, _, _, _ = _digest_words(
                        raw,
                        algo=self._digest_algo,
                        digest_bytes=self._digest_bytes,
                        word_bytes=self._word_bytes,
                        seed=self.total_updates + r,
                    )
                    uniform_u = float(coin_w & ((1 << self._coin_bits) - 1)) / self._coin_scale
                    if uniform_u < decay_prob:
                        decayed = cur_cnt - 1
                        if decayed <= 0:
                            self._hk_buckets[r][b_idx] = (fp, 1)
                            max_matched = max(max_matched, 1)
                        else:
                            self._hk_buckets[r][b_idx] = (cur_fp, decayed)

            if max_matched > 0:
                if key in self._top_k_map:
                    self._top_k_map[key] = max(self._top_k_map[key], max_matched)
                elif len(self._top_k_map) < self.hk_top_k:
                    self._top_k_map[key] = max_matched
                else:
                    smallest_key = min(self._top_k_map, key=lambda k: (self._top_k_map[k], k))
                    if max_matched > self._top_k_map[smallest_key]:
                        del self._top_k_map[smallest_key]
                        self._top_k_map[key] = max_matched

        # 3. HyperLogLog register update
        h64, _, _, _ = _digest_words(
            raw,
            algo=self._digest_algo,
            digest_bytes=self._digest_bytes,
            word_bytes=self._word_bytes,
            seed=0,
        )
        reg_idx = h64 & self._hll_reg_mask
        w_bits = h64 >> self.hll_precision
        rem_bits = self._hash64_bits - self.hll_precision
        if w_bits == 0:
            rho = rem_bits + 1
        else:
            leading_zeros = rem_bits - w_bits.bit_length()
            rho = leading_zeros + 1
        if rho > self._hll_registers[reg_idx]:
            self._hll_registers[reg_idx] = rho

    def estimate_frequency(self, key: str) -> int:
        """Point query frequency estimate from Conservative-Update Count-Min Sketch."""
        raw = _to_bytes(key)
        return min(
            self._cms_table[r][self._row_hash(raw, r)[0] % self.cms_width]
            for r in range(self.cms_depth)
        )

    def top_k(self) -> list[dict[str, Any]]:
        """Return HeavyKeeper tracked top-K heavy hitters ordered by estimated count."""
        ordered = sorted(self._top_k_map.items(), key=lambda kv: (-kv[1], kv[0]))
        return [{"key": k, "estimated_count": c} for k, c in ordered[: self.hk_top_k]]

    def _hll_alpha(self) -> float:
        m = self.hll_num_registers
        if m <= self._hll_small_16:
            return self._hll_alpha_16
        if m <= self._hll_small_32:
            return self._hll_alpha_32
        if m <= self._hll_small_64:
            return self._hll_alpha_64
        return self._hll_alpha_inf_numer / (1.0 + self._hll_alpha_inf_denom / float(m))

    def estimate_cardinality(self) -> float:
        """HyperLogLog harmonic-mean cardinality estimate with small-range linear counting."""
        if self.total_updates == 0:
            return 0.0
        m = float(self.hll_num_registers)
        inv_sum = sum(1.0 / float(1 << reg) for reg in self._hll_registers)
        raw_est = self._hll_alpha() * m * m / inv_sum
        zero_regs = sum(1 for reg in self._hll_registers if reg == 0)
        if raw_est <= self._hll_linear_factor * m and zero_regs > 0:
            linear_est = m * math.log(m / float(zero_regs))
            return round(linear_est, self._round_digits)
        return round(raw_est, self._round_digits)
