"""Command line for the edge case generator. It prints ASCII-only JSON and writes nothing.

  python -m edge_cases generate --kind strings --kind dates --seed 20261030 [--max-length 64] [--summary]
  python -m edge_cases labels [--kind dates]

Limits: --max-length (strings), --minimum and --maximum (numbers), --year (dates), --page-size (lists),
--max-bytes and --depth (bodies), and --seeded for the number of seeded cases of every kind asked for.
A limit for a kind that was not asked for is an error, so a typo never passes silently.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .generate import KINDS, LABELS, generate, summary

FLAGS = {
    "max_length": "strings",
    "minimum": "numbers",
    "maximum": "numbers",
    "year": "dates",
    "page_size": "lists",
    "max_bytes": "bodies",
    "depth": "bodies",
}


def limits_from(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, kind in FLAGS.items():
        value = getattr(args, name)
        if value is not None:
            if kind not in args.kind:
                raise SystemExit(f"--{name.replace('_', '-')} is a {kind} limit, but --kind {kind} was not asked for")
            out.setdefault(kind, {})[name] = value
    if args.seeded is not None:
        for kind in args.kind:
            out.setdefault(kind, {})["seeded"] = args.seeded
    return out


def emit(document: Any) -> None:
    print(json.dumps(document, indent=1, ensure_ascii=True, allow_nan=False))


def cmd_generate(args: argparse.Namespace) -> int:
    try:
        result = generate(args.kind, args.seed, limits_from(args))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    emit(summary(result) if args.summary else result)
    return 0


def cmd_labels(args: argparse.Namespace) -> int:
    kinds = set(args.kind or KINDS)
    emit({label: spec for label, spec in LABELS.items() if spec["kind"] in kinds})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edge_cases", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="labelled cases for one or more kinds")
    gen.add_argument("--kind", action="append", choices=KINDS, required=True)
    gen.add_argument("--seed", type=int, required=True)
    for name in FLAGS:
        gen.add_argument("--" + name.replace("_", "-"), dest=name, type=int, default=None)
    gen.add_argument("--seeded", type=int, default=None, help="seeded cases per kind")
    gen.add_argument("--summary", action="store_true", help="ids, labels, digests and sizes, without values")
    gen.set_defaults(func=cmd_generate)
    labels = sub.add_parser("labels", help="what every label tests and what a careful target does")
    labels.add_argument("--kind", action="append", choices=KINDS)
    labels.set_defaults(func=cmd_labels)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
