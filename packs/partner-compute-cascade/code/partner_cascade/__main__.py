"""CLI entrypoint for Partner Compute Cascade validation and simulation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cascade_simulator import run_full_cascade_report, run_worked_example
from .modal_qlora_and_sandbox import dry_run_validate_modal_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="partner_cascade")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sim = sub.add_parser("verify-all", help="Run Modal dry-run, Baseten 2M TPM mock swarm, Fireworks router and simulator")
    p_sim.add_argument("--out", type=Path, help="Optional JSON output file")

    sub.add_parser("modal-dry-run", help="Run deterministic Modal QLoRA VRAM, trace holdout and sandbox validation")

    p_worked = sub.add_parser("worked-example", help="Recompute synthetic worked example")
    p_worked.add_argument("--input", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "verify-all":
        doc = run_full_cascade_report()
        text = json.dumps(doc, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0

    if args.cmd == "modal-dry-run":
        print(json.dumps(dry_run_validate_modal_pipeline(), indent=2))
        return 0

    data = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(run_worked_example(data), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
