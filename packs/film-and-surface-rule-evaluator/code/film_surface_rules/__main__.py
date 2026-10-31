"""CLI entry point for film_surface_rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .evaluator import load_default_grid_cell, run_worked_example


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        bundle = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    else:
        src_path = Path(__file__).resolve().parents[1 + 1] / "source.json"
        src = json.loads(src_path.read_text(encoding="utf-8"))
        bundle = next(
            n["value"]["bundle"] for n in src["nouns"] if n["key"].endswith("example.film-surface-rules-bundle")
        )
    receipt = run_worked_example(bundle, load_default_grid_cell())
    sys.stdout.write(json.dumps(receipt, indent=1 + 1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
