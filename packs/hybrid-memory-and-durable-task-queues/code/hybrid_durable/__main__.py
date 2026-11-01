"""CLI entrypoint for hybrid_durable bundle evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import evaluate_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a hybrid durable task queue and subspace memory bundle.")
    parser.add_argument("--bundle", required=True, type=Path, help="Path to JSON input bundle.")
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    receipt = evaluate_bundle(bundle)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
