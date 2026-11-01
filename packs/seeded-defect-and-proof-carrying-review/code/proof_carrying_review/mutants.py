"""Deterministic 6-class seeded defect mutant injector and AST/invariant check suite."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from typing import Any

from .grid import resolve_grid_cell


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SeededDefectMutantSuite:
    """Injects 6 universal classes of defects and runs deterministic witness-producing checks."""

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
        self.defect_classes: list[str] = list(self.constants["defect_classes"])
        self.defect_to_check: dict[str, str] = dict(self.constants["defect_to_check_id"])
        self.effect_order: dict[str, int] = {
            str(k): int(v) for k, v in self.constants["effect_order"].items()
        }

    def inject_mutant(self, clean_bundle: dict[str, Any], defect_class: str) -> dict[str, Any]:
        """Return a mutated copy of clean_bundle carrying one deterministic seeded defect."""
        if defect_class not in self.defect_to_check:
            raise ValueError(f"unsupported defect_class: {defect_class!r}")
        mutated = copy.deepcopy(clean_bundle)
        if defect_class == "digest_mismatch":
            orig = str(mutated["artifact"]["declared_sha256"])
            replacement_char = "0" if orig[0] != "0" else "f"
            mutated["artifact"]["declared_sha256"] = replacement_char + orig[1:]
        elif defect_class == "boundary_off_by_one":
            limit_val = int(mutated["boundary"]["max_allowed"])
            mutated["boundary"]["observed"] = limit_val + 1
        elif defect_class == "silent_exception_swallow":
            snippet = str(mutated.get("code_snippet", ""))
            mutated["code_snippet"] = snippet + str(self.constants["mutated_swallow_snippet"])
        elif defect_class == "capability_tier_violation":
            mutated["capability"]["requested_effect"] = str(
                self.constants["mutated_effect_escalation"]
            )
        elif defect_class == "self_approval_principal_reuse":
            mutated["attestation"]["reviewer_principal"] = mutated["attestation"]["drafter_principal"]
            mutated["attestation"]["reviewer_key_id"] = mutated["attestation"]["drafter_key_id"]
        elif defect_class == "ungrounded_citation_span":
            mutated["citations"][0]["exact_quote"] = (
                str(mutated["citations"][0]["exact_quote"])
                + str(self.constants["mutated_quote_suffix"])
            )
        return mutated

    def generate_twin_suite(self, clean_bundles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate all 6 seeded-defect mutants for each clean bundle."""
        records: list[dict[str, Any]] = []
        for idx, clean in enumerate(clean_bundles):
            cid = str(clean.get("bundle_id", f"clean-{idx}"))
            for defect in self.defect_classes:
                records.append(
                    {
                        "mutant_id": f"{cid}::{defect}",
                        "source_bundle_id": cid,
                        "defect_class": defect,
                        "expected_failing_check": self.defect_to_check[defect],
                        "bundle": self.inject_mutant(clean, defect),
                    }
                )
        return records

    @staticmethod
    def _find_silent_swallow_line(code_snippet: str) -> int | None:
        tree = ast.parse(code_snippet)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    return int(node.lineno)
        return None

    def run_checks(self, candidate: dict[str, Any]) -> list[dict[str, Any]]:
        """Run all 6 deterministic checks on candidate and emit reproducible witnesses."""
        results: list[dict[str, Any]] = []

        # 1. Digest integrity
        art = candidate.get("artifact", {})
        actual_sha = canonical_sha256(art.get("payload", {}))
        declared_sha = str(art.get("declared_sha256", ""))
        ok_digest = actual_sha == declared_sha
        results.append(
            {
                "check_id": "chk_digest_integrity",
                "passed": ok_digest,
                "witness": "" if ok_digest else f"declared={declared_sha}!=actual={actual_sha}",
            }
        )

        # 2. Boundary invariant
        bnd = candidate.get("boundary", {})
        obs = int(bnd.get("observed", 0))
        lim = int(bnd.get("max_allowed", 0))
        ok_bound = obs <= lim
        results.append(
            {
                "check_id": "chk_boundary_invariant",
                "passed": ok_bound,
                "witness": "" if ok_bound else f"observed={obs}>max_allowed={lim}",
            }
        )

        # 3. Silent exception swallow (AST check)
        code_src = str(candidate.get("code_snippet", ""))
        swallow_line = self._find_silent_swallow_line(code_src)
        ok_ast = swallow_line is None
        results.append(
            {
                "check_id": "chk_no_silent_exception_swallow",
                "passed": ok_ast,
                "witness": "" if ok_ast else f"silent_except_pass_at_line:{swallow_line}",
            }
        )

        # 4. Capability ceiling
        cap = candidate.get("capability", {})
        req_eff = str(cap.get("requested_effect", "none"))
        ceil_eff = str(cap.get("granted_ceiling", "none"))
        ok_cap = (
            req_eff in self.effect_order
            and ceil_eff in self.effect_order
            and self.effect_order[req_eff] <= self.effect_order[ceil_eff]
        )
        results.append(
            {
                "check_id": "chk_capability_ceiling",
                "passed": ok_cap,
                "witness": "" if ok_cap else f"requested={req_eff}>granted_ceiling={ceil_eff}",
            }
        )

        # 5. Distinct drafter/reviewer principals
        att = candidate.get("attestation", {})
        drafter_p = str(att.get("drafter_principal", ""))
        reviewer_p = str(att.get("reviewer_principal", ""))
        drafter_k = str(att.get("drafter_key_id", ""))
        reviewer_k = str(att.get("reviewer_key_id", ""))
        ok_principals = (
            bool(drafter_p)
            and bool(reviewer_p)
            and drafter_p != reviewer_p
            and bool(drafter_k)
            and bool(reviewer_k)
            and drafter_k != reviewer_k
        )
        results.append(
            {
                "check_id": "chk_distinct_principals",
                "passed": ok_principals,
                "witness": "" if ok_principals else f"reused_principal_or_key:{drafter_p}/{reviewer_p}",
            }
        )

        # 6. Grounded citation spans
        sources = {str(k): str(v) for k, v in candidate.get("sources", {}).items()}
        bad_cite = ""
        for idx, cite in enumerate(candidate.get("citations", [])):
            sid = str(cite.get("source_id", ""))
            quote = str(cite.get("exact_quote", ""))
            if sid not in sources or not quote or quote not in sources[sid]:
                bad_cite = f"citation[{idx}]:{sid}:ungrounded_span"
                break
        ok_cite = bad_cite == ""
        results.append(
            {
                "check_id": "chk_grounded_citations",
                "passed": ok_cite,
                "witness": "" if ok_cite else bad_cite,
            }
        )
        return results
