"""Fireworks AI multi-LoRA specialist router & Sinan Ozdemir rubric verifier behind <2ms edge shim."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any

PII_PATTERN = re.compile(r"\b(?:\d{3}-\d{2}-\d{4}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")

SPECIALIST_LORAS: dict[str, dict[str, Any]] = {
    "triage-lane-splitter-lora": {
        "fireworks_model_id": "accounts/ta-amps/models/llama3p1-8b-triage-lane-splitter",
        "base_model": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "task_role": "drafter",
        "triggers": ("intake", "handwritten", "private", "shelter", "split", "confidential"),
        "price_per_1m_tokens_usd": 0.20,
        "typical_ttft_ms": 95,
    },
    "statute-citation-extractor-lora": {
        "fireworks_model_id": "accounts/ta-amps/models/llama3p1-8b-statute-citation",
        "base_model": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "task_role": "drafter",
        "triggers": ("budget", "statute", "appropriation", "ordinance", "enacted", "table"),
        "price_per_1m_tokens_usd": 0.20,
        "typical_ttft_ms": 105,
    },
    "schema-json-normalizer-lora": {
        "fireworks_model_id": "accounts/ta-amps/models/llama3p1-8b-schema-normalizer",
        "base_model": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "task_role": "drafter",
        "triggers": ("csv", "json", "schema", "column", "extract", "manifest"),
        "price_per_1m_tokens_usd": 0.20,
        "typical_ttft_ms": 90,
    },
    "rubric-judge-verifier-lora": {
        "fireworks_model_id": "accounts/ta-amps/models/llama3p3-70b-rubric-verifier",
        "base_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "task_role": "verifier",
        "triggers": ("verify", "rubric", "audit"),
        "price_per_1m_tokens_usd": 0.90,
        "typical_ttft_ms": 165,
    },
}


class FireworksMultiLoraRouter:
    """Sub-2ms edge shim + Fireworks multi-LoRA specialist selector + distinct-adapter rubric gate."""

    def __init__(self, memo_cache: dict[str, dict[str, Any]] | None = None) -> None:
        self.memo_cache: dict[str, dict[str, Any]] = dict(memo_cache or {})

    @staticmethod
    def _request_fingerprint(task_kind: str, prompt: str, schema_required: list[str]) -> str:
        canonical = json.dumps(
            {"task_kind": task_kind, "prompt": prompt.strip().lower(), "required": sorted(schema_required)},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def route_request(
        self,
        task_kind: str,
        prompt: str,
        schema_required: list[str],
    ) -> dict[str, Any]:
        """Execute <2ms edge shim check and select hot-swappable specialist LoRA adapter."""
        t0 = time.perf_counter()
        fp = self._request_fingerprint(task_kind, prompt, schema_required)
        if fp in self.memo_cache:
            shim_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "tier": "edge_shim_zero_token",
                "fingerprint": fp,
                "selected_adapter": "none",
                "verifier_adapter": "none",
                "shim_latency_ms": round(shim_ms, 5),
                "within_2ms_shim_budget": shim_ms < 2.0,
                "cached_output": self.memo_cache[fp],
            }

        lowered = prompt.lower()
        best_adapter = "schema-json-normalizer-lora"
        best_hits = -1
        for adapter_name, spec in SPECIALIST_LORAS.items():
            if spec["task_role"] != "drafter":
                continue
            hits = sum(1 for kw in spec["triggers"] if kw in lowered)
            if hits > best_hits:
                best_hits = hits
                best_adapter = adapter_name

        spec = SPECIALIST_LORAS[best_adapter]
        shim_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "tier": "fireworks_specialist_multilora",
            "fingerprint": fp,
            "selected_adapter": best_adapter,
            "fireworks_model_id": spec["fireworks_model_id"],
            "verifier_adapter": "rubric-judge-verifier-lora",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "tessera_task_output",
                    "strict": True,
                    "required": schema_required,
                },
            },
            "shim_latency_ms": round(shim_ms, 5),
            "within_2ms_shim_budget": shim_ms < 2.0,
        }

    @staticmethod
    def verify_rubric(
        drafter_adapter: str,
        verifier_adapter: str,
        candidate_json: dict[str, Any],
        schema_required: list[str],
    ) -> dict[str, Any]:
        """Sinan Ozdemir rubric-verification pattern: distinct verifier adapter + explicit checklist."""
        failed: list[str] = []
        if drafter_adapter == verifier_adapter:
            failed.append("drafter_adapter_cannot_self_verify")
        missing = [field for field in schema_required if field not in candidate_json]
        if missing:
            failed.append(f"missing_required_fields:{','.join(missing)}")
        serialized = json.dumps(candidate_json)
        if PII_PATTERN.search(serialized):
            failed.append("unredacted_pii_pattern_in_output")
        if not str(candidate_json.get("human_only", "")).strip():
            failed.append("missing_human_only_boundary")
        if not candidate_json.get("citations"):
            failed.append("missing_grounded_citations")

        passed = len(failed) == 0
        return {
            "passed": passed,
            "drafter_adapter": drafter_adapter,
            "verifier_adapter": verifier_adapter,
            "distinct_adapters": drafter_adapter != verifier_adapter,
            "next_action": "accept_specialist_output" if passed else "escalate_to_baseten_or_modal_tier",
            "failed_rubric_items": failed,
        }


def run_fireworks_local_verification() -> dict[str, Any]:
    """Run local deterministic router, memo cache and rubric-verifier checks."""
    router = FireworksMultiLoraRouter()
    req_schema = ["summary", "citations", "human_only"]

    r1 = router.route_request(
        "verb.situate",
        "Extract enacted FY2026 state shelter budget statute appropriation lines into JSON.",
        req_schema,
    )
    good_candidate = {
        "summary": "Enacted shelter line items reconciled across 12 statutory rows.",
        "citations": ["FY2026-Act-Ch42-Line108"],
        "human_only": "Nonprofit finance lead signs off before funder submission.",
    }
    good_verdict = router.verify_rubric(
        r1["selected_adapter"], r1["verifier_adapter"], good_candidate, req_schema
    )
    # Populate memo cache after verified pass and confirm <2ms 0-token replay
    if good_verdict["passed"]:
        router.memo_cache[r1["fingerprint"]] = good_candidate
    r1_replay = router.route_request(
        "verb.situate",
        "Extract enacted FY2026 state shelter budget statute appropriation lines into JSON.",
        req_schema,
    )

    # Negative check 1: self-verification attempt
    self_verdict = router.verify_rubric(
        "statute-citation-extractor-lora",
        "statute-citation-extractor-lora",
        good_candidate,
        req_schema,
    )
    # Negative check 2: PII leak triggers escalation
    pii_verdict = router.verify_rubric(
        r1["selected_adapter"],
        r1["verifier_adapter"],
        {**good_candidate, "summary": "Client SSN 123-45-6789 included."},
        req_schema,
    )

    receipt = {
        "provider": "fireworks_ai",
        "mode": "local_verified",
        "live_credentials_present": bool(os.environ.get("FIREWORKS_API_KEY")),
        "pattern_attribution": "Sinan Ozdemir specialist multi-LoRA routing and explicit rubric verification behind <2ms edge shim",
        "specialist_adapter_count": len(SPECIALIST_LORAS),
        "initial_route": r1,
        "memo_replay_tier": r1_replay["tier"],
        "shim_within_2ms": r1["within_2ms_shim_budget"] and r1_replay["within_2ms_shim_budget"],
        "good_candidate_passed": good_verdict["passed"],
        "self_verification_blocked": not self_verdict["passed"],
        "pii_leak_escalated": pii_verdict["next_action"] == "escalate_to_baseten_or_modal_tier",
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return receipt
