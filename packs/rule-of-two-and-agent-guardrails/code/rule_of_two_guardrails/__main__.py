"""CLI entry point for rule-of-two-and-agent-guardrails."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .grid import load_default_grid_spec
from .lattice import RuleOfTwoCapabilityLattice
from .license_firewall import ModelLicenseTierFirewall
from .privacy_gateway import BidirectionalPrivacyPlaceholderGateway


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()
    regime = bundle.get("regime")

    lattice = RuleOfTwoCapabilityLattice(regime=regime, spec=cfg)
    safe_res = lattice.evaluate_dag(list(bundle["safe_two_leg_dag"]))
    unapproved_res = lattice.evaluate_dag(list(bundle["unapproved_three_leg_dag"]))
    approved_res = lattice.evaluate_dag(
        list(bundle["unapproved_three_leg_dag"]),
        human_steward_approval=dict(bundle["steward_approval"]),
    )

    privacy_metrics = BidirectionalPrivacyPlaceholderGateway.evaluate_bidirectional(
        list(bundle["privacy_cases"]),
        regime=regime,
        spec=cfg,
    )
    sample_gateway = BidirectionalPrivacyPlaceholderGateway(regime=regime, spec=cfg)
    sample_scrubbed = sample_gateway.scrub_text(str(bundle["sample_outbound_prompt"]))
    sample_rehydrated, unresolved = sample_gateway.rehydrate_text(sample_scrubbed)

    firewall = ModelLicenseTierFirewall(regime=regime, spec=cfg)
    tier_routes: dict[str, str] = {}
    tier_decisions: dict[str, str] = {}
    for item in bundle["license_requests"]:
        req_id = str(item["id"])
        routed = firewall.route_payload(dict(item))
        tier_routes[req_id] = str(routed["recommended_tier"])
        tier_decisions[req_id] = str(routed["decision"])

    return {
        "safe_dag_status_code": int(safe_res["status_code"]),
        "safe_dag_verdict": str(safe_res["verdict"]),
        "three_leg_dag_status_code": int(unapproved_res["status_code"]),
        "three_leg_dag_verdict": str(unapproved_res["verdict"]),
        "three_leg_violating_step": str(unapproved_res["violating_step_id"]),
        "three_leg_minimal_witness_path": list(unapproved_res["minimal_witness_path"]),
        "steward_approved_status_code": int(approved_res["status_code"]),
        "steward_approved_verdict": str(approved_res["verdict"]),
        "sample_scrubbed_prompt": sample_scrubbed,
        "sample_round_trip_exact": sample_rehydrated == str(bundle["sample_outbound_prompt"]) and not unresolved,
        "outbound_zero_leak_recall": float(privacy_metrics["outbound_zero_leak_recall"]),
        "inbound_round_trip_fidelity": float(privacy_metrics["inbound_round_trip_fidelity"]),
        "coreference_preserved_rate": float(privacy_metrics["coreference_preserved_rate"]),
        "license_tier_routes": tier_routes,
        "license_tier_decisions": tier_decisions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run rule-of-two-and-agent-guardrails bundle evaluation."
    )
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    cfg = load_default_grid_spec()
    indent = int(cfg["constants"]["json_indent"])
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
