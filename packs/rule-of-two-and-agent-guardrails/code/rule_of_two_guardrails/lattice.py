"""Monotone Rule of Two taint & capability join-semilattice over multi-step tool DAGs."""

from __future__ import annotations

from collections import deque
from typing import Any

from .grid import resolve_grid_cell


class RuleOfTwoCapabilityLattice:
    """Tracks untrusted_input (A), sensitive_access (B) and external_mutation_or_egress (C) across DAGs."""

    def __init__(
        self,
        *,
        overrides: dict[str, Any] | None = None,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.grid, self.cell, self.constants = resolve_grid_cell(
            overrides, regime=regime, spec=spec
        )
        self.canonical_legs: list[str] = list(self.constants["canonical_legs"])
        self.leg_aliases: dict[str, str] = dict(self.constants["leg_aliases"])
        self.allow_status: int = int(self.constants["allow_status_code"])
        self.refuse_status: int = int(self.constants["refuse_status_code"])
        self.triad_count: int = int(self.constants["triad_leg_count"])
        self.max_unapproved_legs: int = int(self.cell["max_unapproved_legs"])
        self.max_dag_steps: int = int(self.cell["max_dag_steps"])

    def normalize_legs(self, raw_legs: list[str] | set[str] | tuple[str, ...]) -> list[str]:
        normalized: set[str] = set()
        for raw in raw_legs:
            token = str(raw).strip()
            if token not in self.leg_aliases:
                raise ValueError(f"unknown capability leg: {token!r}")
            normalized.add(self.leg_aliases[token])
        return [leg for leg in self.canonical_legs if leg in normalized]

    def _valid_human_steward_approval(
        self,
        approval: dict[str, Any] | None,
        *,
        step_id: str,
    ) -> bool:
        if not isinstance(approval, dict):
            return False
        kind = str(approval.get("principal_kind", "")).strip()
        principal = str(approval.get("approver_principal", "")).strip()
        token = str(approval.get("token", "")).strip()
        approved_steps = approval.get("approved_steps", [])
        prefix = str(self.constants["approval_token_prefix"])
        min_len = int(self.constants["min_approval_token_len"])
        if kind != str(self.constants["required_approval_kind"]):
            return False
        if not principal or principal == "anonymous":
            return False
        if not token.startswith(prefix) or len(token) < min_len:
            return False
        if isinstance(approved_steps, list) and approved_steps:
            return step_id in {str(s) for s in approved_steps} or "*" in {str(s) for s in approved_steps}
        return str(approval.get("approved_step_id", "")) == step_id

    @staticmethod
    def _topological_order(steps: list[dict[str, Any]]) -> tuple[list[str], dict[str, list[str]]]:
        step_map: dict[str, dict[str, Any]] = {}
        parents: dict[str, list[str]] = {}
        children: dict[str, list[str]] = {}
        in_degree: dict[str, int] = {}

        for item in steps:
            sid = str(item["id"])
            if sid in step_map:
                raise ValueError(f"duplicate DAG step id: {sid!r}")
            step_map[sid] = item
            parents[sid] = []
            children[sid] = []
            in_degree[sid] = 0

        for item in steps:
            sid = str(item["id"])
            for dep_raw in item.get("depends_on", []):
                dep = str(dep_raw)
                if dep not in step_map:
                    raise ValueError(f"step {sid!r} depends on unknown upstream step {dep!r}")
                if dep not in parents[sid]:
                    parents[sid].append(dep)
                    children[dep].append(sid)
                    in_degree[sid] += 1

        ready = sorted(sid for sid, deg in in_degree.items() if deg == 0)
        order: list[str] = []
        queue: deque[str] = deque(ready)
        while queue:
            cur = queue.popleft()
            order.append(cur)
            next_ready: list[str] = []
            for child in children[cur]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    next_ready.append(child)
            for nxt in sorted(next_ready):
                queue.append(nxt)

        if len(order) != len(step_map):
            raise ValueError("cycle detected in tool DAG")
        return order, parents

    @staticmethod
    def _shortest_origin_path(
        target_step: str,
        leg: str,
        own_legs: dict[str, set[str]],
        parents: dict[str, list[str]],
    ) -> list[str]:
        """Find shortest upstream directed path [origin_step, ..., target_step] introducing leg."""
        if leg in own_legs[target_step]:
            return [target_step]
        visited: set[str] = {target_step}
        queue: deque[tuple[str, list[str]]] = deque([(target_step, [target_step])])
        while queue:
            cur, suffix = queue.popleft()
            for par in parents[cur]:
                cand_path = [par, *suffix]
                if leg in own_legs[par]:
                    return cand_path
                if par not in visited:
                    visited.add(par)
                    queue.append((par, cand_path))
        return [target_step]

    def evaluate_dag(
        self,
        steps: list[dict[str, Any]],
        *,
        human_steward_approval: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate monotone capability taint across a multi-step tool DAG."""
        if len(steps) > self.max_dag_steps:
            raise ValueError(f"DAG step count {len(steps)} exceeds grid bound {self.max_dag_steps}")

        topo_order, parents = self._topological_order(steps)
        by_id = {str(s["id"]): s for s in steps}
        own_legs: dict[str, set[str]] = {}
        effective_legs: dict[str, set[str]] = {}
        step_reports: list[dict[str, Any]] = []

        for sid in topo_order:
            raw_step = by_id[sid]
            local = set(self.normalize_legs(raw_step.get("legs", [])))
            own_legs[sid] = local
            joined = set(local)
            for par in parents[sid]:
                joined |= effective_legs[par]
            effective_legs[sid] = joined

            ordered_effective = [leg for leg in self.canonical_legs if leg in joined]
            ordered_local = [leg for leg in self.canonical_legs if leg in local]
            step_approval = raw_step.get("human_steward_approval", human_steward_approval)
            approved = self._valid_human_steward_approval(step_approval, step_id=sid)

            exceeds_lattice = len(ordered_effective) > self.max_unapproved_legs or (
                len(ordered_effective) >= self.triad_count
            )
            if exceeds_lattice and not approved:
                leg_witnesses = {
                    leg: self._shortest_origin_path(sid, leg, own_legs, parents)
                    for leg in ordered_effective
                }
                witness_nodes: set[str] = set()
                for wpath in leg_witnesses.values():
                    witness_nodes |= set(wpath)
                minimal_witness_path = [node for node in topo_order if node in witness_nodes]
                return {
                    "verdict": "refuse",
                    "allowed": False,
                    "status_code": self.refuse_status,
                    "grid_cell_id": self.grid.cell_id(self.cell),
                    "violating_step_id": sid,
                    "combined_legs": ordered_effective,
                    "minimal_witness_path": minimal_witness_path,
                    "leg_origin_paths": leg_witnesses,
                    "human_steward_approved": False,
                    "evaluated_steps": step_reports
                    + [
                        {
                            "id": sid,
                            "own_legs": ordered_local,
                            "effective_legs": ordered_effective,
                            "status_code": self.refuse_status,
                            "approved_override": False,
                        }
                    ],
                }

            step_reports.append(
                {
                    "id": sid,
                    "own_legs": ordered_local,
                    "effective_legs": ordered_effective,
                    "status_code": self.allow_status,
                    "approved_override": approved and exceeds_lattice,
                }
            )

        max_seen = 0
        for rep in step_reports:
            max_seen = max(max_seen, len(rep["effective_legs"]))

        return {
            "verdict": "allow",
            "allowed": True,
            "status_code": self.allow_status,
            "grid_cell_id": self.grid.cell_id(self.cell),
            "violating_step_id": None,
            "combined_legs": [],
            "minimal_witness_path": [],
            "leg_origin_paths": {},
            "human_steward_approved": any(bool(r["approved_override"]) for r in step_reports),
            "max_effective_legs": max_seen,
            "evaluated_steps": step_reports,
        }
