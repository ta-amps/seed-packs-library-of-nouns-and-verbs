"""Unit tests for Modal QLoRA/Sandbox, Baseten 2M TPM Swarm, and Fireworks Multi-LoRA Router."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from partner_cascade import (
    FireworksMultiLoraRouter,
    compute_qlora_vram_and_config,
    dry_run_validate_modal_pipeline,
    format_traces_for_qlora,
    run_baseten_mock_swarm_verification,
    run_fireworks_local_verification,
    run_full_cascade_report,
    run_worked_example,
    verify_sandbox_contract,
)


class PartnerComputeCascadeTests(unittest.TestCase):
    def test_modal_qlora_vram_math_and_sandbox_isolation(self) -> None:
        llama = compute_qlora_vram_and_config("Llama-3.2-3B-Instruct")
        glimmer = compute_qlora_vram_and_config("Muse-Glimmer-30B")
        self.assertTrue(llama["fits_within_92pct_vram"])
        self.assertTrue(glimmer["fits_within_92pct_vram"])
        self.assertLess(llama["estimated_peak_vram_gib"], 10.0)
        self.assertLess(glimmer["estimated_peak_vram_gib"], 36.0)

        bad_sbx = verify_sandbox_contract(
            {
                "block_network": False,
                "forward_host_secrets": True,
                "read_only_pack_mount": False,
                "timeout_seconds": 9999,
            }
        )
        self.assertFalse(bad_sbx["contract_valid"])
        self.assertEqual(len(bad_sbx["violations"]), 4)

        receipt = dry_run_validate_modal_pipeline()
        self.assertEqual(receipt["mode"], "local_verified")
        self.assertEqual(receipt["dataset_validation"]["accepted_count"], 1)
        self.assertEqual(receipt["dataset_validation"]["rejected_count"], 1)

    def test_qlora_trace_formatter_blocks_holdout_leakage_and_missing_human_boundary(self) -> None:
        res = format_traces_for_qlora(
            [
                {
                    "prompt": "Audit enacted city budget table lines with exact page references",
                    "completion": '{"rows":12}',
                    "human_only": "Finance director signs off.",
                },
                {
                    "prompt": "Audit enacted city budget table lines with exact page references",
                    "completion": '{"rows":12}',
                    "human_only": "",
                },
            ],
            holdout_prompts=["Summarize rural paratransit wheelchair pickup schedules"],
        )
        self.assertEqual(res["accepted_count"], 1)
        self.assertEqual(res["rejected_count"], 1)

    def test_baseten_2m_tpm_mock_server_pacing_429_and_fenced_lease_safety(self) -> None:
        receipt = run_baseten_mock_swarm_verification()
        self.assertEqual(receipt["mode"], "local_verified")
        self.assertTrue(receipt["respected_2m_tpm_ceiling"])
        self.assertLessEqual(receipt["peak_sliding_window_tokens"], 2_000_000)
        self.assertEqual(receipt["succeeded_claims"], 12)
        self.assertEqual(receipt["pre_flight_fenced_or_ttl_blocked"], 2)
        self.assertTrue(receipt["retried_429_preserved_in_ledger"])
        self.assertGreater(receipt["pacing_waits_triggered"], 0)

    def test_fireworks_multilora_router_memo_replay_and_rubric_verifier(self) -> None:
        receipt = run_fireworks_local_verification()
        self.assertEqual(receipt["mode"], "local_verified")
        self.assertTrue(receipt["shim_within_2ms"])
        self.assertEqual(receipt["memo_replay_tier"], "edge_shim_zero_token")
        self.assertTrue(receipt["good_candidate_passed"])
        self.assertTrue(receipt["self_verification_blocked"])
        self.assertTrue(receipt["pii_leak_escalated"])

        router = FireworksMultiLoraRouter()
        intake_route = router.route_request(
            "verb.ingest",
            "Split confidential shelter handwritten intake from public statutes",
            ["private_lane", "public_lane", "human_only", "citations"],
        )
        self.assertEqual(intake_route["selected_adapter"], "triage-lane-splitter-lora")

    def test_full_cascade_simulator_reduces_cost_over_65_percent(self) -> None:
        report = run_full_cascade_report()
        self.assertEqual(report["mode"], "local_verified")
        sim = report["cascade_1000_request_simulation"]
        self.assertEqual(sim["workload_requests"], 1000)
        self.assertGreater(sim["cost_savings_pct"], 65.0)

    def test_source_json_worked_example_recomputes_identically(self) -> None:
        source_path = Path(__file__).resolve().parents[2] / "source.json"
        if not source_path.exists():
            return
        source = json.loads(source_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in source["nouns"]}
        bundle = nouns["example.cascade-bundle"]
        expected = nouns["example.cascade-receipt"]["instance"]
        self.assertEqual(run_worked_example(bundle), expected)


if __name__ == "__main__":
    unittest.main()
