"""CLI entry point for rubric_audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .auditor import audit_repository_manifest, build_manifest_from_directory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rubric_audit", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_man = sub.add_parser("audit", help="Audit a JSON repository manifest")
    p_man.add_argument("manifest_json", type=Path)

    p_dir = sub.add_parser("score-directory", help="Scan a local directory and audit against rubric")
    p_dir.add_argument("repo_dir", type=Path)
    p_dir.add_argument("--probes", type=Path, default=None, help="Optional JSON list of HTTP probe receipts")
    p_dir.add_argument("--commits-in-window", type=int, default=5)

    args = parser.parse_args(argv)
    if args.cmd == "audit":
        manifest = json.loads(args.manifest_json.read_text(encoding="utf-8"))
        report = audit_repository_manifest(manifest)
    else:
        probes = json.loads(args.probes.read_text(encoding="utf-8")) if args.probes else []
        manifest = build_manifest_from_directory(
            args.repo_dir,
            probe_receipts=probes,
            commits_in_window=args.commits_in_window,
        )
        report = audit_repository_manifest(manifest)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
