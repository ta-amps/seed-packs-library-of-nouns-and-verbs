"""Command line: check a snapshot, then print its measures, liquidity screens or roll candidates as JSON.

  python -m chain_measures check --request REQUEST.json --snapshot SNAPSHOT.json --history HISTORY.json
  python -m chain_measures measures --request REQUEST.json --snapshot SNAPSHOT.json --history HISTORY.json
  python -m chain_measures screen --request REQUEST.json --snapshot SNAPSHOT.json --history HISTORY.json
  python -m chain_measures candidates --request REQUEST.json --snapshot SNAPSHOT.json --history HISTORY.json
  python -m chain_measures iv-rank --history HISTORY.json --lookback 252 --min-observations 200

It reads only the files named and writes only to standard output. check exits 1 when it finds a problem;
the other commands exit 1 with the problems when the snapshot fails its check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .chain import check_snapshot, measures, roll_candidates, screen
from .ivrank import iv_rank


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chain_measures", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("check", "problems that stop a review"), ("measures", "every number the review may cite"),
                       ("screen", "the liquidity screens for every contract"),
                       ("candidates", "roll candidates compared with the reference contract")):
        command = sub.add_parser(name, help=text)
        for flag in ("--request", "--snapshot", "--history"):
            command.add_argument(flag, type=Path, required=True)
    rank = sub.add_parser("iv-rank", help="rank and percentile of the last observation")
    rank.add_argument("--history", type=Path, required=True)
    rank.add_argument("--lookback", type=int, default=252)
    rank.add_argument("--min-observations", type=int, default=200)
    args = parser.parse_args(argv)
    if args.command == "iv-rank":
        history = load(args.history)
        print(json.dumps(iv_rank(history["observations"], args.lookback, args.min_observations), indent=1))
        return 0
    request, snapshot, history = load(args.request), load(args.snapshot), load(args.history)
    problems = check_snapshot(request, snapshot, history)
    if args.command == "check" or problems:
        print(json.dumps({"problems": problems}, indent=1))
        return 1 if problems else 0
    measured = measures(request, snapshot, history)
    if args.command == "measures":
        print(json.dumps(measured, indent=1))
        return 0
    screened = screen(request, measured)
    if args.command == "screen":
        print(json.dumps(screened, indent=1))
        return 0
    print(json.dumps(roll_candidates(request, measured, screened), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
