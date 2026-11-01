"""Composable topological Verifier DAG, Checks-of-Checks Mutation Gate, and negative_tombstone extractor."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import deque
from typing import Any, Callable

from .grid import resolve_grid_cell

ISO_TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b")
HEX_ID_RE = re.compile(r"\b[0-9a-f]{8,64}\b")
LINE_NUM_RE = re.compile(r"\bline\s+\d+\b", re.IGNORECASE)


class ComposableVerifierDagAndMutationGate:
    """Executes topological pre_submit verifier DAGs, audits verifier sensitivity, and extracts tombstones."""

    def __init__(
        self,
        grid_overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.cell, self.constants = resolve_grid_cell(grid_overrides, regime=regime, spec=spec)

    @staticmethod
    def canonical_sha256(payload: Any) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def topological_order(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort verifier nodes topologically via Kahn's algorithm; raise ValueError on cycles."""
        by_id = {str(n["id"]): n for n in nodes}
        if len(by_id) != len(nodes):
            raise ValueError("duplicate verifier node id")
        in_deg: dict[str, int] = {nid: 0 for nid in by_id}
        children: dict[str, list[str]] = {nid: [] for nid in by_id}
        for nid, node in by_id.items():
            for dep in node.get("depends_on", []):
                dep_s = str(dep)
                if dep_s not in by_id:
                    raise ValueError(f"unknown dependency {dep_s} for {nid}")
                in_deg[nid] += 1
                children[dep_s].append(nid)

        ready = deque(sorted(nid for nid, deg in in_deg.items() if deg == 0))
        ordered: list[dict[str, Any]] = []
        while ready:
            cur = ready.popleft()
            ordered.append(by_id[cur])
            for nxt in sorted(children[cur]):
                in_deg[nxt] -= 1
                if in_deg[nxt] == 0:
                    ready.append(nxt)
        if len(ordered) != len(nodes):
            raise ValueError("cycle detected in verifier DAG")
        return ordered

    def _check_json_schema(self, schema: dict[str, Any], value: Any, path: str = "$") -> list[str]:
        errs: list[str] = []
        expected_type = schema.get("type")
        if expected_type == "object" and not isinstance(value, dict):
            return [f"{path}: expected object"]
        if expected_type == "array" and not isinstance(value, list):
            return [f"{path}: expected array"]
        if expected_type == "string" and not isinstance(value, str):
            return [f"{path}: expected string"]
        if expected_type == "boolean" and not isinstance(value, bool):
            return [f"{path}: expected boolean"]
        if expected_type == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            return [f"{path}: expected integer"]
        if expected_type == "number" and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
        ):
            return [f"{path}: expected number"]

        if "enum" in schema and value not in schema["enum"]:
            errs.append(f"{path}: value not in enum")
        if isinstance(value, str):
            if "minLength" in schema and len(value) < int(schema["minLength"]):
                errs.append(f"{path}: string shorter than minLength")
            if "maxLength" in schema and len(value) > int(schema["maxLength"]):
                errs.append(f"{path}: string longer than maxLength")
            if "pattern" in schema and re.search(str(schema["pattern"]), value) is None:
                errs.append(f"{path}: string does not match pattern")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and float(value) < float(schema["minimum"]):
                errs.append(f"{path}: number below minimum")
            if "maximum" in schema and float(value) > float(schema["maximum"]):
                errs.append(f"{path}: number above maximum")
        if isinstance(value, list) and "items" in schema:
            for idx, item in enumerate(value):
                errs.extend(self._check_json_schema(schema["items"], item, f"{path}[{idx}]"))
        if isinstance(value, dict):
            props = schema.get("properties", {})
            for req in schema.get("required", []):
                if req not in value:
                    errs.append(f"{path}: missing required field {req}")
            if schema.get("additionalProperties") is False:
                for extra in sorted(set(value) - set(props)):
                    errs.append(f"{path}: unexpected field {extra}")
            for field_name, sub_schema in props.items():
                if field_name in value:
                    errs.extend(self._check_json_schema(sub_schema, value[field_name], f"{path}.{field_name}"))
        return errs

    def run_single_verifier(self, node: dict[str, Any], submission: dict[str, Any]) -> dict[str, Any]:
        """Execute one deterministic verifier node against submission payload."""
        round_d = int(self.constants["round_digits"])
        vtype = str(node["verifier_type"])

        if vtype == "json_schema_conformance":
            schema = node["schema"]
            target = submission.get("payload", {})
            errs = self._check_json_schema(schema, target)
            return {
                "passed": len(errs) == 0,
                "reason": "ok" if not errs else "; ".join(errs),
            }

        if vtype == "sha256_pin_integrity":
            hex_len = int(self.constants["sha256_hex_length"])
            pins = submission.get("pins", [])
            if not pins:
                return {"passed": False, "reason": "no artifact pins provided"}
            for pin in pins:
                declared = str(pin.get("declared_sha256", ""))
                actual = self.canonical_sha256(pin.get("artifact_value"))
                if len(declared) != hex_len or declared != actual:
                    return {
                        "passed": False,
                        "reason": f"pin digest mismatch for {pin.get('key', 'unknown')}",
                    }
            return {"passed": True, "reason": "all pin digests verified"}

        if vtype == "human_only_boundary_check":
            is_human_only = bool(submission.get("human_only", False))
            claimant = str(submission.get("claimant", "agent"))
            model_calls = int(submission.get("model_calls", 0))
            if is_human_only and (claimant != "human" or model_calls != 0):
                return {
                    "passed": False,
                    "reason": "human_only task requires human claimant and zero model calls",
                }
            return {"passed": True, "reason": "human_only boundary respected"}

        if vtype == "multi_principal_publication_check":
            drafter_w = str(submission.get("drafter_worker_id", "")).strip()
            reviewer_w = str(submission.get("reviewer_worker_id", "")).strip()
            drafter_k = str(submission.get("drafter_key_id", "")).strip()
            reviewer_k = str(submission.get("reviewer_key_id", "")).strip()
            anon_prefixes = tuple(str(p) for p in self.constants["anonymous_key_prefixes"])
            for key_val in (drafter_k, reviewer_k):
                if not key_val or key_val == "anonymous" or key_val.startswith(anon_prefixes):
                    return {
                        "passed": False,
                        "reason": "anonymous or missing principal key forbidden for publication",
                    }
            if not drafter_w or not reviewer_w or drafter_w == reviewer_w or drafter_k == reviewer_k:
                return {
                    "passed": False,
                    "reason": "drafter and reviewer must have distinct worker_id and key_id",
                }
            return {"passed": True, "reason": "multi-principal distinct attestation verified"}

        if vtype == "paired_bootstrap_delta_check":
            base = [float(x) for x in submission.get("baseline_scores", [])]
            cand = [float(x) for x in submission.get("candidate_scores", [])]
            if not base or len(base) != len(cand):
                return {"passed": False, "reason": "paired scores must be non-empty and equal length"}
            n_items = len(base)
            deltas = [c_val - b_val for b_val, c_val in zip(base, cand)]
            mean_delta = sum(deltas) / float(n_items)
            resamples = int(self.cell["bootstrap_resamples"])
            slice_chars = int(self.constants["digest_slice_chars"])
            radix = int(self.constants["hex_radix"])
            boot_means: list[float] = []
            for rep_idx in range(resamples):
                acc = 0.0
                for slot_idx in range(n_items):
                    seed_bytes = f"boot:{rep_idx}:{slot_idx}".encode("utf-8")
                    pick = int(hashlib.sha256(seed_bytes).hexdigest()[:slice_chars], radix) % n_items
                    acc += deltas[pick]
                boot_means.append(acc / float(n_items))
            boot_means.sort()
            low_idx = max(0, int(float(resamples) * float(self.cell["bootstrap_lower_quantile"])))
            ci_lower = boot_means[low_idx]
            min_mean = float(node.get("min_mean_delta", self.cell["min_mean_delta"]))
            min_ci = float(node.get("min_delta_ci_lower", self.cell["min_delta_ci_lower"]))
            ok = mean_delta >= min_mean and ci_lower >= min_ci
            return {
                "passed": ok,
                "mean_delta": round(mean_delta, round_d),
                "ci_lower": round(ci_lower, round_d),
                "reason": "paired bootstrap passed" if ok else "paired bootstrap below delta or CI floor",
            }

        raise ValueError(f"unsupported verifier_type: {vtype}")

    def execute_verifier_dag(
        self,
        nodes: list[dict[str, Any]],
        submission: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute topological verifier DAG, skipping dependents when an upstream check fails."""
        ordered = self.topological_order(nodes)
        results: dict[str, dict[str, Any]] = {}
        execution_order: list[str] = []
        failed_ids: list[str] = []
        skipped_ids: list[str] = []

        for node in ordered:
            nid = str(node["id"])
            execution_order.append(nid)
            deps = [str(d) for d in node.get("depends_on", [])]
            if any(not results[d]["passed"] for d in deps):
                results[nid] = {
                    "passed": False,
                    "status": "skipped_dependency_failed",
                    "reason": "upstream dependency failed",
                }
                skipped_ids.append(nid)
                continue
            outcome = self.run_single_verifier(node, submission)
            status = "passed" if outcome["passed"] else "failed"
            results[nid] = {**outcome, "status": status}
            if not outcome["passed"]:
                failed_ids.append(nid)

        return {
            "all_passed": len(failed_ids) == 0 and len(skipped_ids) == 0,
            "execution_order": execution_order,
            "failed_verifiers": failed_ids,
            "skipped_verifiers": skipped_ids,
            "results": results,
        }

    def audit_verifier_sensitivity(
        self,
        verifier_fn: Callable[[dict[str, Any]], bool],
        *,
        clean_twins: list[dict[str, Any]],
        mutated_negatives: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Checks-of-Checks mutation gate classifying a verifier as trusted | revise | reject."""
        round_d = int(self.constants["round_digits"])
        if not clean_twins or not mutated_negatives:
            raise ValueError("clean_twins and mutated_negatives must both be non-empty")

        false_positives = sum(1 for item in clean_twins if not bool(verifier_fn(item)))
        killed_mutations = sum(1 for item in mutated_negatives if not bool(verifier_fn(item)))

        clean_fp_rate = float(false_positives) / float(len(clean_twins))
        kill_rate = float(killed_mutations) / float(len(mutated_negatives))

        max_fp = float(self.cell["max_clean_fp_rate"])
        min_trusted = float(self.cell["min_trusted_kill_rate"])
        min_non_trivial = float(self.cell["min_non_trivial_kill_rate"])

        if clean_fp_rate > max_fp or kill_rate < min_non_trivial:
            classification = "reject"
        elif kill_rate < min_trusted:
            classification = "revise"
        else:
            classification = "trusted"

        return {
            "classification": classification,
            "clean_false_positive_rate": round(clean_fp_rate, round_d),
            "mutation_kill_rate": round(kill_rate, round_d),
            "clean_tested": len(clean_twins),
            "mutations_tested": len(mutated_negatives),
            "mutations_killed": killed_mutations,
        }

    def extract_negative_tombstone(
        self,
        *,
        failed_stage: str,
        approach_label: str,
        failed_verifiers: list[str],
        raw_diagnostics: list[str],
    ) -> dict[str, Any]:
        """Normalize failure diagnostics into a deterministic dead-end negative_tombstone signature."""
        normalized_lines: list[str] = []
        for diag in raw_diagnostics:
            cleaned = ISO_TS_RE.sub("<ts>", str(diag))
            cleaned = HEX_ID_RE.sub("<hex>", cleaned)
            cleaned = LINE_NUM_RE.sub("line <n>", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
            if cleaned:
                normalized_lines.append(cleaned)

        canonical_sig = "|".join(
            [
                failed_stage.strip().lower(),
                approach_label.strip().lower(),
                ",".join(sorted(str(v) for v in failed_verifiers)),
                ";".join(sorted(set(normalized_lines))),
            ]
        )
        prefix_len = int(self.constants["tombstone_prefix_chars"])
        digest = hashlib.sha256(canonical_sig.encode("utf-8")).hexdigest()[:prefix_len]
        return {
            "tombstone_id": f"tombstone:{digest}",
            "failed_stage": failed_stage,
            "approach_label": approach_label,
            "failed_verifiers": sorted(str(v) for v in failed_verifiers),
            "normalized_signature": canonical_sig,
            "do_not_repeat_hint": f"Avoid {approach_label}: failed {', '.join(sorted(failed_verifiers))} during {failed_stage}.",
        }
