"""CLI entry point for lora_memory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compiler import check_holdout_disjointness, compile_post_cutoff_pairs
from .gates import evaluate_promotion_gate
from .router import route_adaptation_strategy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lora_memory")
    sub = parser.add_subparsers(dest="command", required=True)

    cp = sub.add_parser("compile", help="compile post-cutoff Task Objects and check holdout disjointness")
    cp.add_argument("--input", required=True, type=Path)

    rt = sub.add_parser("route", help="choose prompt_context_shim vs lora_weight_update vs hybrid_shim_and_lora")
    rt.add_argument("--spec-json", required=True, type=Path)

    gt = sub.add_parser("gate", help="evaluate paired bootstrap CI promotion gate")
    gt.add_argument("--eval-json", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "compile":
        doc = json.loads(args.input.read_text(encoding="utf-8"))
        pairs = compile_post_cutoff_pairs(doc["task_objects"])
        disj = check_holdout_disjointness(pairs, doc.get("holdout_prompts", []))
        print(json.dumps({"pairs": pairs, "disjointness": disj}, indent=2, sort_keys=True))
        return 0
    if args.command == "route":
        spec = json.loads(args.spec_json.read_text(encoding="utf-8"))
        print(json.dumps(route_adaptation_strategy(spec), indent=2, sort_keys=True))
        return 0
    if args.command == "gate":
        ev = json.loads(args.eval_json.read_text(encoding="utf-8"))
        print(json.dumps(evaluate_promotion_gate(**ev), indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
