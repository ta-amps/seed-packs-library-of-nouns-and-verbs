"""Weight-Decomposed Low-Rank Adaptation (DoRA) analyzer and TIES subspace interference router."""

from __future__ import annotations

import copy
import math
from typing import Any

from .grid import NodeGrid, load_default_grid_spec


def _matmul(mat_b: list[list[float]], mat_a: list[list[float]]) -> list[list[float]]:
    if not mat_b or not mat_a:
        return []
    rows_b = len(mat_b)
    rank = len(mat_b[0])
    if len(mat_a) != rank:
        raise ValueError("Inner rank dimension mismatch in low-rank matrix product B @ A")
    cols_a = len(mat_a[0])
    out: list[list[float]] = []
    for i in range(rows_b):
        row_out: list[float] = []
        for j in range(cols_a):
            acc = 0.0
            for k in range(rank):
                acc += float(mat_b[i][k]) * float(mat_a[k][j])
            row_out.append(acc)
        out.append(row_out)
    return out


class WeightDecomposedLoraAnalyzer:
    """Decomposes W = m * (V / ||V||_col) from base weights W_0 and low-rank (B @ A) deltas."""

    def __init__(self, *, spec: dict[str, Any] | None = None) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        num = cfg["numerics"]
        dora_cfg = cfg["dora"]
        self._eps = float(num["epsilon"])
        self._round_digits = int(num["round_digits"])
        self._default_alpha = float(dora_cfg["default_lora_alpha"])
        self._default_rank = int(dora_cfg["default_lora_rank"])

    def decompose_columns(self, weights: list[list[float]]) -> dict[str, Any]:
        """Decompose matrix into per-column Euclidean magnitudes m_j = ||V[:, j]||_2 and unit directions."""
        if not weights or not weights[0]:
            return {"magnitudes": [], "unit_directions": []}
        rows = len(weights)
        cols = len(weights[0])
        magnitudes: list[float] = []
        unit_cols: list[list[float]] = []
        for j in range(cols):
            sq_norm = 0.0
            for i in range(rows):
                val = float(weights[i][j])
                sq_norm += val * val
            col_norm = math.sqrt(max(sq_norm, self._eps))
            magnitudes.append(col_norm)
            unit_cols.append([float(weights[i][j]) / col_norm for i in range(rows)])

        unit_matrix = [[unit_cols[j][i] for j in range(cols)] for i in range(rows)]
        return {
            "magnitudes": magnitudes,
            "unit_directions": unit_matrix,
        }

    def compose_dora_weights(
        self,
        base_weights: list[list[float]],
        lora_b: list[list[float]],
        lora_a: list[list[float]],
        learned_magnitudes: list[float],
        *,
        lora_scale: float | None = None,
    ) -> list[list[float]]:
        """Synthesize W_dora = diag_col(m) * ((W_0 + scale * B @ A) / ||W_0 + scale * B @ A||_col)."""
        rank = len(lora_a) if lora_a else self._default_rank
        scale = float(lora_scale) if lora_scale is not None else (self._default_alpha / float(max(1, rank)))
        delta = _matmul(lora_b, lora_a)
        rows = len(base_weights)
        cols = len(base_weights[0]) if rows > 0 else 0
        if len(learned_magnitudes) != cols:
            raise ValueError("learned_magnitudes length must match column count")
        combined = [
            [float(base_weights[i][j]) + scale * float(delta[i][j]) for j in range(cols)]
            for i in range(rows)
        ]
        decomp = self.decompose_columns(combined)
        unit_dirs = decomp["unit_directions"]
        return [
            [float(learned_magnitudes[j]) * float(unit_dirs[i][j]) for j in range(cols)]
            for i in range(rows)
        ]

    def analyze_low_rank_update(
        self,
        base_weights: list[list[float]],
        lora_b: list[list[float]],
        lora_a: list[list[float]],
        *,
        learned_magnitudes: list[float] | None = None,
        lora_scale: float | None = None,
    ) -> dict[str, Any]:
        """Measure DoRA directional (1 - cos(V_0, V_1)) vs relative magnitude |m_1 - m_0| / ||V_0|| learning ratios."""
        rank = len(lora_a) if lora_a else self._default_rank
        scale = float(lora_scale) if lora_scale is not None else (self._default_alpha / float(max(1, rank)))
        delta = _matmul(lora_b, lora_a)
        rows = len(base_weights)
        cols = len(base_weights[0]) if rows > 0 else 0
        updated_v = [
            [float(base_weights[i][j]) + scale * float(delta[i][j]) for j in range(cols)]
            for i in range(rows)
        ]

        base_dec = self.decompose_columns(base_weights)
        upd_dec = self.decompose_columns(updated_v)
        m0_list: list[float] = base_dec["magnitudes"]
        m1_list: list[float] = (
            [float(m) for m in learned_magnitudes]
            if learned_magnitudes is not None
            else list(upd_dec["magnitudes"])
        )
        u0_mat: list[list[float]] = base_dec["unit_directions"]
        u1_mat: list[list[float]] = upd_dec["unit_directions"]

        rel_mag_deltas: list[float] = []
        dir_deltas: list[float] = []
        for j in range(cols):
            rel_mag = abs(m1_list[j] - m0_list[j]) / max(m0_list[j], self._eps)
            cos_sim = sum(u0_mat[i][j] * u1_mat[i][j] for i in range(rows))
            clamped_cos = max(-1.0, min(1.0, cos_sim))
            dir_div = 1.0 - clamped_cos
            rel_mag_deltas.append(rel_mag)
            dir_deltas.append(dir_div)

        denom = float(max(1, cols))
        mean_mag = sum(rel_mag_deltas) / denom
        mean_dir = sum(dir_deltas) / denom
        dir_to_mag_ratio = mean_dir / max(mean_mag, self._eps)

        return {
            "mean_relative_magnitude_delta": round(mean_mag, self._round_digits),
            "mean_directional_cosine_delta": round(mean_dir, self._round_digits),
            "directional_to_magnitude_ratio": round(dir_to_mag_ratio, self._round_digits),
            "per_column_magnitudes": [round(m, self._round_digits) for m in m1_list],
        }


class SubspaceInterferenceAndMergeRouter:
    """Computes Frobenius cosine similarity, TIES sign-conflict density and static-vs-dynamic adapter routing."""

    def __init__(
        self,
        *,
        trim_density: float | None = None,
        scaling_lambda: float | None = None,
        max_cosine_for_static_merge: float | None = None,
        max_sign_conflict_for_static_merge: float | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        grid = NodeGrid(cfg)
        num = cfg["numerics"]
        tr = cfg["ties_router"]

        self._eps = float(num["epsilon"])
        self._round_digits = int(num["round_digits"])
        self._min_overlap_elements = int(tr["min_overlap_elements"])

        clamped = grid.clamp_cell({
            "ties_trim_density": trim_density if trim_density is not None else tr["default_trim_density"],
            "max_cosine_for_static_merge": (
                max_cosine_for_static_merge
                if max_cosine_for_static_merge is not None
                else tr["max_cosine_for_static_merge"]
            ),
            "max_sign_conflict_for_static_merge": (
                max_sign_conflict_for_static_merge
                if max_sign_conflict_for_static_merge is not None
                else tr["max_sign_conflict_for_static_merge"]
            ),
        })
        self.trim_density = float(clamped["ties_trim_density"])
        self.max_cosine_for_static_merge = float(clamped["max_cosine_for_static_merge"])
        self.max_sign_conflict_for_static_merge = float(clamped["max_sign_conflict_for_static_merge"])
        self.scaling_lambda = float(
            scaling_lambda if scaling_lambda is not None else tr["default_scaling_lambda"]
        )

    @staticmethod
    def flatten_matrix(matrix: list[list[float]]) -> list[float]:
        return [float(val) for row in matrix for val in row]

    def frobenius_cosine_similarity(
        self,
        delta_a: list[list[float]],
        delta_b: list[list[float]],
    ) -> float:
        vec_a = self.flatten_matrix(delta_a)
        vec_b = self.flatten_matrix(delta_b)
        if len(vec_a) != len(vec_b):
            raise ValueError("Adapter delta shapes must match for Frobenius cosine similarity")
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(max(sum(a * a for a in vec_a), self._eps))
        norm_b = math.sqrt(max(sum(b * b for b in vec_b), self._eps))
        return round(max(-1.0, min(1.0, dot / (norm_a * norm_b))), self._round_digits)

    def _trim_vector(self, vec: list[float]) -> list[float]:
        length = len(vec)
        if length == 0:
            return []
        keep_count = max(1, min(length, int(math.ceil(self.trim_density * float(length)))))
        ranked = sorted(range(length), key=lambda idx: (-abs(vec[idx]), idx))
        keep_indices = set(ranked[:keep_count])
        return [vec[idx] if idx in keep_indices else 0.0 for idx in range(length)]

    def ties_trim_elect_merge(self, deltas: list[list[list[float]]]) -> dict[str, Any]:
        """Run TIES (Trim, Elect Sign, Disjoint Merge) and measure sign-conflict density."""
        if not deltas or not deltas[0]:
            return {
                "merged_delta": [],
                "sign_conflict_density": 0.0,
                "active_coordinates": 0,
                "conflicting_coordinates": 0,
            }
        rows = len(deltas[0])
        cols = len(deltas[0][0])
        flat_trimmed = [self._trim_vector(self.flatten_matrix(mat)) for mat in deltas]
        total_coords = rows * cols
        for trimmed in flat_trimmed:
            if len(trimmed) != total_coords:
                raise ValueError("All adapter deltas must share identical dimensions")

        merged_flat: list[float] = []
        active_coords = 0
        conflict_coords = 0

        for pos in range(total_coords):
            non_zero = [t[pos] for t in flat_trimmed if abs(t[pos]) > self._eps]
            if not non_zero:
                merged_flat.append(0.0)
                continue

            if len(non_zero) >= self._min_overlap_elements:
                active_coords += 1
                has_pos = any(val > 0.0 for val in non_zero)
                has_neg = any(val < 0.0 for val in non_zero)
                if has_pos and has_neg:
                    conflict_coords += 1

            mass_sum = sum(non_zero)
            elected_positive = mass_sum >= 0.0
            agreeing = [
                val for val in non_zero if (val > 0.0 if elected_positive else val < 0.0)
            ]
            if not agreeing:
                merged_flat.append(0.0)
            else:
                disjoint_mean = sum(agreeing) / float(len(agreeing))
                merged_flat.append(self.scaling_lambda * disjoint_mean)

        conflict_density = (
            float(conflict_coords) / float(active_coords) if active_coords > 0 else 0.0
        )
        merged_matrix = [
            [round(merged_flat[r * cols + c], self._round_digits) for c in range(cols)]
            for r in range(rows)
        ]
        return {
            "merged_delta": merged_matrix,
            "sign_conflict_density": round(conflict_density, self._round_digits),
            "active_coordinates": active_coords,
            "conflicting_coordinates": conflict_coords,
        }

    def route_adapters(self, deltas: list[list[list[float]]]) -> dict[str, Any]:
        """Evaluate pairwise Frobenius cosine + TIES sign conflicts and recommend static merge vs dynamic switch."""
        if len(deltas) < self._min_overlap_elements:
            raise ValueError("At least two adapter deltas are required for interference routing")

        max_abs_cos = 0.0
        pair_cosines: list[float] = []
        for i in range(len(deltas)):
            for j in range(i + 1, len(deltas)):
                cos_ij = self.frobenius_cosine_similarity(deltas[i], deltas[j])
                pair_cosines.append(cos_ij)
                if abs(cos_ij) > max_abs_cos:
                    max_abs_cos = abs(cos_ij)

        ties_res = self.ties_trim_elect_merge(deltas)
        conflict_density = float(ties_res["sign_conflict_density"])

        low_interference = (
            max_abs_cos <= self.max_cosine_for_static_merge
            and conflict_density <= self.max_sign_conflict_for_static_merge
        )
        recommended_strategy = (
            "ties_static_merge" if low_interference else "dynamic_co_resident_switch"
        )
        return {
            "max_abs_frobenius_cosine": round(max_abs_cos, self._round_digits),
            "pairwise_frobenius_cosines": pair_cosines,
            "sign_conflict_density": conflict_density,
            "recommended_strategy": recommended_strategy,
            "merged_delta": ties_res["merged_delta"],
        }
