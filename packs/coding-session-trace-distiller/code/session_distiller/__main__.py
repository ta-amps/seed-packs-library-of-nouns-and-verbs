"""Command-line entry point for coding-session-trace-distiller."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .analyzer import distill_session_events, load_jsonl_events
from .redactor import redact_session


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="session_distiller")
    sub = parser.add_subparsers(dest="command", required=True)

    p_distill = sub.add_parser("distill", help="Sanitize a session JSONL file and mine loops, tombstones, fixes, and shims")
    p_distill.add_argument("jsonl_path", type=Path)
    p_distill.add_argument("--session-id", default=None)
    p_distill.add_argument("--min-loop-repeats", type=int, default=2)

    p_redact = sub.add_parser("redact", help="Sanitize a session JSONL file and print redacted JSONL summary")
    p_redact.add_argument("jsonl_path", type=Path)

    args = parser.parse_args(argv)
    events = load_jsonl_events(args.jsonl_path)

    if args.command == "redact":
        sanitized, stats = redact_session(events)
        print(json.dumps({"redaction_counts": stats, "events": sanitized}, indent=2, sort_keys=True))
        return 0

    sid = args.session_id or args.jsonl_path.stem
    report = distill_session_events(events, session_id=sid, min_loop_repeats=args.min_loop_repeats)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
