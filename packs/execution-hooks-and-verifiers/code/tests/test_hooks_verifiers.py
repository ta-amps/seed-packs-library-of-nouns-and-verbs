"""Unit tests for execution-hooks-and-verifiers (including self-conformance AST gate)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from hooks_verifiers import (
    ComposableVerifierDagAndMutationGate,
    PortableHookCompiler,
    ZeroHardcodedValuesAstGate,
)
from hooks_verifiers.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "hooks_verifiers"


class HooksVerifiersTests(unittest.TestCase):
    def test_package_passes_zero_hardcoded_values_ast_gate(self) -> None:
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"], f"Unexpected magic literals in hooks_verifiers: {report}")
        self.assertEqual(report["violation_count"], 0)

    def test_portable_hook_compiler_and_pre_tool_decisions(self) -> None:
        compiler = PortableHookCompiler()
        spec = {
            "stages": {
                "pre_claim": ["verify_lease_budget"],
                "pre_tool": ["guard_tool_invocation"],
                "post_step": ["record_step_digest"],
                "pre_submit": ["run_verifier_dag"],
            }
        }
        compiled = compiler.compile_all_harnesses(spec)
        self.assertEqual(
            sorted(compiled.keys()),
            ["claude_code", "muse_code", "opencode", "pi_coding_agent"],
        )
        for cfg in compiled.values():
            self.assertTrue(cfg["disable_bypass_permissions"])
        self.assertEqual(compiled["claude_code"]["hooks"]["PreToolUse"], ["guard_tool_invocation"])
        self.assertEqual(compiled["claude_code"]["hooks"]["PostToolUse"], ["record_step_digest"])
        self.assertEqual(compiled["claude_code"]["hooks"]["Stop"], ["run_verifier_dag"])

        # Verify all blocked categories + rewrite_hint + allow
        self.assertEqual(
            compiler.evaluate_pre_tool({"command": "agent --dangerously-skip-permissions"})["decision"],
            "deny",
        )
        self.assertEqual(
            compiler.evaluate_pre_tool({"file_path": "config/.env.local"})["decision"],
            "deny",
        )
        self.assertEqual(
            compiler.evaluate_pre_tool({"command": "printenv"})["decision"],
            "deny",
        )
        self.assertEqual(
            compiler.evaluate_pre_tool({"command": "git update-ref --force main"})["decision"],
            "deny",
        )
        self.assertEqual(
            compiler.evaluate_pre_tool({"command": "rm -rf build_dir"})["decision"],
            "deny",
        )
        self.assertEqual(
            compiler.evaluate_pre_tool({"config_delta": {"contributor_mode": True}})["decision"],
            "deny",
        )
        self.assertEqual(
            compiler.evaluate_pre_tool({"estimated_spend_usd": 5.0})["decision"],
            "deny",
        )
        csp_res = compiler.evaluate_pre_tool({"content_patch": "<div style={{ color: 'red' }} />"})
        self.assertEqual(csp_res["decision"], "rewrite_hint")
        self.assertTrue(csp_res["blocked"])

        storage_res = compiler.evaluate_pre_tool({"content_patch": "window.localStorage.setItem('k', 'v')"})
        self.assertEqual(storage_res["decision"], "rewrite_hint")
        self.assertTrue(storage_res["blocked"])

        allow_res = compiler.evaluate_pre_tool(
            {"command": "python3 -m unittest", "estimated_spend_usd": 0.1}
        )
        self.assertEqual(allow_res["decision"], "allow")
        self.assertFalse(allow_res["blocked"])

    def test_composable_verifier_dag_and_cycle_detection(self) -> None:
        dag = ComposableVerifierDagAndMutationGate()
        with self.assertRaises(ValueError):
            dag.topological_order(
                [
                    {"id": "a", "depends_on": ["b"], "verifier_type": "human_only_boundary_check"},
                    {"id": "b", "depends_on": ["a"], "verifier_type": "human_only_boundary_check"},
                ]
            )

        artifact_doc = {"summary": "verified-artifact"}
        digest = dag.canonical_sha256(artifact_doc)
        nodes = [
            {
                "id": "schema_check",
                "verifier_type": "json_schema_conformance",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["status"],
                    "properties": {"status": {"type": "string", "enum": ["ready"]}},
                },
            },
            {
                "id": "pin_check",
                "depends_on": ["schema_check"],
                "verifier_type": "sha256_pin_integrity",
            },
            {
                "id": "human_check",
                "depends_on": ["schema_check"],
                "verifier_type": "human_only_boundary_check",
            },
            {
                "id": "principal_check",
                "depends_on": ["pin_check", "human_check"],
                "verifier_type": "multi_principal_publication_check",
            },
            {
                "id": "bootstrap_check",
                "depends_on": ["principal_check"],
                "verifier_type": "paired_bootstrap_delta_check",
            },
        ]
        good_sub = {
            "payload": {"status": "ready"},
            "pins": [{"key": "art.1", "artifact_value": artifact_doc, "declared_sha256": digest}],
            "human_only": False,
            "claimant": "agent",
            "model_calls": 0,
            "drafter_worker_id": "worker-a",
            "drafter_key_id": "tsk_drafter_a",
            "reviewer_worker_id": "worker-b",
            "reviewer_key_id": "tsk_reviewer_b",
            "baseline_scores": [0.70, 0.72, 0.68, 0.71, 0.69],
            "candidate_scores": [0.82, 0.84, 0.80, 0.83, 0.81],
        }
        good_out = dag.execute_verifier_dag(nodes, good_sub)
        self.assertTrue(good_out["all_passed"])

        # Self-approved principal fails principal_check and skips bootstrap_check
        bad_sub = dict(good_sub)
        bad_sub["reviewer_key_id"] = "tsk_drafter_a"
        bad_out = dag.execute_verifier_dag(nodes, bad_sub)
        self.assertFalse(bad_out["all_passed"])
        self.assertEqual(bad_out["failed_verifiers"], ["principal_check"])
        self.assertEqual(bad_out["skipped_verifiers"], ["bootstrap_check"])

    def test_checks_of_checks_mutation_gate_and_tombstone_normalization(self) -> None:
        dag = ComposableVerifierDagAndMutationGate()
        clean = [{"val": 10, "tag": "ok"}, {"val": 20, "tag": "ok"}]
        mutants = [
            {"val": -5, "tag": "ok"},
            {"val": 10, "tag": "corrupt"},
        ]

        trusted_res = dag.audit_verifier_sensitivity(
            lambda d: d["val"] > 0 and d["tag"] == "ok",
            clean_twins=clean,
            mutated_negatives=mutants,
        )
        self.assertEqual(trusted_res["classification"], "trusted")

        revise_res = dag.audit_verifier_sensitivity(
            lambda d: d["val"] > 0,
            clean_twins=clean,
            mutated_negatives=mutants,
        )
        self.assertEqual(revise_res["classification"], "revise")

        reject_fp_res = dag.audit_verifier_sensitivity(
            lambda d: d["val"] > 15,
            clean_twins=clean,
            mutated_negatives=mutants,
        )
        self.assertEqual(reject_fp_res["classification"], "reject")

        t1 = dag.extract_negative_tombstone(
            failed_stage="pre_submit",
            approach_label="self_sign_attempt",
            failed_verifiers=["principal_check"],
            raw_diagnostics=["2026-10-31T10:00:00Z error at line 42 id aabbccddeeff0011"],
        )
        t2 = dag.extract_negative_tombstone(
            failed_stage="pre_submit",
            approach_label="self_sign_attempt",
            failed_verifiers=["principal_check"],
            raw_diagnostics=["2026-10-31T23:59:59Z error at line 99 id 1122334455667788"],
        )
        self.assertEqual(t1["tombstone_id"], t2["tombstone_id"])

    def test_worked_example_and_cli_roundtrip(self) -> None:
        src_path = PACK_DIR / "source.json"
        if not src_path.exists():
            return
        src = json.loads(src_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.hooks-verifiers-bundle"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, nouns["example.hooks-verifiers-receipt"]["instance"])

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "hooks_verifiers", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(json.loads(proc.stdout), recomputed)


if __name__ == "__main__":
    unittest.main()
