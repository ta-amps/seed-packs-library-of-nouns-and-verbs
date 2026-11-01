"""CLI entry point for multimodal_align."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .aligner import align_multimodal_timeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="multimodal_align", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_align = sub.add_parser("align", help="Align segmentation masks, word timings, and safe zones")
    p_align.add_argument("timeline_json", type=Path)
    p_align.add_argument("--max-drift-ms", type=float, default=250.0)
    p_align.add_argument("--max-intrusion", type=float, default=0.05)
    p_align.add_argument("--min-word-confidence", type=float, default=0.70)

    args = parser.parse_args(argv)
    timeline = json.loads(args.timeline_json.read_text(encoding="utf-8"))
    report = align_multimodal_timeline(
        timeline,
        max_drift_ms=args.max_drift_ms,
        max_intrusion=args.max_intrusion,
        min_word_confidence=args.min_word_confidence,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
