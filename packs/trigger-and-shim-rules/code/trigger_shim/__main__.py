"""CLI entry point for trigger-and-shim-rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .engine import ThreeTierTriggerEngine
from .knapsack import ConversationDedupAndSubmodularKnapsack
from .matcher import WhichFitsCompatibilityMatcher
from .router import HarnessTaxAndThreeRegimeRouter


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Evaluate trigger rules, context-shim knapsack, HarnessTax routing, and which-fits matching."""
    grid_cell = bundle.get("grid_cell")
    engine = ThreeTierTriggerEngine(grid_cell)
    trigger_out = engine.evaluate_all(bundle["query"], bundle["trigger_rules"])

    knapsack = ConversationDedupAndSubmodularKnapsack(grid_cell)
    packed_out = knapsack.pack_provisions(
        bundle["provisions"],
        bundle.get("conversation_history", []),
        current_error_signature=bundle.get("current_error_signature"),
    )

    router = HarnessTaxAndThreeRegimeRouter(grid_cell)
    tax_spec = bundle["harness_tax_input"]
    tax_out = router.compute_harness_tax(
        prefix_tokens_p=int(tax_spec["prefix_tokens_p"]),
        content_tokens_c=int(tax_spec["content_tokens_c"]),
        slice_count_k=int(tax_spec["slice_count_k"]),
        observed_skip_rate=float(tax_spec.get("observed_skip_rate", 0.0)),
    )
    regime_decisions = {
        str(item["id"]): router.route_intervention_regime(item)["selected_regime"]
        for item in bundle["interventions"]
    }

    matcher = WhichFitsCompatibilityMatcher(grid_cell)
    fits_out = matcher.recommend_which_fits(
        bundle["workload_request"],
        bundle["candidate_entries"],
        grid_cell,
    )

    rejected_by_rule = {
        str(ev["rule_id"]): ev["rejected_tier"]
        for ev in trigger_out["evaluations"]
        if not ev["matched"]
    }
    intent_by_rule = {
        str(ev["rule_id"]): str(ev["intent_action"])
        for ev in trigger_out["matched"]
    }

    return {
        "matched_rule_ids": [str(ev["rule_id"]) for ev in trigger_out["matched"]],
        "intent_by_rule": intent_by_rule,
        "rejected_by_rule": rejected_by_rule,
        "selected_provision_ids": packed_out["selected_provision_ids"],
        "packed_tokens": int(packed_out["total_tokens"]),
        "break_even_skip_rate": float(tax_out["break_even_skip_rate"]),
        "slicing_saves_tokens": bool(tax_out["slicing_saves_tokens"]),
        "regime_decisions": regime_decisions,
        "pareto_winners": fits_out["pareto_winners"],
        "disqualified_entry_ids": [str(d["entry_id"]) for d in fits_out["disqualified"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run trigger-and-shim-rules bundle evaluation.")
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
