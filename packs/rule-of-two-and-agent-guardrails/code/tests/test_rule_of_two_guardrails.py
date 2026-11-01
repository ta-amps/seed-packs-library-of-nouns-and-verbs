"""Unit tests for rule-of-two-and-agent-guardrails (including AST magic-literal gate)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rule_of_two_guardrails import (
    BidirectionalPrivacyPlaceholderGateway,
    ModelLicenseTierFirewall,
    NodeGrid,
    RuleOfTwoCapabilityLattice,
    ZeroHardcodedValuesAstGate,
    scan_directory_for_hardcoded_values,
)
from rule_of_two_guardrails.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "rule_of_two_guardrails"


class RuleOfTwoGuardrailsTests(unittest.TestCase):
    def test_zero_hardcoded_values_ast_gate_clean(self) -> None:
        violations = scan_directory_for_hardcoded_values(PKG_DIR)
        self.assertEqual(violations, [], f"Unexpected magic literals: {violations}")
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"])
        self.assertGreaterEqual(report["files_scanned"], 7)

        bad_scan = ZeroHardcodedValuesAstGate.scan_source("def bad_status() -> int:\n    return 403\n")
        self.assertFalse(bad_scan["passed"])
        self.assertEqual(bad_scan["violation_count"], 1)

    def test_node_grid_clamping_enumeration_and_auto_expansion(self) -> None:
        grid = NodeGrid()
        clamped = grid.clamp_cell({"max_unapproved_legs": 99, "placeholder_index_width": 1})
        self.assertEqual(clamped["max_unapproved_legs"], 2)
        self.assertEqual(clamped["placeholder_index_width"], 3)
        cells = grid.enumerate_cells()
        self.assertGreater(len(cells["applicable"]), 0)
        expanded, axes = grid.auto_expand_if_saturated({"max_dag_steps": 256})
        self.assertEqual(expanded.generation, 2)
        self.assertEqual(axes, ["max_dag_steps:high->512"])

    def test_rule_of_two_allows_one_or_two_legs_and_blocks_transitive_triad_with_minimal_witness(self) -> None:
        lattice = RuleOfTwoCapabilityLattice()
        two_leg_dag = [
            {"id": "parse_external_doc", "legs": ["A"]},
            {"id": "read_scoped_vault", "legs": ["B"], "depends_on": ["parse_external_doc"]},
        ]
        res_ok = lattice.evaluate_dag(two_leg_dag)
        self.assertTrue(res_ok["allowed"])
        self.assertEqual(res_ok["status_code"], 200)
        self.assertEqual(res_ok["max_effective_legs"], 2)

        # Diamond + distractor branch: transitive A + B + C meets at dispatch_webhook
        triad_dag = [
            {"id": "distractor_metrics", "legs": []},
            {"id": "ingest_untrusted_issue", "legs": ["untrusted_input"]},
            {
                "id": "summarize_issue",
                "legs": [],
                "depends_on": ["ingest_untrusted_issue", "distractor_metrics"],
            },
            {"id": "query_private_records", "legs": ["sensitive_access"]},
            {
                "id": "dispatch_webhook",
                "legs": ["external_mutation_or_egress"],
                "depends_on": ["summarize_issue", "query_private_records"],
            },
        ]
        res_block = lattice.evaluate_dag(triad_dag)
        self.assertFalse(res_block["allowed"])
        self.assertEqual(res_block["verdict"], "refuse")
        self.assertEqual(res_block["status_code"], 403)
        self.assertEqual(res_block["violating_step_id"], "dispatch_webhook")
        self.assertEqual(
            res_block["minimal_witness_path"],
            [
                "ingest_untrusted_issue",
                "query_private_records",
                "summarize_issue",
                "dispatch_webhook",
            ],
        )
        self.assertNotIn("distractor_metrics", res_block["minimal_witness_path"])

        # Agent self-approval or invalid token must NOT bypass 403
        forged = lattice.evaluate_dag(
            triad_dag,
            human_steward_approval={
                "principal_kind": "agent",
                "approver_principal": "worker-1",
                "token": "steward_ack:forged_agent_token_01",
                "approved_steps": ["dispatch_webhook"],
            },
        )
        self.assertEqual(forged["status_code"], 403)

        # Valid human steward token permits explicitly scoped step
        steward_ok = lattice.evaluate_dag(
            triad_dag,
            human_steward_approval={
                "principal_kind": "human_steward",
                "approver_principal": "steward:alice",
                "token": "steward_ack:verified_ticket_9941",
                "approved_steps": ["dispatch_webhook"],
            },
        )
        self.assertTrue(steward_ok["allowed"])
        self.assertEqual(steward_ok["status_code"], 200)
        self.assertTrue(steward_ok["human_steward_approved"])

    def test_lattice_detects_cycles_and_single_leg_regime(self) -> None:
        lattice = RuleOfTwoCapabilityLattice()
        with self.assertRaises(ValueError):
            lattice.evaluate_dag(
                [
                    {"id": "s1", "legs": ["A"], "depends_on": ["s2"]},
                    {"id": "s2", "legs": ["B"], "depends_on": ["s1"]},
                ]
            )
        strict_single = RuleOfTwoCapabilityLattice(regime="high_assurance_single_leg")
        res = strict_single.evaluate_dag([{"id": "dual", "legs": ["A", "B"]}])
        self.assertEqual(res["status_code"], 403)

    def test_bidirectional_privacy_placeholder_gateway_preserves_hashes_and_coreference(self) -> None:
        gw = BidirectionalPrivacyPlaceholderGateway()
        digest = "a" * 64
        payload = {
            "summary": (
                f"Contact ops@example.invalid or ops@example.invalid with token "
                f"sk-liveSecretToken987654 and artifact {digest} from 10.24.8.19."
            ),
            "nested": ["+1-555-234-5678", "123-45-6789"],
        }
        scrubbed = gw.scrub_payload(payload)
        self.assertNotIn("ops@example.invalid", scrubbed["summary"])
        self.assertNotIn("sk-liveSecretToken987654", scrubbed["summary"])
        self.assertNotIn("10.24.8.19", scrubbed["summary"])
        self.assertIn("<EMAIL_ADDR_001> or <EMAIL_ADDR_001>", scrubbed["summary"])
        self.assertIn("<API_SECRET_001>", scrubbed["summary"])
        self.assertIn("<IPV4_HOST_001>", scrubbed["summary"])
        self.assertIn(digest, scrubbed["summary"])
        self.assertEqual(scrubbed["nested"], ["<PHONE_NUM_001>", "<GOV_ID_001>"])

        rehydrated, unresolved = gw.rehydrate_payload(scrubbed)
        self.assertEqual(unresolved, [])
        self.assertEqual(rehydrated, payload)

        # Hallucinated placeholder surfaces in unresolved list without crashing
        partial, missing = gw.rehydrate_text("Reply to <EMAIL_ADDR_001> and <EMAIL_ADDR_999>.")
        self.assertIn("ops@example.invalid", partial)
        self.assertEqual(missing, ["<EMAIL_ADDR_999>"])

        eval_res = BidirectionalPrivacyPlaceholderGateway.evaluate_bidirectional(
            [
                {
                    "text": "Send alert to sec@example.invalid and cc sec@example.invalid using ghp_AbCdEfGhIjKlMnOp1234.",
                    "ground_truth_sensitive": ["sec@example.invalid", "ghp_AbCdEfGhIjKlMnOp1234"],
                    "expect_coreference_symbol": "sec@example.invalid",
                },
                {
                    "text": "Host 192.168.4.12 holds record 987-65-4321 for custodian Pat.",
                    "explicit_entities": {"PERSON_NAME": ["Pat"]},
                    "ground_truth_sensitive": ["192.168.4.12", "987-65-4321", "Pat"],
                },
            ]
        )
        self.assertEqual(eval_res["outbound_zero_leak_recall"], 1.0)
        self.assertEqual(eval_res["inbound_round_trip_fidelity"], 1.0)
        self.assertEqual(eval_res["coreference_preserved_rate"], 1.0)
        self.assertEqual(eval_res["residual_leak_count"], 0)

    def test_model_license_tier_firewall_routes_across_all_three_tiers(self) -> None:
        fw_strict = ModelLicenseTierFirewall(overrides={"firewall_mode": "strict_fail_closed"})
        r_contrib = fw_strict.route_payload(
            {
                "sensitivity": "public",
                "synthetic_provenance": True,
                "license_tag": "MIT",
                "requested_tier": "contributor_training_allowed",
            }
        )
        self.assertEqual(r_contrib["decision"], "allow")
        self.assertEqual(r_contrib["recommended_tier"], "contributor_training_allowed")

        r_zero_ret = fw_strict.route_payload(
            {
                "sensitivity": "internal",
                "synthetic_provenance": False,
                "license_tag": "internal-commercial-no-train",
                "requested_tier": "contributor_training_allowed",
            }
        )
        self.assertEqual(r_zero_ret["decision"], "refuse")
        self.assertEqual(r_zero_ret["recommended_tier"], "standard_zero_retention")

        fw_reroute = ModelLicenseTierFirewall(overrides={"firewall_mode": "reroute_to_safe_tier"})
        r_rerouted = fw_reroute.route_payload(
            {
                "sensitivity": "secret",
                "license_tag": "MIT",
                "requested_tier": "standard_zero_retention",
            }
        )
        self.assertEqual(r_rerouted["decision"], "reroute")
        self.assertEqual(r_rerouted["recommended_tier"], "local_open_weights")

        r_license_local = fw_strict.route_payload(
            {
                "sensitivity": "public",
                "synthetic_provenance": True,
                "license_tag": "restricted-derivative-no-api",
            }
        )
        self.assertEqual(r_license_local["recommended_tier"], "local_open_weights")

    def test_worked_example_recomputes_exact_receipt_and_cli_runs(self) -> None:
        source_path = PACK_DIR / "source.json"
        if not source_path.exists():
            return
        src = json.loads(source_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.rule-of-two-guardrails-bundle"]
        expected = nouns["example.rule-of-two-guardrails-receipt"]["instance"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, expected)

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "rule_of_two_guardrails", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out, expected)


if __name__ == "__main__":
    unittest.main()
