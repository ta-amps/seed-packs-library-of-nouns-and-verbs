"""End-to-end Partner Compute Cascade simulator and $300 ($100x3) credit envelope calculator."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from .baseten_2m_tpm_swarm import run_baseten_mock_swarm_verification
from .fireworks_multilora_shim import FireworksMultiLoraRouter, run_fireworks_local_verification
from .modal_qlora_and_sandbox import (
    compute_qlora_vram_and_config,
    dry_run_validate_modal_pipeline,
    verify_sandbox_contract,
)


def simulate_1000_request_cascade() -> dict[str, Any]:
    """Deterministically simulate routing 1,000 public-good requests across the 5-tier compute cascade."""
    # Workload mix drawn from the 1,000-Scenario Matrix distribution:
    # - 310 repeated/pinned deterministic rule & memoized requests -> Tier 0 (<2ms edge shim, $0)
    # - 410 structured triage/statute/schema requests passing rubric check -> Tier 1 (Fireworks Multi-LoRA)
    # - 180 parallel batch fanout sub-tasks -> Tier 2 (Baseten <=2M TPM Meta Llama-3.3-70B Swarm)
    # - 70 domain-adapted complex reasoning tasks -> Tier 3 (Modal Muse-Glimmer-30B / Llama-3.2 QLoRA + Sandbox)
    # - 30 frontier novel multi-constraint syntheses -> Tier 4 (Meta Muse Spark escalation)
    tiers = {
        "tier_0_edge_shim_memo": {
            "requests": 310,
            "avg_tokens": 0,
            "avg_latency_ms": 0.08,
            "cost_per_request_usd": 0.0,
        },
        "tier_1_fireworks_multilora": {
            "requests": 410,
            "avg_tokens": 2400,
            "avg_latency_ms": 420.0,
            "cost_per_request_usd": round(0.00048 + 0.00054, 6),  # 8B drafter + compact rubric verifier
        },
        "tier_2_baseten_2m_tpm_swarm": {
            "requests": 180,
            "avg_tokens": 6200,
            "avg_latency_ms": 1650.0,
            "cost_per_request_usd": 0.0038,
        },
        "tier_3_modal_qlora_and_sandbox": {
            "requests": 70,
            "avg_tokens": 4800,
            "avg_latency_ms": 2850.0,
            "cost_per_request_usd": 0.0064,
        },
        "tier_4_meta_muse_spark_frontier": {
            "requests": 30,
            "avg_tokens": 5500,
            "avg_latency_ms": 3900.0,
            "cost_per_request_usd": 0.0095,
        },
    }

    total_reqs = sum(t["requests"] for t in tiers.values())
    cascade_cost = sum(t["requests"] * t["cost_per_request_usd"] for t in tiers.values())
    naive_frontier_cost = total_reqs * 0.0095
    weighted_latency_ms = sum(t["requests"] * t["avg_latency_ms"] for t in tiers.values()) / total_reqs

    credit_envelopes = {
        "modal_100_usd": {
            "credit_usd": 100.0,
            "llama3_3b_qlora_l4_20min_runs": 375,
            "muse_glimmer_30b_qlora_a100_20min_runs": 120,
            "isolated_pack_sandbox_verifications": 45_000,
        },
        "baseten_100_usd": {
            "credit_usd": 100.0,
            "rate_ceiling_tpm": 2_000_000,
            "sustained_hourly_token_throughput": 120_000_000,
            "estimated_public_statute_swarm_tasks": 26_300,
        },
        "fireworks_100_usd": {
            "credit_usd": 100.0,
            "8b_multilora_tokens_supported": 500_000_000,
            "rubric_verified_triage_requests": 98_000,
        },
    }

    return {
        "workload_requests": total_reqs,
        "tiers": tiers,
        "cascade_total_cost_usd": round(cascade_cost, 4),
        "naive_all_frontier_cost_usd": round(naive_frontier_cost, 4),
        "cost_savings_pct": round(100.0 * (naive_frontier_cost - cascade_cost) / naive_frontier_cost, 2),
        "weighted_avg_latency_ms": round(weighted_latency_ms, 2),
        "partner_credit_envelopes_300_usd": credit_envelopes,
    }


def run_full_cascade_report() -> dict[str, Any]:
    """Execute all local partner verifications and emit honest partner_compute_cascade.json artifact."""
    env_status = {
        key: ("set" if os.environ.get(key) else "unset")
        for key in ("MODAL_TOKEN_ID", "BASETEN_API_KEY", "FIREWORKS_API_KEY", "META_API_KEY")
    }
    any_live = any(v == "set" for v in env_status.values())
    modal_receipt = dry_run_validate_modal_pipeline()
    baseten_receipt = run_baseten_mock_swarm_verification()
    fireworks_receipt = run_fireworks_local_verification()
    sim = simulate_1000_request_cascade()

    doc: dict[str, Any] = {
        "schema_version": "ta-amps.partner-compute-cascade.v1",
        "mode": "local_verified",
        "credential_environment_status": env_status,
        "honesty_statement": (
            "All partner API keys are unset in this build environment (or live calls were not invoked); "
            "every receipt below is deterministically executed and verified locally (mode=local_verified), "
            "never faking live cloud API responses."
            if not any_live
            else "Local deterministic verification run completed (mode=local_verified)."
        ),
        "modal_qlora_and_sandbox": modal_receipt,
        "baseten_2m_tpm_swarm": baseten_receipt,
        "fireworks_multilora_shim": fireworks_receipt,
        "cascade_1000_request_simulation": sim,
    }
    doc["artifact_sha256"] = hashlib.sha256(
        json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return doc


def run_worked_example(bundle: dict[str, Any]) -> dict[str, Any]:
    """Deterministic recomputation for the synthetic worked example in source.json."""
    vram_cfg = compute_qlora_vram_and_config(
        bundle["model_name"],
        lora_rank=bundle["lora_rank"],
        lora_alpha=bundle["lora_alpha"],
        seq_len=bundle["seq_len"],
    )
    sbx = verify_sandbox_contract(bundle["sandbox_spec"])
    router = FireworksMultiLoraRouter()
    route = router.route_request(
        bundle["task_kind"],
        bundle["prompt"],
        bundle["schema_required"],
    )
    verdict = router.verify_rubric(
        route["selected_adapter"],
        route["verifier_adapter"],
        bundle["candidate_output"],
        bundle["schema_required"],
    )
    return {
        "mode": "local_verified",
        "fits_within_92pct_vram": vram_cfg["fits_within_92pct_vram"],
        "estimated_peak_vram_gib": vram_cfg["estimated_peak_vram_gib"],
        "sandbox_contract_valid": sbx["contract_valid"],
        "selected_adapter": route["selected_adapter"],
        "rubric_passed": verdict["passed"],
    }
