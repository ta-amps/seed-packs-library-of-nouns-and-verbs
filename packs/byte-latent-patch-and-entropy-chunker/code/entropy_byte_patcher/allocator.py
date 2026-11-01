"""SurpriseProportionalBudgetAllocator and corruption/shift robustness benchmark vs fixed-stride chunking."""

from __future__ import annotations

from typing import Any

from .grid import resolve_grid_cell
from .patcher import DynamicByteEntropyPatcher, _to_bytes


class SurpriseProportionalBudgetAllocator:
    """Allocates downstream compute/context slots across patches proportional to cumulative surprise."""

    def __init__(
        self,
        overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.grid, self.cell, self.constants = resolve_grid_cell(overrides, regime=regime, spec=spec)
        self.default_budget = int(self.cell["total_inspection_budget"])
        self.min_slots = int(self.cell["min_slots_per_patch"])
        self.fixed_stride = int(self.constants["fixed_stride_bytes"])
        self.round_digits = int(self.constants["round_digits"])

    def _apportion(self, weights: list[float], total_slots: int, floor_slots: int) -> list[int]:
        count = len(weights)
        if count == 0 or total_slots <= 0:
            return [0] * count

        effective_floor = floor_slots if count * floor_slots <= total_slots else 0
        allocations = [effective_floor] * count
        remaining = total_slots - sum(allocations)
        if remaining <= 0:
            return allocations

        weight_sum = sum(max(0.0, w) for w in weights)
        if weight_sum <= 0.0:
            base = remaining // count
            rem = remaining % count
            for idx in range(count):
                allocations[idx] += base + (1 if idx < rem else 0)
            return allocations

        quotas = [(max(0.0, w) / weight_sum) * float(remaining) for w in weights]
        floors = [int(q) for q in quotas]
        for idx, fl in enumerate(floors):
            allocations[idx] += fl

        leftover = remaining - sum(floors)
        ranked = sorted(
            range(count),
            key=lambda idx: (quotas[idx] - float(floors[idx]), weights[idx], -idx),
            reverse=True,
        )
        for idx in ranked[:leftover]:
            allocations[idx] += 1
        return allocations

    def allocate_budget(
        self,
        patches: list[dict[str, Any]],
        *,
        total_budget: int | None = None,
    ) -> dict[str, Any]:
        """Compare surprise-proportional slot allocation against naive byte-length allocation."""
        budget = self.default_budget if total_budget is None else max(0, int(total_budget))
        if not patches:
            return {
                "total_budget": budget,
                "allocations": [],
                "surprise_density_per_byte_corr_gain": 0.0,
                "high_entropy_surprise_budget_share": 0.0,
                "high_entropy_byte_budget_share": 0.0,
                "high_entropy_focus_gain": 0.0,
            }

        surprise_weights = [float(p["cumulative_surprise_bits"]) for p in patches]
        byte_weights = [float(p["byte_length"]) for p in patches]

        surprise_slots = self._apportion(surprise_weights, budget, self.min_slots)
        byte_slots = self._apportion(byte_weights, budget, self.min_slots)

        mean_entropy_across_patches = sum(
            float(p["mean_entropy_bits"]) for p in patches
        ) / len(patches)
        high_indices = [
            idx
            for idx, p in enumerate(patches)
            if float(p["mean_entropy_bits"]) > mean_entropy_across_patches
        ]

        surprise_high_share = (
            round(sum(surprise_slots[idx] for idx in high_indices) / budget, self.round_digits)
            if budget > 0 and high_indices
            else 0.0
        )
        byte_high_share = (
            round(sum(byte_slots[idx] for idx in high_indices) / budget, self.round_digits)
            if budget > 0 and high_indices
            else 0.0
        )

        enriched: list[dict[str, Any]] = []
        for idx, patch in enumerate(patches):
            enriched.append(
                {
                    "index": int(patch["index"]),
                    "byte_length": int(patch["byte_length"]),
                    "mean_entropy_bits": float(patch["mean_entropy_bits"]),
                    "cumulative_surprise_bits": float(patch["cumulative_surprise_bits"]),
                    "surprise_slots": surprise_slots[idx],
                    "byte_length_slots": byte_slots[idx],
                }
            )

        return {
            "total_budget": budget,
            "allocations": enriched,
            "high_entropy_surprise_budget_share": surprise_high_share,
            "high_entropy_byte_budget_share": byte_high_share,
            "high_entropy_focus_gain": round(
                surprise_high_share - byte_high_share, self.round_digits
            ),
        }

    def fixed_stride_chunks(self, data: bytes | str, stride: int | None = None) -> list[bytes]:
        """Split a byte stream into rigid fixed-stride chunks."""
        raw = _to_bytes(data)
        step = self.fixed_stride if stride is None else max(1, int(stride))
        return [raw[pos : pos + step] for pos in range(0, len(raw), step)]

    def benchmark_corruption_robustness(
        self,
        clean_stream: bytes | str,
        corrupted_stream: bytes | str,
        *,
        calibration_corpus: list[bytes | str] | None = None,
        online_update: bool = False,
    ) -> dict[str, Any]:
        """Measure downstream patch recovery after prefix/mid-stream byte insertions or noise vs fixed stride."""
        patcher = DynamicByteEntropyPatcher(
            regime=None, spec=self.grid.spec, overrides=self.cell
        )
        if calibration_corpus:
            patcher.fit_corpus(calibration_corpus)

        clean_seg = patcher.segment_stream(clean_stream, online_update=online_update)
        corrupt_seg = patcher.segment_stream(corrupted_stream, online_update=online_update)

        dyn_clean_multiset = [bytes.fromhex(p["hex_bytes"]) for p in clean_seg["patches"]]
        dyn_corrupt_pool = [bytes.fromhex(p["hex_bytes"]) for p in corrupt_seg["patches"]]
        dyn_matches = self._multiset_overlap_count(dyn_clean_multiset, dyn_corrupt_pool)
        dyn_recovery = (
            round(dyn_matches / len(dyn_clean_multiset), self.round_digits)
            if dyn_clean_multiset
            else 1.0
        )

        fixed_clean = self.fixed_stride_chunks(clean_stream)
        fixed_corrupt = self.fixed_stride_chunks(corrupted_stream)
        fixed_matches = self._multiset_overlap_count(fixed_clean, fixed_corrupt)
        fixed_recovery = (
            round(fixed_matches / len(fixed_clean), self.round_digits) if fixed_clean else 1.0
        )

        return {
            "clean_reconstructed_exact": bool(clean_seg["reconstructed_exact"]),
            "corrupted_reconstructed_exact": bool(corrupt_seg["reconstructed_exact"]),
            "dynamic_clean_patch_count": int(clean_seg["patch_count"]),
            "dynamic_preserved_patch_fraction": dyn_recovery,
            "fixed_stride_bytes": self.fixed_stride,
            "fixed_stride_preserved_chunk_fraction": fixed_recovery,
            "boundary_resync_gain": round(dyn_recovery - fixed_recovery, self.round_digits),
        }

    @staticmethod
    def _multiset_overlap_count(reference: list[bytes], candidate: list[bytes]) -> int:
        counts: dict[bytes, int] = {}
        for item in candidate:
            counts[item] = counts.get(item, 0) + 1
        matched = 0
        for item in reference:
            avail = counts.get(item, 0)
            if avail > 0:
                matched += 1
                counts[item] = avail - 1
        return matched
