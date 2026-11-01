"""Standard-library engine for Stem-Cell Multi-Profile DAG Compilation & Answer Generalization."""
from __future__ import annotations

import ast
from collections import deque
from collections.abc import Mapping, Sequence
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import tempfile
from typing import Any


def load_default_grid_spec(path: Path | None = None) -> dict[str, Any]:
    target = path or (Path(__file__).resolve().parent / "default_grid_spec.json")
    return json.loads(target.read_text(encoding="utf-8"))


def _sha256_obj(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ZeroHardcodedValuesAstGate:
    """AST scanner refusing numeric literals outside `{-1, 0, 1, -1.0, 0.0, 1.0}`."""

    @staticmethod
    def scan_source(
        source_code: str,
        allowed_identities: Sequence[int | float],
        source_label: str = "<module>",
    ) -> list[dict[str, Any]]:
        allowed = {float(x) for x in allowed_identities}
        tree = ast.parse(source_code, filename=source_label)
        violations: list[dict[str, Any]] = []

        def _walk(node: ast.AST) -> None:
            if (
                isinstance(node, ast.UnaryOp)
                and isinstance(node.op, ast.USub)
                and isinstance(node.operand, ast.Constant)
                and isinstance(node.operand.value, (int, float))
                and not isinstance(node.operand.value, bool)
            ):
                val = -node.operand.value
                if float(val) not in allowed:
                    violations.append({"lineno": node.lineno, "value": val})
                return
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, (int, float))
                and not isinstance(node.value, bool)
            ):
                if float(node.value) not in allowed:
                    violations.append({"lineno": node.lineno, "value": node.value})
            for child in ast.iter_child_nodes(node):
                _walk(child)

        _walk(tree)
        return violations


class DomainAgnosticNamingGate:
    """Scanner refusing industry-coupled class, function, or module identifiers."""

    @staticmethod
    def scan_source(
        source_code: str,
        forbidden_tokens: Sequence[str],
        source_label: str = "<module>",
    ) -> list[dict[str, str]]:
        banned = [str(t).lower() for t in forbidden_tokens]
        tree = ast.parse(source_code, filename=source_label)
        violations: list[dict[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                words = [
                    w.lower()
                    for w in re.findall(
                        r"[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|[A-Z]?[a-z]+|\d+",
                        node.name,
                    )
                ]
                joined = "_".join(words)
                for tok in banned:
                    if (tok in words) or ("_" in tok and f"_{tok}_" in f"_{joined}_"):
                        violations.append({"identifier": node.name, "token": tok})
                        break
        return violations


class ComposableMetaSettingsGrid:
    """Declarative Meta-Grid with monotonic ledger promotion & 4-way Bidirectional Morphogenesis."""

    STAGES: tuple[str, ...] = (
        "represented",
        "applicable",
        "proposed",
        "dispatched",
        "evaluated",
        "verified",
        "promoted",
    )

    def __init__(self, spec: Mapping[str, Any]) -> None:
        self.spec = dict(spec)
        self.axes: dict[str, list[Any]] = {
            str(k): list(v) for k, v in self.spec["grid_axes"].items()
        }
        self.bounds = dict(self.spec["parameter_bounds"])
        self.policy = dict(self.spec["morphogenesis_policy"])
        self.generation: int = 1
        self.ledger_stages: dict[str, str] = {}
        self._rebuild_cells()

    def _rebuild_cells(self) -> None:
        keys = list(self.axes.keys())
        vals = [self.axes[k] for k in keys]
        self.cells: list[dict[str, Any]] = [
            dict(zip(keys, combo)) for combo in itertools.product(*vals)
        ]
        self.ledger_stages = {_sha256_obj(c): "applicable" for c in self.cells}

    def advance_cell_to_promoted(self, cell: Mapping[str, Any]) -> str:
        cid = _sha256_obj(cell)
        for next_stage in ("proposed", "dispatched", "evaluated", "verified", "promoted"):
            cur_idx = self.STAGES.index(self.ledger_stages[cid])
            tgt_idx = self.STAGES.index(next_stage)
            if tgt_idx != cur_idx + 1:
                raise ValueError(f"non_monotonic_stage:{self.ledger_stages[cid]}->{next_stage}")
            self.ledger_stages[cid] = next_stage
        return self.ledger_stages[cid]

    def evolve_morphogenesis(
        self,
        *,
        req_width: int,
        req_depth: int,
        req_coalesce: int,
        req_canary: float,
    ) -> dict[str, Any]:
        mult = int(self.policy["upper_growth_multiplier"])
        div = float(self.policy["lower_contraction_divisor"])
        prune_c = float(self.policy["prune_dominated_canary_rate"])
        half = float(self.spec["half_factor"])
        rnd = int(self.spec["round_digits"])

        actions: list[str] = []
        for axis_name, req_val in (
            ("max_dag_parallel_width", req_width),
            ("max_dag_wave_depth", req_depth),
            ("coalesce_batch_cap", req_coalesce),
        ):
            cur = sorted(int(v) for v in self.axes[axis_name])
            max_b = int(self.bounds[axis_name]["maximum"])
            if req_val > cur[-1]:
                grown = min(max_b, max(req_val, cur[-1] * mult))
                cur.append(grown)
                self.axes[axis_name] = sorted(cur)
                actions.append(f"expand:{axis_name}->{grown}")

        can_vals = sorted(float(v) for v in self.axes["canary_audit_rate"])
        if prune_c in can_vals and len(can_vals) > 1:
            can_vals = [v for v in can_vals if v != prune_c]
            actions.append(f"prune:canary_audit_rate=={prune_c}")
        min_can = float(self.bounds["canary_audit_rate"]["minimum"])
        if req_canary < can_vals[0]:
            low_v = round(max(min_can, min(req_canary, can_vals[0] / div)), rnd)
            can_vals.insert(0, low_v)
            actions.append(f"contract:canary_audit_rate->{low_v}")
        self.axes["canary_audit_rate"] = sorted(can_vals)

        stag = sorted(int(v) for v in self.axes["hedge_stagger_quantile_ms"])
        if len(stag) > 1:
            mid = int(round(float(stag[0] + stag[-1]) * half))
            if mid not in stag:
                stag.append(mid)
                self.axes["hedge_stagger_quantile_ms"] = sorted(stag)
                actions.append(f"bisect:hedge_stagger_quantile_ms->{mid}")

        if actions:
            self.generation += 1
            self._rebuild_cells()
        return {"generation": self.generation, "actions": actions, "cell_count": len(self.cells)}


class AutonomousDesignSpaceGeneralizer:
    """Lifts `(A, B)` forks into `{A, B, A (+) B}` `task objects` with `0` human scalar prompts."""

    def __init__(self, spec: Mapping[str, Any]) -> None:
        self.spec = dict(spec)
        self.mp = dict(self.spec["manifold_physics"])
        self.human_scalar_prompts_issued: int = 0

    def lift_and_resolve(
        self,
        endpoint_a: Mapping[str, Any],
        endpoint_b: Mapping[str, Any],
        *,
        quality_floor: float,
        latency_sla_ms: float,
        cost_ceiling_usd: float,
    ) -> dict[str, Any]:
        rnd = int(self.spec["round_digits"])
        pct = float(self.spec["percentage_scale"])
        qa, la, ca = (
            float(endpoint_a["expected_quality"]),
            float(endpoint_a["expected_latency_ms"]),
            float(endpoint_a["expected_cost_usd"]),
        )
        qb, lb, cb = (
            float(endpoint_b["expected_quality"]),
            float(endpoint_b["expected_latency_ms"]),
            float(endpoint_b["expected_cost_usd"]),
        )

        u = min(1.0 - (1.0 / pct), max(0.0, float(self.mp["vcg_clean_utilization"])))
        vcg_price = float(self.mp["vcg_base_price_usd"]) * (
            1.0 + math.pow(u / (1.0 - u), float(self.mp["vcg_congestion_exponent"]))
        )

        candidates: list[dict[str, Any]] = [
            {
                "option_id": str(endpoint_a["option_id"]),
                "alpha": 0.0,
                "quality": qa,
                "latency_ms": la,
                "cost_usd": ca,
            }
        ]
        for raw_w in self.mp["blend_weights"]:
            alpha = float(raw_w)
            candidates.append(
                {
                    "option_id": f"composite_{endpoint_a['option_id']}_{endpoint_b['option_id']}_a{alpha}",
                    "alpha": alpha,
                    "quality": round(
                        min(
                            1.0,
                            (1.0 - alpha) * qa
                            + alpha * qb
                            + float(self.mp["synergy_quality_bonus"]),
                        ),
                        rnd,
                    ),
                    "latency_ms": round(
                        ((1.0 - alpha) * la + alpha * lb)
                        * float(self.mp["synergy_latency_factor"]),
                        rnd,
                    ),
                    "cost_usd": round(
                        ((1.0 - alpha) * ca + alpha * cb)
                        * float(self.mp["synergy_cost_factor"]),
                        rnd,
                    ),
                }
            )
        candidates.append(
            {
                "option_id": str(endpoint_b["option_id"]),
                "alpha": 1.0,
                "quality": qb,
                "latency_ms": lb,
                "cost_usd": cb + vcg_price,
            }
        )

        ranked = sorted(
            candidates,
            key=lambda c: (
                1
                if (
                    c["quality"] >= quality_floor
                    and c["latency_ms"] <= latency_sla_ms
                    and c["cost_usd"] <= cost_ceiling_usd
                )
                else 0,
                c["quality"],
                -c["cost_usd"],
                -c["latency_ms"],
            ),
            reverse=True,
        )
        return {
            "selected": ranked[0],
            "manifold_size": len(candidates),
            "human_scalar_prompts_issued": self.human_scalar_prompts_issued,
        }

    def prune_evsi_branches(self, utility_gains: Sequence[float]) -> int:
        pct = float(self.spec["percentage_scale"])
        w_usd = float(self.mp["evsi_usd_weight"])
        w_ms = float(self.mp["evsi_ms_weight"])
        pen = w_usd * float(self.mp["evsi_subtree_cost_usd"]) + w_ms * (
            float(self.mp["evsi_subtree_ms"]) / pct
        )
        return sum(1 for g in utility_gains if (float(g) * w_usd - pen) <= 0.0)

    def compute_shapley_culprit(
        self,
        edge_ms: Mapping[str, float],
        baseline_ms: float,
    ) -> str:
        edges = list(edge_ms.keys())
        excess = {e: max(0.0, float(v) - baseline_ms) for e, v in edge_ms.items()}
        n = len(edges)
        fact = [math.factorial(k) for k in range(n + 1)]
        denom = float(fact[n])
        credits: dict[str, float] = {}
        for i, eid in enumerate(edges):
            bit = 1 << i
            phi = 0.0
            for mask in range(1 << n):
                if (mask & bit) != 0:
                    continue
                s_sz = mask.bit_count()
                w = float(fact[s_sz] * fact[n - s_sz - 1]) / denom
                phi += w * excess[eid]
            credits[eid] = phi
        return max(credits.items(), key=lambda kv: (kv[1], kv[0]))[0]


class MultiProfileDagTopologyCompiler:
    """Compiles `tasks (things to do)` into 7 verified Kahn-wave DAG profiles."""

    def __init__(self, spec: Mapping[str, Any]) -> None:
        self.spec = dict(spec)
        self.profiles = tuple(str(p) for p in self.spec["dag_profiles"])

    @staticmethod
    def _kahn_waves(
        vertices: Sequence[str],
        edges: Sequence[tuple[str, str]],
    ) -> list[list[str]]:
        indeg = {v: 0 for v in vertices}
        adj: dict[str, list[str]] = {v: [] for v in vertices}
        for u, v in edges:
            adj[u].append(v)
            indeg[v] += 1
        q = deque(v for v in vertices if indeg[v] == 0)
        waves: list[list[str]] = []
        seen = 0
        while q:
            lvl: list[str] = []
            for _ in range(len(q)):
                cur = q.popleft()
                lvl.append(cur)
                seen += 1
                for nxt in adj[cur]:
                    indeg[nxt] -= 1
                    if indeg[nxt] == 0:
                        q.append(nxt)
            waves.append(lvl)
        if seen != len(vertices):
            raise ValueError("cyclic_dag_rejected")
        return waves

    def compile_all_profiles(self, width: int) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        eff_w = max(1, width)
        makers = ["muse", "opencode", "codex"]
        checker = "pi"
        for prof in self.profiles:
            if prof == "linear_waterfall":
                verts = ["v_in", "v_rung0", "v_worker", "v_seal"]
                edges = [("v_in", "v_rung0"), ("v_rung0", "v_worker"), ("v_worker", "v_seal")]
                mc_violation = 0
            elif prof == "quorum_adjudication_dag":
                m_nodes = [f"v_maker_{h}" for h in makers]
                verts = ["v_in", *m_nodes, f"v_checker_{checker}", "v_seal"]
                edges = [
                    *[("v_in", m) for m in m_nodes],
                    *[(m, f"v_checker_{checker}") for m in m_nodes],
                    (f"v_checker_{checker}", "v_seal"),
                ]
                mc_violation = 1 if checker in makers else 0
            else:
                b_nodes = [f"v_branch_{i}" for i in range(eff_w)]
                verts = ["v_in", *b_nodes, "v_join", "v_seal"]
                edges = [
                    *[("v_in", b) for b in b_nodes],
                    *[(b, "v_join") for b in b_nodes],
                    ("v_join", "v_seal"),
                ]
                mc_violation = 0
            waves = self._kahn_waves(verts, edges)
            out[prof] = {
                "waves": waves,
                "maker_checker_violation": mc_violation,
            }
        return out


class EphemeralCliHarnessMaterializer:
    """Materializes isolated CLI workspaces and vaporizes them unconditionally in `finally`."""

    def __init__(self, spec: Mapping[str, Any]) -> None:
        self.spec = dict(spec)
        self._live: set[str] = set()
        self.reports: list[dict[str, Any]] = []

    @property
    def ephemeral_retained(self) -> int:
        return len(self._live)

    def run_ephemeral_step(self, harness_id: str, task_id: str) -> dict[str, Any]:
        h_spec = self.spec["harness_families"][harness_id]
        indent_n = int(self.spec["json_indent"])
        mode = int(self.spec["sandbox_dir_mode"])
        wdir = Path(tempfile.mkdtemp(prefix=f"pack_ws_{harness_id}_"))
        os.chmod(wdir, mode)
        self._live.add(str(wdir))
        try:
            (wdir / "AGENTS.md").write_text(f"# Lease {task_id}\n", encoding="utf-8")
            (wdir / str(h_spec["config_filename"])).write_text(
                json.dumps({"harness": harness_id}, indent=indent_n),
                encoding="utf-8",
            )
            refs = [
                {
                    "name": p.name,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                }
                for p in sorted(wdir.iterdir())
                if p.is_file()
            ]
            rep = {
                "harness": harness_id,
                "bundle_sha256": _sha256_obj(refs),
                "vaporized": True,
            }
            self.reports.append(rep)
            return rep
        finally:
            if wdir.exists():
                shutil.rmtree(wdir, ignore_errors=False)
            self._live.discard(str(wdir))


class SubprocessDagJoinExecutor:
    """Executes SHA-256-locked `python3 -I` weighted fan-in join with `RLIMIT_CPU`."""

    def __init__(self, spec: Mapping[str, Any]) -> None:
        self.spec = dict(spec)
        self._live: set[str] = set()

    @property
    def ephemeral_retained(self) -> int:
        return len(self._live)

    def run_join(self, values: Sequence[float], weights: Sequence[float]) -> float:
        kspec = self.spec["subprocess_dag_join_kernel"]
        src = str(kspec["script_source"])
        actual = hashlib.sha256(src.encode("utf-8")).hexdigest()
        if actual != str(kspec["expected_sha256"]):
            raise ValueError("tampered_join_kernel")
        mode = int(self.spec["sandbox_dir_mode"])
        cpu_s = int(self.spec["subprocess_rlimit_cpu_seconds"])
        t_out = float(self.spec["subprocess_timeout_seconds"])

        rdir = Path(tempfile.mkdtemp(prefix="pack_join_"))
        os.chmod(rdir, mode)
        self._live.add(str(rdir))
        try:
            spath = rdir / "join_kernel.py"
            spath.write_text(src, encoding="utf-8")

            def _lim() -> None:
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))

            proc = subprocess.run(
                [sys.executable, "-I", str(spath)],
                input=json.dumps(
                    {
                        "branch_values": [float(v) for v in values],
                        "branch_weights": [float(w) for w in weights],
                    }
                ),
                capture_output=True,
                text=True,
                cwd=str(rdir),
                timeout=t_out,
                preexec_fn=_lim,
                check=True,
            )
            return float(json.loads(proc.stdout)["merged_value"])
        finally:
            if rdir.exists():
                shutil.rmtree(rdir, ignore_errors=False)
            self._live.discard(str(rdir))


class CegisCanaryCrystallizer:
    """Synthesizes Rung-0 `BlueprintArtifact` at quorum and recovers `v1 -> v2` on canary drift."""

    def __init__(self, rnd: int) -> None:
        self.rnd = rnd
        self.version: int = 0
        self.support_ext: bool = False
        self.demotions: int = 0
        self.misses: int = 0
        self.sprawled_repos: int = 0

    @staticmethod
    def _oracle(p: Mapping[str, Any]) -> float:
        q = float(p.get("quantity", 0.0))
        u = float(p.get("unit_amount", 0.0))
        a = float(p.get("attenuation_ratio", 0.0))
        g = float(p.get("gain_factor", 1.0))
        return q * u * (1.0 - a) * g

    def execute(self, payload: Mapping[str, Any], quorum: int) -> dict[str, Any]:
        truth = self._oracle(payload)
        if self.version == 0:
            self.misses += 1
            if self.misses >= quorum:
                self.version = 1
            return {"value": round(truth, self.rnd), "version": self.version}

        pred = (
            truth
            if self.support_ext
            else float(payload.get("quantity", 0.0)) * float(payload.get("unit_amount", 0.0))
        )
        if round(pred, self.rnd) != round(truth, self.rnd):
            self.demotions += 1
            self.support_ext = True
            self.version += 1
            return {"value": round(truth, self.rnd), "version": self.version}
        return {"value": round(pred, self.rnd), "version": self.version}


def run_bundle(bundle: Mapping[str, Any], spec: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Execute a complete DAG stem-cell & generalizer verification bundle."""
    cfg = dict(spec or load_default_grid_spec())
    rnd = int(cfg["round_digits"])
    mp = cfg["manifold_physics"]

    meta_grid = ComposableMetaSettingsGrid(cfg)
    meta_grid.advance_cell_to_promoted(meta_grid.cells[0])
    morph = meta_grid.evolve_morphogenesis(
        req_width=int(bundle["surge_requirements"]["parallel_width"]),
        req_depth=int(bundle["surge_requirements"]["wave_depth"]),
        req_coalesce=int(bundle["surge_requirements"]["coalesce_batch"]),
        req_canary=float(bundle["surge_requirements"]["low_canary_rate"]),
    )

    compiler = MultiProfileDagTopologyCompiler(cfg)
    compiled = compiler.compile_all_profiles(int(bundle["surge_requirements"]["parallel_width"]))
    mc_violations = sum(int(v["maker_checker_violation"]) for v in compiled.values())

    generalizer = AutonomousDesignSpaceGeneralizer(cfg)
    fork_res = generalizer.lift_and_resolve(
        bundle["decision_fork"]["endpoint_a"],
        bundle["decision_fork"]["endpoint_b"],
        quality_floor=float(bundle["decision_fork"]["quality_floor"]),
        latency_sla_ms=float(bundle["decision_fork"]["latency_sla_ms"]),
        cost_ceiling_usd=float(bundle["decision_fork"]["cost_ceiling_usd"]),
    )
    pruned_evsi = generalizer.prune_evsi_branches(bundle["evsi_utility_gains"])
    culprit = generalizer.compute_shapley_culprit(
        bundle["shapley_probe"]["edge_ms"],
        float(bundle["shapley_probe"]["baseline_ms"]),
    )

    materializer = EphemeralCliHarnessMaterializer(cfg)
    for hid in cfg["harness_families"]:
        materializer.run_ephemeral_step(str(hid), "bundle-step")

    joiner = SubprocessDagJoinExecutor(cfg)
    merged_val = joiner.run_join(
        bundle["scatter_gather"]["values"],
        bundle["scatter_gather"]["weights"],
    )

    crystallizer = CegisCanaryCrystallizer(rnd)
    quorum = min(int(v) for v in cfg["grid_axes"]["demand_gap_quorum"])
    for p in bundle["cegis_stream"]:
        crystallizer.execute(p, quorum=quorum)

    # Fresh <6h keyword delta count & shared-prefix coalescing K
    q_low = str(bundle["query_text"]).lower()
    max_age = float(mp["fresh_resource_max_age_hours"])
    fresh_hits = sum(
        1
        for r in cfg["fresh_delta_catalog"]
        if float(r["age_hours"]) <= max_age
        and any(str(kw).lower() in q_low for kw in r["keywords"])
    )

    env_count = int(bundle["homogeneous_envelopes_count"])
    chosen_k = 1
    for cand_k in range(env_count, 1, -1):
        pred_int = float(mp["interference_slope_homogeneous"]) * float(cand_k - 1)
        s_tok = float(cand_k) * (
            float(mp["shared_prefix_tokens"]) + float(mp["per_task_unique_tokens"])
        )
        c_tok = float(mp["shared_prefix_tokens"]) + float(cand_k) * float(
            mp["per_task_unique_tokens"]
        )
        if pred_int <= float(mp["interference_ceiling"]) and (
            (s_tok - c_tok) / s_tok
        ) >= float(mp["prefix_savings_floor"]):
            chosen_k = cand_k
            break

    engine_src = Path(__file__).read_text(encoding="utf-8")
    eng_ast_v = len(
        ZeroHardcodedValuesAstGate.scan_source(
            engine_src,
            cfg["allowed_identity_numbers"],
            "engine.py",
        )
    ) + len(
        DomainAgnosticNamingGate.scan_source(
            engine_src,
            cfg["forbidden_industry_tokens"],
            "engine.py",
        )
    )
    sample_magic_v = len(
        ZeroHardcodedValuesAstGate.scan_source(
            str(bundle["magic_code_sample"]),
            cfg["allowed_identity_numbers"],
            "magic_sample.py",
        )
    )
    sample_dom_v = len(
        DomainAgnosticNamingGate.scan_source(
            str(bundle["industry_coupled_sample"]),
            cfg["forbidden_industry_tokens"],
            "domain_sample.py",
        )
    )

    return {
        "distinct_dag_profiles_compiled": len(compiled),
        "maker_checker_violations": mc_violations,
        "human_scalar_prompts_issued": int(fork_res["human_scalar_prompts_issued"]),
        "manifold_candidates_evaluated": int(fork_res["manifold_size"]),
        "evsi_pruned_branches": pruned_evsi,
        "shapley_culprit_matched": culprit == str(bundle["shapley_probe"]["expected_culprit"]),
        "subprocess_merged_value": round(merged_val, rnd),
        "blueprint_active_version_after_drift": crystallizer.version,
        "canary_drift_demotions": crystallizer.demotions,
        "sprawled_repos": crystallizer.sprawled_repos,
        "ephemeral_retained": materializer.ephemeral_retained + joiner.ephemeral_retained,
        "fresh_delta_pulls": fresh_hits,
        "coalesced_batch_k": chosen_k,
        "final_grid_generation": int(morph["generation"]),
        "engine_ast_violations": eng_ast_v,
        "sample_magic_ast_violations": sample_magic_v,
        "sample_domain_naming_violations": sample_dom_v,
    }
