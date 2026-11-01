"""DynamicByteEntropyPatcher computing rolling conditional byte Shannon entropy and variable patches."""

from __future__ import annotations

import copy
import hashlib
import math
from typing import Any

from .grid import resolve_grid_cell


def _to_bytes(data: bytes | str) -> bytes:
    if isinstance(data, bytes):
        return data
    return data.encode("utf-8")


class DynamicByteEntropyPatcher:
    """Segments byte streams into variable-length patches at conditional Shannon entropy spikes."""

    def __init__(
        self,
        overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.grid, self.cell, self.constants = resolve_grid_cell(overrides, regime=regime, spec=spec)
        self.global_threshold = float(self.cell["global_entropy_threshold"])
        self.delta_spike_threshold = float(self.cell["delta_spike_threshold"])
        self.min_patch_bytes = int(self.cell["min_patch_bytes"])
        self.max_patch_bytes = int(self.cell["max_patch_bytes"])
        self.context_order = int(self.cell["context_order"])
        self.alphabet_size = int(self.constants["byte_alphabet_size"])
        self.prior_concentration = float(self.cell["prior_concentration"])
        self.alpha = self.prior_concentration / float(self.alphabet_size)
        self.log_base_two = float(self.constants["log_base_two"])
        self.min_ctx_obs = int(self.constants["min_context_observations"])
        self.round_digits = int(self.constants["round_digits"])

        # Order -> context_bytes -> {next_byte: count}
        self._counts: dict[int, dict[bytes, dict[int, int]]] = {
            order: {} for order in range(self.context_order + 1)
        }
        self._totals: dict[int, dict[bytes, int]] = {
            order: {} for order in range(self.context_order + 1)
        }

    def fit_corpus(self, samples: list[bytes | str]) -> None:
        """Fit variable-order byte n-gram counts from calibration byte sequences."""
        for sample in samples:
            raw = _to_bytes(sample)
            for pos, byte_val in enumerate(raw):
                self._observe(raw, pos, byte_val, self._counts, self._totals)

    def _observe(
        self,
        stream: bytes,
        pos: int,
        byte_val: int,
        counts_map: dict[int, dict[bytes, dict[int, int]]],
        totals_map: dict[int, dict[bytes, int]],
    ) -> None:
        max_ord = min(self.context_order, pos)
        for order in range(max_ord + 1):
            ctx = stream[pos - order : pos] if order > 0 else b""
            ctx_dict = counts_map[order].setdefault(ctx, {})
            ctx_dict[byte_val] = ctx_dict.get(byte_val, 0) + 1
            totals_map[order][ctx] = totals_map[order].get(ctx, 0) + 1

    def _predictive_entropy_and_surprise(
        self,
        stream: bytes,
        pos: int,
        byte_val: int,
        counts_map: dict[int, dict[bytes, dict[int, int]]],
        totals_map: dict[int, dict[bytes, int]],
    ) -> tuple[float, float]:
        selected_counts: dict[int, int] = {}
        selected_total = 0
        max_ord = min(self.context_order, pos)
        for order in range(max_ord, -1, -1):
            ctx = stream[pos - order : pos] if order > 0 else b""
            tot = totals_map[order].get(ctx, 0)
            if tot >= self.min_ctx_obs or (order == 0 and tot > 0):
                selected_counts = counts_map[order].get(ctx, {})
                selected_total = tot
                break

        denom = float(selected_total) + float(self.alphabet_size) * self.alpha
        entropy = 0.0
        for count in selected_counts.values():
            prob = (float(count) + self.alpha) / denom
            entropy -= prob * math.log(prob, self.log_base_two)

        unseen_symbols = self.alphabet_size - len(selected_counts)
        if unseen_symbols > 0:
            p_unseen = self.alpha / denom
            entropy -= float(unseen_symbols) * p_unseen * math.log(p_unseen, self.log_base_two)

        obs_prob = (float(selected_counts.get(byte_val, 0)) + self.alpha) / denom
        surprise = -math.log(obs_prob, self.log_base_two)
        return entropy, surprise

    def segment_stream(
        self,
        data: bytes | str,
        *,
        online_update: bool = True,
    ) -> dict[str, Any]:
        """Segment a byte stream into lossless variable-length patches driven by conditional entropy."""
        raw = _to_bytes(data)
        if not raw:
            return {
                "patches": [],
                "patch_count": 0,
                "total_bytes": 0,
                "reconstructed_exact": True,
                "stream_sha256": hashlib.sha256(b"").hexdigest(),
                "mean_patch_bytes": 0.0,
                "grid_cell_id": self.grid.cell_id(self.cell),
            }

        counts_work = copy.deepcopy(self._counts) if online_update else self._counts
        totals_work = copy.deepcopy(self._totals) if online_update else self._totals

        entropies: list[float] = []
        surprises: list[float] = []
        for pos, byte_val in enumerate(raw):
            h_t, s_t = self._predictive_entropy_and_surprise(
                raw, pos, byte_val, counts_work, totals_work
            )
            entropies.append(h_t)
            surprises.append(s_t)
            if online_update:
                self._observe(raw, pos, byte_val, counts_work, totals_work)

        patches: list[dict[str, Any]] = []
        patch_start = 0
        boundary_reason = "stream_start"

        for pos in range(1, len(raw)):
            cur_len = pos - patch_start
            h_now = entropies[pos]
            h_prev = entropies[pos - 1]
            delta_h = h_now - h_prev

            cut_reason: str | None = None
            if cur_len >= self.max_patch_bytes:
                cut_reason = "max_patch_ceiling"
            elif cur_len >= self.min_patch_bytes:
                if delta_h > self.delta_spike_threshold:
                    cut_reason = "entropy_delta_spike"
                elif h_now > self.global_threshold:
                    cut_reason = "global_entropy_exceeded"
                elif h_prev > self.global_threshold and (h_prev - h_now) > self.delta_spike_threshold:
                    cut_reason = "entropy_regime_resync"

            if cut_reason is not None:
                patches.append(
                    self._build_patch(
                        len(patches),
                        raw,
                        patch_start,
                        pos,
                        entropies,
                        surprises,
                        boundary_reason,
                    )
                )
                patch_start = pos
                boundary_reason = cut_reason

        patches.append(
            self._build_patch(
                len(patches),
                raw,
                patch_start,
                len(raw),
                entropies,
                surprises,
                boundary_reason,
            )
        )

        reconstructed = b"".join(bytes.fromhex(p["hex_bytes"]) for p in patches)
        return {
            "patches": patches,
            "patch_count": len(patches),
            "total_bytes": len(raw),
            "reconstructed_exact": reconstructed == raw,
            "stream_sha256": hashlib.sha256(raw).hexdigest(),
            "mean_patch_bytes": round(len(raw) / len(patches), self.round_digits),
            "grid_cell_id": self.grid.cell_id(self.cell),
        }

    def _build_patch(
        self,
        index: int,
        raw: bytes,
        start: int,
        end: int,
        entropies: list[float],
        surprises: list[float],
        reason: str,
    ) -> dict[str, Any]:
        chunk = raw[start:end]
        h_slice = entropies[start:end]
        s_slice = surprises[start:end]
        mean_h = sum(h_slice) / len(h_slice)
        max_h = max(h_slice)
        cum_s = sum(s_slice)
        return {
            "index": index,
            "start_byte": start,
            "end_byte": end,
            "byte_length": len(chunk),
            "hex_bytes": chunk.hex(),
            "utf8_preview": chunk.decode("utf-8", errors="replace"),
            "mean_entropy_bits": round(mean_h, self.round_digits),
            "max_entropy_bits": round(max_h, self.round_digits),
            "cumulative_surprise_bits": round(cum_s, self.round_digits),
            "boundary_reason": reason,
        }
