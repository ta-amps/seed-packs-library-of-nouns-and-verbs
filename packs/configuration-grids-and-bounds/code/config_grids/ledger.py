"""GridLedger lifecycle enforcement and OperationCostLedger contextual regime selection."""

from __future__ import annotations

from typing import Any

from .grid import NodeGrid

CELL_LIFECYCLE_ORDER: tuple[str, ...] = (
    "represented",
    "applicable",
    "proposed",
    "dispatched",
    "evaluated",
    "verified",
    "promoted",
)


class GridLedger:
    """Tracks configuration cell lifecycle and enforces verified + distinct-reviewer promotion."""

    def __init__(self, grid: NodeGrid) -> None:
        self.grid = grid
        self.http_conflict = int(grid.spec["http_conflict_status"])
        self.http_ok = int(grid.spec["http_ok_status"])
        self.records: dict[str, dict[str, Any]] = {}
        enumerated = grid.enumerate_cells()
        for cell in enumerated["represented"]:
            cid = grid.cell_id(cell)
            self.records[cid] = {
                "cell_id": cid,
                "cell": dict(cell),
                "state": "applicable" if grid.is_applicable(cell) else "represented",
                "proposer_worker_id": None,
                "proposer_key_id": None,
                "verifier_worker_id": None,
                "verifier_key_id": None,
                "metrics": None,
            }

    def transition(
        self,
        cell: dict[str, Any],
        target_state: str,
        *,
        worker_id: str = "",
        key_id: str = "",
        metrics: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        cid = self.grid.cell_id(self.grid.clamp_cell(cell))
        if cid not in self.records:
            raise KeyError(f"unknown grid cell: {cid}")
        rec = self.records[cid]
        cur_idx = CELL_LIFECYCLE_ORDER.index(rec["state"])
        tgt_idx = CELL_LIFECYCLE_ORDER.index(target_state)
        if rec["state"] == "represented" and tgt_idx > 0:
            return {"ok": False, "status_code": self.http_conflict, "reason": "inapplicable_constraint_cell"}
        if tgt_idx != cur_idx + 1:
            return {
                "ok": False,
                "status_code": self.http_conflict,
                "reason": f"invalid_lifecycle_jump:{rec['state']}->{target_state}",
            }
        if target_state == "proposed":
            rec["proposer_worker_id"] = worker_id
            rec["proposer_key_id"] = key_id
        elif target_state == "evaluated" and metrics is not None:
            rec["metrics"] = dict(metrics)
        elif target_state == "verified":
            if (
                not worker_id
                or not key_id
                or worker_id == rec["proposer_worker_id"]
                or key_id == rec["proposer_key_id"]
            ):
                return {
                    "ok": False,
                    "status_code": self.http_conflict,
                    "reason": "distinct_verifier_required",
                }
            rec["verifier_worker_id"] = worker_id
            rec["verifier_key_id"] = key_id
        rec["state"] = target_state
        return {"ok": True, "status_code": self.http_ok, "cell_id": cid, "state": target_state}


class OperationCostLedger:
    """Resolves verified or fallback grid cells contextually by workload regime signature."""

    def __init__(self, grid: NodeGrid, ledger: GridLedger) -> None:
        self.grid = grid
        self.ledger = ledger
        self.observations: list[dict[str, Any]] = []

    def record_observation(
        self,
        *,
        regime: str,
        cell: dict[str, Any],
        quality_score: float,
        cost_units: float,
    ) -> str:
        clamped = self.grid.clamp_cell(cell)
        cid = self.grid.cell_id(clamped)
        self.observations.append({
            "regime": regime,
            "cell_id": cid,
            "cell": clamped,
            "quality_score": float(quality_score),
            "cost_units": float(cost_units),
        })
        return cid

    def resolve_for_regime(self, regime: str, *, min_quality: float = 0.0) -> dict[str, Any]:
        candidates: list[tuple[float, str, dict[str, Any]]] = []
        for obs in self.observations:
            if obs["regime"] != regime or obs["quality_score"] < min_quality:
                continue
            cid = obs["cell_id"]
            state = self.ledger.records.get(cid, {}).get("state", "")
            if state in ("verified", "promoted"):
                candidates.append((obs["cost_units"], cid, obs["cell"]))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]))
            best_cost, best_cid, best_cell = candidates[0]
            return {
                "regime": regime,
                "source": "verified_ledger_optimum",
                "cell_id": best_cid,
                "cell": dict(best_cell),
                "cost_units": best_cost,
            }
        fallback_raw = self.grid.regime_defaults.get(regime, {})
        fallback_cell = self.grid.clamp_cell(fallback_raw)
        return {
            "regime": regime,
            "source": "regime_default",
            "cell_id": self.grid.cell_id(fallback_cell),
            "cell": fallback_cell,
            "cost_units": None,
        }
