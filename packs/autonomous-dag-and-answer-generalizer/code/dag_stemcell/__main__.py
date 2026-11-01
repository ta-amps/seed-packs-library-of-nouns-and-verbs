"""CLI entrypoint for dag_stemcell."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import load_default_grid_spec, run_bundle


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute a dag_stemcell bundle against default_grid_spec.json."
    )
    parser.add_argument("--bundle", required=True, help="Path to JSON bundle file.")
    args = parser.parse_args()

    spec = load_default_grid_spec()
    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    receipt = run_bundle(bundle, spec=spec)
    print(json.dumps(receipt, indent=int(spec["json_indent"]), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
