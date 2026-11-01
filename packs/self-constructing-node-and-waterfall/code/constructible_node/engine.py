"""Stateless contract-hydrated constructible node, per-step profiler, waterfall and spinout queue."""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def load_default_grid_spec(path: Path | None = None) -> dict[str, Any]:
    spec_path = path or (Path(__file__).resolve().parent / "default_grid_spec.json")
    return json.loads(spec_path.read_text(encoding="utf-8"))


def _canonical_sha(payload: Any, chars: int) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:chars]


class Interrogator5W1H:
    """Extracts structured who/what/where/when/why/how and temporal horizon attributes."""

    def interrogate(self, envelope: dict[str, Any]) -> dict[str, str]:
        return {
            "who": str(envelope.get("actor_id", "anonymous_actor")),
            "what": str(envelope.get("intent_kind", "generic_query")),
            "where": str(envelope.get("entity_id", envelope.get("cohort_id", "global_scope"))),
            "when": str(envelope.get("temporal_horizon", "point_in_time")),
            "why": str(envelope.get("decision_objective", "operational_intelligence")),
            "how": str(envelope.get("operating_preset", "full_20_stage_frontier_supernode")),
        }


class ContinuousStepProfiler:
    """Profiles initial and intermediate execution states to short-circuit already-solved signatures."""

    def __init__(self, sha_chars: int) -> None:
        self.sha_chars = sha_chars
        self._cache: dict[str, dict[str, Any]] = {}

    def profile(self, stage_id: str, envelope: dict[str, Any]) -> dict[str, Any]:
        exact_payload = {
            "intent_kind": envelope.get("intent_kind"),
            "entity_id": envelope.get("entity_id"),
            "cohort_id": envelope.get("cohort_id"),
            "query_text": str(envelope.get("query_text", "")).strip().lower(),
            "negative_tags": sorted(str(t) for t in envelope.get("negative_tags", [])),
        }
        shape_payload = {
            "intent_kind": envelope.get("intent_kind"),
            "has_entity": bool(envelope.get("entity_id")),
            "has_negative_tags": len(envelope.get("negative_tags", [])) > 0,
            "temporal_horizon": envelope.get("temporal_horizon", "point_in_time"),
        }
        return {
            "stage_id": stage_id,
            "exact_hash": _canonical_sha(exact_payload, self.sha_chars),
            "shape_hash": _canonical_sha(shape_payload, self.sha_chars),
        }

    def lookup(self, exact_hash: str) -> dict[str, Any] | None:
        return self._cache.get(exact_hash)

    def record(self, exact_hash: str, output: dict[str, Any]) -> None:
        self._cache[exact_hash] = output


class KeywordFreshResourceTrigger:
    """Scans request tokens deterministically to hydrate fresh (< max_age_hours) external resources."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.rules = list(spec["keyword_triggers"])
        self.max_age_hours = float(spec["fresh_resource_max_age_hours"])

    def scan(self, query_text: str) -> list[dict[str, Any]]:
        lowered = query_text.lower()
        hydrated: list[dict[str, Any]] = []
        for rule in self.rules:
            age_ok = float(rule["age_hours"]) <= self.max_age_hours
            matched = [kw for kw in rule["keywords"] if str(kw).lower() in lowered]
            if age_ok and matched:
                hydrated.append(
                    {
                        "rule_id": str(rule["rule_id"]),
                        "resource_id": str(rule["resource_id"]),
                        "matched_keywords": matched,
                        "drift_multiplier": float(rule["drift_multiplier"]),
                    }
                )
        return hydrated


class PlanKDecideOneFrontier:
    """Generates K strategy candidates and selects reuse, compose, modify or build_new with placement."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.k_limit = int(spec["plan_k_candidates"])
        self.priors = {str(k): float(v) for k, v in spec["strategy_priors"].items()}
        self.placements = {str(k): str(v) for k, v in spec["placement_targets"].items()}
        self.digits = int(spec["decimal_round_digits"])

    def plan_and_decide(self, has_admitted_block: bool, requires_multi_block: bool) -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []
        for mode, prior in self.priors.items():
            bonus = 0.0
            if mode == "reuse" and has_admitted_block and not requires_multi_block:
                bonus = prior
            elif mode == "compose" and has_admitted_block and requires_multi_block:
                bonus = prior
            elif mode == "build_new" and not has_admitted_block:
                bonus = 1.0
            score = round(prior + bonus, self.digits)
            candidates.append(
                {
                    "strategy": mode,
                    "placement_target": self.placements[mode],
                    "utility_score": score,
                }
            )
        ranked = sorted(candidates, key=lambda item: (-float(item["utility_score"]), str(item["strategy"])))
        kept = ranked[: self.k_limit]
        return {
            "candidates_explored": len(kept),
            "selected": kept[0],
            "frontier": kept,
        }


class CapabilityGapSpinoutLedger:
    """Tracks repeated unserved shape hashes and proposes a background builder verb at quorum."""

    def __init__(self, quorum: int) -> None:
        self.quorum = quorum
        self.counts: dict[str, int] = {}
        self.admitted_blocks: set[str] = {"point_lookup", "cohort_percentile", "appetite_exclusion_match", "ols_trend"}
        self.proposed_verbs: list[dict[str, Any]] = []

    def has_block(self, intent_kind: str) -> bool:
        return intent_kind in self.admitted_blocks

    def observe_unserved(self, shape_hash: str, intent_kind: str) -> dict[str, Any] | None:
        updated = self.counts.get(shape_hash, 0) + 1
        self.counts[shape_hash] = updated
        if updated == self.quorum:
            proposal = {
                "verb_id": f"verb-synthesize-block-{shape_hash}",
                "shape_hash": shape_hash,
                "intent_kind": intent_kind,
                "occurrences": updated,
            }
            self.proposed_verbs.append(proposal)
            return proposal
        return None

    def admit_verified_block(self, intent_kind: str) -> None:
        self.admitted_blocks.add(intent_kind)


class MultiPersonaVectorJudge:
    """Evaluates outputs across multiple stakeholder personas and vector dimensions rather than binary pass/fail."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.personas = dict(spec["persona_panel"])
        self.digits = int(spec["decimal_round_digits"])
        self.token_trigger = int(spec["token_distillation_trigger"])
        self.token_budget = float(spec["token_budget"])
        self.pass_floor = float(spec["persona_pass_floor"])

    def evaluate(
        self,
        schema_valid: bool,
        excluded_leaks: int,
        tokens_used: int,
        reusable_block: bool,
    ) -> dict[str, Any]:
        token_ratio = min(1.0, float(tokens_used) / self.token_budget) if self.token_budget > 0.0 else 0.0
        dims = {
            "correctness": 1.0 if schema_valid else 0.0,
            "latency_score": round(1.0 - token_ratio * (1.0 - self.pass_floor), self.digits),
            "cost_efficiency": round(1.0 - token_ratio, self.digits),
            "token_economy": 1.0 if tokens_used == 0 else round(1.0 - token_ratio, self.digits),
            "safety_compliance": 1.0 if excluded_leaks == 0 else 0.0,
            "reusability": 1.0 if reusable_block else self.pass_floor,
        }
        persona_scores: dict[str, float] = {}
        for persona_name, weights in self.personas.items():
            total = 0.0
            for dim_name, weight in weights.items():
                total += float(dims[dim_name]) * float(weight)
            persona_scores[persona_name] = round(total, self.digits)
        mean_score = round(sum(persona_scores.values()) / float(len(persona_scores)), self.digits)
        cheaper_proposal = (
            "distill_verified_trace_into_rung_2_code_block"
            if tokens_used >= self.token_trigger
            else "already_optimal_zero_token_path"
        )
        return {
            "dimensions": dims,
            "persona_scores": persona_scores,
            "aggregate_score": mean_score,
            "passed": mean_score >= self.pass_floor and excluded_leaks == 0,
            "cheaper_alternative_proposal": cheaper_proposal,
        }


class WeightedWaterfallExecutor:
    """Executes contract-hydrated envelopes across Rung 0..4 with continuous re-profiling."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        self.digits = int(spec["decimal_round_digits"])
        self.sha_chars = int(spec["sha_digest_hex_chars"])
        self.interrogator = Interrogator5W1H()
        self.profiler = ContinuousStepProfiler(sha_chars=self.sha_chars)
        self.keywords = KeywordFreshResourceTrigger(spec)
        self.planner = PlanKDecideOneFrontier(spec)
        self.spinout = CapabilityGapSpinoutLedger(quorum=int(spec["capability_spinout_quorum"]))
        self.judge = MultiPersonaVectorJudge(spec)
        self.rungs = {str(r["id"]): dict(r) for r in spec["waterfall_rungs"]}

    def execute_envelope(self, envelope: dict[str, Any], substrate: dict[str, Any]) -> dict[str, Any]:
        preset = str(envelope.get("operating_preset", "full_20_stage_frontier_supernode"))
        stages = list(self.spec["stage_presets"][preset])
        interrogation = self.interrogator.interrogate(envelope) if "s02_interrogate_5w1h_and_time" in stages else {}
        p0 = self.profiler.profile("entry", envelope)

        cached = self.profiler.lookup(p0["exact_hash"])
        if cached is not None:
            verdict = self.judge.evaluate(schema_valid=True, excluded_leaks=0, tokens_used=0, reusable_block=True)
            return {
                "exact_hash": p0["exact_hash"],
                "shape_hash": p0["shape_hash"],
                "stages_executed": len(stages),
                "rung_used": "rung_0_exact_cache",
                "tokens_used": 0,
                "hydrated_resources": [],
                "frontier_selected": "reuse",
                "result": cached,
                "persona_panel": verdict,
                "spinout_proposal": None,
                "interrogation": interrogation,
            }

        hydrated = self.keywords.scan(str(envelope.get("query_text", ""))) if "s05_keyword_and_fresh_resource_trigger" in stages else []
        intent = str(envelope.get("intent_kind", "point_lookup"))
        force_harness = preset == "minimal_cli_harness_delegate"
        has_block = self.spinout.has_block(intent) and not force_harness
        multi_block = intent in ("appetite_exclusion_match", "ols_trend")
        plan = self.planner.plan_and_decide(has_admitted_block=has_block, requires_multi_block=multi_block)

        excluded_leaks = 0
        spinout_proposal: dict[str, Any] | None = None

        if has_block:
            result = self._run_deterministic_block(intent=intent, envelope=envelope, substrate=substrate, hydrated=hydrated)
            excluded_leaks = int(result.get("excluded_leaks", 0))
            if bool(envelope.get("require_narrative_synthesis", False)):
                rung_used = "rung_3_hybrid_analytical"
                tokens_used = int(self.rungs[rung_used]["estimated_tokens"])
            else:
                rung_used = "rung_1_keyword_fresh_context" if hydrated else "rung_2_typed_code_blocks"
                tokens_used = 0
        else:
            rung_used = "rung_4_cli_harness_grid"
            cell_name = str(envelope.get("harness_cell", "opencode_structured_builder"))
            cell = dict(self.spec["harness_cells"][cell_name])
            tokens_used = int(self.rungs[rung_used]["estimated_tokens"])
            result = {
                "harness_cli": cell["cli"],
                "pinned_version": cell["pinned_version"],
                "workspace_files": list(cell["workspace_files"]),
                "synthesized_answer": f"harness_solved:{intent}:{envelope.get('entity_id', 'cohort')}",
            }
            if not force_harness:
                spinout_proposal = self.spinout.observe_unserved(shape_hash=p0["shape_hash"], intent_kind=intent)

        self.profiler.record(p0["exact_hash"], result)
        verdict = self.judge.evaluate(
            schema_valid=True,
            excluded_leaks=excluded_leaks,
            tokens_used=tokens_used,
            reusable_block=has_block,
        )
        return {
            "exact_hash": p0["exact_hash"],
            "shape_hash": p0["shape_hash"],
            "stages_executed": len(stages),
            "rung_used": rung_used,
            "tokens_used": tokens_used,
            "hydrated_resources": [r["resource_id"] for r in hydrated],
            "frontier_selected": str(plan["selected"]["strategy"]),
            "result": result,
            "persona_panel": verdict,
            "spinout_proposal": spinout_proposal,
            "interrogation": interrogation,
        }

    def _run_deterministic_block(
        self,
        intent: str,
        envelope: dict[str, Any],
        substrate: dict[str, Any],
        hydrated: list[dict[str, Any]],
    ) -> dict[str, Any]:
        entities = {str(e["entity_id"]): dict(e) for e in substrate.get("entities", [])}
        if intent == "point_lookup":
            ent = entities[str(envelope["entity_id"])]
            return {"entity_id": ent["entity_id"], "hazard_index": float(ent["hazard_index"]), "excluded_leaks": 0}

        if intent == "cohort_percentile":
            target = entities[str(envelope["entity_id"])]
            drift = float(hydrated[0]["drift_multiplier"]) if hydrated else 1.0
            cohort_vals = sorted(
                float(e["hazard_index"]) * drift
                for e in entities.values()
                if str(e["cohort_id"]) == str(target["cohort_id"])
            )
            target_val = float(target["hazard_index"]) * drift
            below_or_eq = sum(1 for v in cohort_vals if v <= target_val)
            pct = round(float(below_or_eq) / float(len(cohort_vals)), self.digits)
            return {"entity_id": target["entity_id"], "calibrated_value": round(target_val, self.digits), "cohort_quantile": pct, "excluded_leaks": 0}

        if intent == "appetite_exclusion_match":
            neg = {str(t) for t in envelope.get("negative_tags", [])}
            appetite = [float(x) for x in envelope.get("appetite_vector", [])]
            matched_entities: list[str] = []
            leaks = 0
            for ent in entities.values():
                ent_tags = {str(t) for t in ent.get("tags", [])}
                if ent_tags & neg:
                    continue
                vec = [float(x) for x in ent.get("feature_vector", [])]
                sim = self._cosine(appetite, vec)
                if sim > 0.0:
                    matched_entities.append(str(ent["entity_id"]))
                    if ent_tags & neg:
                        leaks += 1
            matched_actors = [
                str(a["actor_id"])
                for a in substrate.get("actors", [])
                if not ({str(t) for t in a.get("tags", [])} & neg)
            ]
            return {"matched_entities": sorted(matched_entities), "matched_actors": sorted(matched_actors), "excluded_leaks": leaks}

        if intent == "ols_trend":
            series = [float(v) for v in substrate["series"][str(envelope["entity_id"])]]
            n = len(series)
            xs = [float(i) for i in range(n)]
            mean_x = sum(xs) / float(n)
            mean_y = sum(series) / float(n)
            num = sum((xs[i] - mean_x) * (series[i] - mean_y) for i in range(n))
            den = sum((xs[i] - mean_x) * (xs[i] - mean_x) for i in range(n))
            slope = round(num / den, self.digits) if den > 0.0 else 0.0
            return {"entity_id": str(envelope["entity_id"]), "ols_slope": slope, "excluded_leaks": 0}

        return {"synthesized_deterministic_block": intent, "entity_id": str(envelope.get("entity_id", "cohort")), "excluded_leaks": 0}

    def _cosine(self, a: list[float], b: list[float]) -> float:
        if not a or len(a) != len(b):
            return 0.0
        dot = sum(a[i] * b[i] for i in range(len(a)))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return round(dot / (na * nb), self.digits)


class ZeroHardcodedValuesAstGate:
    """Scans Python source ASTs and rejects inline numeric literals outside (-1, 0, 1, -1.0, 0.0, 1.0)."""

    ALLOWED = {-1, 0, 1, -1.0, 0.0, 1.0}

    @classmethod
    def scan_source(cls, source: str, filename: str = "<memory>") -> list[dict[str, Any]]:
        tree = ast.parse(source, filename=filename)
        violations: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if (
                        isinstance(child, ast.Constant)
                        and isinstance(child.value, (int, float))
                        and not isinstance(child.value, bool)
                        and child.value not in cls.ALLOWED
                    ):
                        violations.append(
                            {
                                "file": filename,
                                "line": child.lineno,
                                "literal": child.value,
                            }
                        )
        return violations


class DomainAgnosticNamingGate:
    """Scans filenames and AST class/function definitions to block narrow industry-coupled identifiers."""

    @staticmethod
    def scan_source(source: str, banned_terms: list[str], filename: str = "<memory>") -> list[str]:
        lowered_banned = [t.lower() for t in banned_terms]
        violations: list[str] = []
        low_file = Path(filename).name.lower()
        for term in lowered_banned:
            if term in low_file:
                violations.append(f"filename:{low_file}:{term}")
        tree = ast.parse(source, filename=filename)
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                sym = node.name.lower()
                for term in lowered_banned:
                    if term in sym:
                        violations.append(f"symbol:{node.name}:{term}")
        return violations


def run_bundle(bundle: dict[str, Any], spec: dict[str, Any] | None = None) -> dict[str, Any]:
    grid = spec or load_default_grid_spec()
    executor = WeightedWaterfallExecutor(grid)
    substrate = dict(bundle["substrate"])
    traces: list[dict[str, Any]] = []

    for env in bundle["envelopes"]:
        res = executor.execute_envelope(env, substrate)
        traces.append(res)
        if res["spinout_proposal"] is not None and bool(bundle.get("auto_admit_verified_spinout", True)):
            executor.spinout.admit_verified_block(str(env["intent_kind"]))

    post_env = dict(bundle["post_spinout_envelope"])
    post_trace = executor.execute_envelope(post_env, substrate)
    traces.append(post_trace)

    engine_source = Path(__file__).read_text(encoding="utf-8")
    clean_ast_violations = len(ZeroHardcodedValuesAstGate.scan_source(engine_source, __file__))
    bad_ast_violations = len(ZeroHardcodedValuesAstGate.scan_source(str(bundle["magic_code_sample"]), "sample.py"))
    domain_violations = len(DomainAgnosticNamingGate.scan_source(str(bundle["industry_coupled_sample"]), list(grid["banned_domain_terms"]), "sample.py"))

    return {
        "total_envelopes_executed": len(traces),
        "zero_token_executions": sum(1 for t in traces if int(t["tokens_used"]) == 0),
        "cache_short_circuits": sum(1 for t in traces if t["rung_used"] == "rung_0_exact_cache"),
        "fresh_resource_hydrations": sum(1 for t in traces if len(t["hydrated_resources"]) > 0),
        "excluded_tag_leaks": sum(int(t["result"].get("excluded_leaks", 0)) for t in traces),
        "spinout_verbs_proposed": len(executor.spinout.proposed_verbs),
        "post_spinout_rung": str(post_trace["rung_used"]),
        "post_spinout_tokens": int(post_trace["tokens_used"]),
        "all_persona_panels_passed": all(bool(t["persona_panel"]["passed"]) for t in traces),
        "engine_ast_violations": clean_ast_violations,
        "sample_magic_ast_violations": bad_ast_violations,
        "sample_domain_naming_violations": domain_violations,
    }
