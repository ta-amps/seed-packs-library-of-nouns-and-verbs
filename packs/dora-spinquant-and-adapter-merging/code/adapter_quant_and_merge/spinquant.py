"""Pure-Python Sylvester/Walsh-Hadamard outlier rotation and symmetric low-bit quantization (SpinQuant/QuaRot)."""

from __future__ import annotations

import copy
import hashlib
import math
from typing import Any

from .grid import NodeGrid, load_default_grid_spec


class FastWalshHadamardOutlierRotator:
    """Orthogonal Walsh-Hadamard channel rotator W' = (W * s) @ H_d / sqrt(d) for outlier suppression."""

    def __init__(
        self,
        *,
        rotation_seed: int | None = None,
        quant_bits: int | None = None,
        quant_granularity: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        grid = NodeGrid(cfg)
        num = cfg["numerics"]
        sq = cfg["spinquant"]

        self._eps = float(num["epsilon"])
        self._round_digits = int(num["round_digits"])
        self._kurtosis_baseline = float(num["kurtosis_gaussian_baseline"])
        self._digest_bytes = int(num["digest_bytes"])
        self._word_bytes = int(num["word_bytes"])
        self._unit_modulus = int(num["unit_modulus"])
        self._radix = int(sq["butterfly_radix"])
        self._made_up_cfg = dict(sq)

        raw_bits = int(quant_bits if quant_bits is not None else sq["default_quant_bits"])
        raw_gran = str(quant_granularity if quant_granularity is not None else sq["default_granularity"])
        clamped = grid.clamp_cell({"quant_bits": raw_bits, "quant_granularity": raw_gran})
        self.quant_bits = int(clamped["quant_bits"])
        self.quant_granularity = str(clamped["quant_granularity"])
        self.rotation_seed = int(rotation_seed if rotation_seed is not None else sq["default_rotation_seed"])

    @staticmethod
    def is_power_of_two(dim: int) -> bool:
        return dim > 0 and (dim & (dim - 1)) == 0

    def next_power_of_two(self, dim: int) -> int:
        target = max(1, int(dim))
        power = 1
        while power < target:
            power *= self._radix
        return power

    def sign_vector(self, dim: int) -> list[float]:
        """Deterministic Rademacher sign flips s_j in {-1.0, +1.0} seeded by rotation_seed."""
        signs: list[float] = []
        for idx in range(int(dim)):
            payload = f"rademacher:{self.rotation_seed}:{idx}".encode("utf-8")
            digest = hashlib.blake2b(payload, digest_size=self._digest_bytes).digest()
            word = int.from_bytes(digest[0 : self._word_bytes], "little")
            signs.append(1.0 if (word & 1) == 0 else -1.0)
        return signs

    def _fwht_1d(self, vec: list[float]) -> list[float]:
        dim = len(vec)
        if not self.is_power_of_two(dim):
            raise ValueError("Fast Walsh-Hadamard transform requires a power-of-two dimension")
        out = list(vec)
        half_step = 1
        while half_step < dim:
            full_step = half_step * self._radix
            start = 0
            while start < dim:
                for offset in range(half_step):
                    left_idx = start + offset
                    right_idx = left_idx + half_step
                    u_val = out[left_idx]
                    v_val = out[right_idx]
                    out[left_idx] = u_val + v_val
                    out[right_idx] = u_val - v_val
                start += full_step
            half_step = full_step
        inv_norm = 1.0 / math.sqrt(float(dim))
        return [val * inv_norm for val in out]

    def rotate_matrix(self, matrix: list[list[float]]) -> list[list[float]]:
        """Compute W' = (W * diag(s)) @ H_d / sqrt(d) across power-of-two channel columns."""
        if not matrix:
            return []
        cols = len(matrix[0])
        if not self.is_power_of_two(cols):
            raise ValueError("Channel count must be a power of two for Walsh-Hadamard rotation")
        signs = self.sign_vector(cols)
        rotated: list[list[float]] = []
        for row in matrix:
            if len(row) != cols:
                raise ValueError("Ragged matrix rows are not permitted")
            signed_row = [float(val) * s_val for val, s_val in zip(row, signs)]
            rotated.append(self._fwht_1d(signed_row))
        return rotated

    def inverse_rotate_matrix(self, rotated_matrix: list[list[float]]) -> list[list[float]]:
        """Invert orthogonal rotation via W = ((W' @ H_d) / sqrt(d)) * diag(s)."""
        if not rotated_matrix:
            return []
        cols = len(rotated_matrix[0])
        signs = self.sign_vector(cols)
        recovered: list[list[float]] = []
        for row in rotated_matrix:
            unrotated = self._fwht_1d([float(val) for val in row])
            recovered.append([val * s_val for val, s_val in zip(unrotated, signs)])
        return recovered

    def channel_outlier_metrics(self, matrix: list[list[float]]) -> dict[str, float]:
        """Compute max-abs-to-RMS ratio and excess fourth-moment kurtosis over matrix entries."""
        flat = [float(x) for row in matrix for x in row]
        count = len(flat)
        if count == 0:
            return {"max_abs_to_rms": 0.0, "excess_kurtosis": 0.0}
        mean_sq = sum(x * x for x in flat) / float(count)
        rms = math.sqrt(max(mean_sq, self._eps))
        max_abs = max(abs(x) for x in flat)
        mean_val = sum(flat) / float(count)
        centered = [x - mean_val for x in flat]
        var = sum(c * c for c in centered) / float(count)
        std = math.sqrt(max(var, self._eps))
        fourth_acc = 0.0
        for c in centered:
            z = c / std
            z_sq = z * z
            fourth_acc += z_sq * z_sq
        kurtosis = (fourth_acc / float(count)) - self._kurtosis_baseline
        return {
            "max_abs_to_rms": round(max_abs / rms, self._round_digits),
            "excess_kurtosis": round(kurtosis, self._round_digits),
        }

    def quantize_dequantize(
        self,
        matrix: list[list[float]],
        *,
        bits: int | None = None,
        granularity: str | None = None,
    ) -> list[list[float]]:
        """Symmetric uniform b-bit quantization and dequantization."""
        if not matrix:
            return []
        b_val = int(bits if bits is not None else self.quant_bits)
        gran = str(granularity if granularity is not None else self.quant_granularity)
        qmax = (1 << (b_val - 1)) - 1
        if qmax <= 0:
            raise ValueError("quant_bits must be >= 2 for signed symmetric quantization")

        if gran == "per_tensor":
            abs_max = max(abs(float(x)) for row in matrix for x in row)
            scale = abs_max / float(qmax) if abs_max > self._eps else 1.0
            return [
                [
                    float(max(-qmax, min(qmax, int(round(float(x) / scale))))) * scale
                    if abs_max > self._eps
                    else 0.0
                    for x in row
                ]
                for row in matrix
            ]

        reconstructed: list[list[float]] = []
        for row in matrix:
            row_max = max((abs(float(x)) for x in row), default=0.0)
            if row_max <= self._eps:
                reconstructed.append([0.0 for _ in row])
                continue
            scale = row_max / float(qmax)
            q_row = [float(max(-qmax, min(qmax, int(round(float(x) / scale))))) * scale for x in row]
            reconstructed.append(q_row)
        return reconstructed

    def reconstruction_mse(self, reference: list[list[float]], candidate: list[list[float]]) -> float:
        total = 0
        sq_err = 0.0
        for ref_row, cand_row in zip(reference, candidate):
            for r_val, c_val in zip(ref_row, cand_row):
                diff = float(r_val) - float(c_val)
                sq_err += diff * diff
                total += 1
        if total == 0:
            return 0.0
        return sq_err / float(total)

    def evaluate_quantization(
        self,
        matrix: list[list[float]],
        *,
        bits: int | None = None,
    ) -> dict[str, float]:
        """Compare unrotated vs SpinQuant/QuaRot FWHT-rotated symmetric b-bit quantization."""
        b_val = int(bits if bits is not None else self.quant_bits)
        before_stats = self.channel_outlier_metrics(matrix)
        rotated = self.rotate_matrix(matrix)
        after_stats = self.channel_outlier_metrics(rotated)

        unrot_recon = self.quantize_dequantize(matrix, bits=b_val)
        rot_quant = self.quantize_dequantize(rotated, bits=b_val)
        rot_recon = self.inverse_rotate_matrix(rot_quant)

        mse_unrot = self.reconstruction_mse(matrix, unrot_recon)
        mse_rot = self.reconstruction_mse(matrix, rot_recon)
        reduction_factor = mse_unrot / max(mse_rot, self._eps)

        return {
            "unrotated_max_to_rms": before_stats["max_abs_to_rms"],
            "rotated_max_to_rms": after_stats["max_abs_to_rms"],
            "unrotated_excess_kurtosis": before_stats["excess_kurtosis"],
            "rotated_excess_kurtosis": after_stats["excess_kurtosis"],
            "unrotated_quant_mse": round(mse_unrot, self._round_digits),
            "rotated_quant_mse": round(mse_rot, self._round_digits),
            "mse_reduction_factor": round(reduction_factor, self._round_digits),
        }

    def generate_heavy_tailed_channel_matrix(
        self,
        *,
        rows: int | None = None,
        cols: int | None = None,
        outlier_channels: int | None = None,
        outlier_scale: float | None = None,
        seed: int | None = None,
    ) -> list[list[float]]:
        """Deterministic made-up channel matrix with concentrated heavy-tailed outlier columns."""
        n_rows = int(rows if rows is not None else self._made_up_cfg["made_up_rows"])
        n_cols = int(cols if cols is not None else self._made_up_cfg["made_up_cols"])
        n_outliers = int(
            outlier_channels if outlier_channels is not None else self._made_up_cfg["made_up_outlier_channels"]
        )
        scale = float(outlier_scale if outlier_scale is not None else self._made_up_cfg["made_up_outlier_scale"])
        gen_seed = int(seed if seed is not None else self._made_up_cfg["made_up_seed"])
        mod = self._unit_modulus

        matrix: list[list[float]] = []
        for r_idx in range(n_rows):
            row_vals: list[float] = []
            for c_idx in range(n_cols):
                payload = f"mat:{gen_seed}:{r_idx}:{c_idx}".encode("utf-8")
                digest = hashlib.blake2b(payload, digest_size=self._digest_bytes).digest()
                raw_int = int.from_bytes(digest[0 : self._word_bytes], "little") % mod
                unit = (float(raw_int) / float(mod - 1)) - 1.0 + (float(raw_int) / float(mod - 1))
                amp = scale if c_idx < n_outliers else 1.0
                row_vals.append(unit * amp)
            matrix.append(row_vals)
        return matrix
