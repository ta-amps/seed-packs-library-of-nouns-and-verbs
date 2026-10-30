"""Command line for the explainer checks. Reads JSON nouns, prints results, writes only where told.

  python -m explainer_checks clock --cut-plan PLAN.json --cut 20s [--track TRACK.json]
  python -m explainer_checks captions --cut-plan PLAN.json --cut 20s --track TRACK.json --out DIR
  python -m explainer_checks manifest --root DIR --cut 20s --title TITLE --out FILE --entry PATH ROLE TYPE ...
  python -m explainer_checks verify --manifest FILE --root DIR
  python -m explainer_checks ledger --ledger FILE [--steps a,b]

Each command exits 1 when it finds a problem. Outputs are refused inside the seed-pack library.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .captions import build_cues, check_cues, to_srt, to_webvtt
from .clock import beat_spans, check_cut, check_narration, clip_spans, frame_sheet_times
from .release import check_ledger, file_entry, missing_receipts, verify_manifest


def library_root() -> Path | None:
    """The seed-pack library this code sits in, if any: a folder with packs/ and scripts/build_packs.py."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "packs").is_dir() and (parent / "scripts" / "build_packs.py").is_file():
            return parent
    return None


def output_path(path: Path) -> Path:
    target = path.resolve()
    root = library_root()
    if root is not None and target.is_relative_to(root):
        raise SystemExit(f"refusing to write inside the seed-pack library: {target}")
    return target


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_cut(plan: dict[str, Any], cut_id: str) -> dict[str, Any]:
    for cut in plan["cuts"]:
        if cut["cut_id"] == cut_id:
            return cut
    raise SystemExit(f"no cut {cut_id!r} in the cut plan")


def cmd_clock(args: argparse.Namespace) -> int:
    plan = load(args.cut_plan)
    cut = find_cut(plan, args.cut)
    fps = plan["fps"]
    problems = check_cut(cut, fps, {beat["beat_id"] for beat in plan["beats"]})
    if args.track:
        problems += check_narration(cut, fps, load(args.track)["placements"])
    print(json.dumps({"cut": args.cut, "clips": clip_spans(cut, fps), "beats": beat_spans(cut, fps),
                      "frame_sheet_times": frame_sheet_times(cut, fps), "problems": problems}, indent=1))
    return 1 if problems else 0


def cmd_captions(args: argparse.Namespace) -> int:
    plan = load(args.cut_plan)
    cut = find_cut(plan, args.cut)
    fps = plan["fps"]
    track = load(args.track)
    cues = build_cues(track["placements"], cut["duration_s"], fps)
    problems = check_cues(cues, fps)
    out = output_path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    vtt, srt = to_webvtt(cues, fps).encode("utf-8"), to_srt(cues, fps).encode("utf-8")
    (out / f"captions-{args.cut}.vtt").write_bytes(vtt)
    (out / f"captions-{args.cut}.srt").write_bytes(srt)
    record = {"cut_id": args.cut, "fps": fps, "cues": cues, "rule_problems": problems,
              "webvtt": file_entry(f"captions-{args.cut}.vtt", vtt, "webvtt", "text/vtt"),
              "srt": file_entry(f"captions-{args.cut}.srt", srt, "srt", "application/x-subrip")}
    (out / f"captions-{args.cut}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"cues": len(cues), "rule_problems": problems, "webvtt_sha256": record["webvtt"]["sha256"]}))
    return 1 if problems else 0


def cmd_manifest(args: argparse.Namespace) -> int:
    files = [file_entry(path, (args.root / path).read_bytes(), role, media_type) for path, role, media_type in args.entry]
    manifest = {"title": args.title, "cut_id": args.cut, "files": files, "disclosures": args.disclosure or [],
                "released": False}
    target = output_path(args.out)
    target.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(files), "out": str(target)}))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    problems = verify_manifest(load(args.manifest), lambda path: (args.root / path).read_bytes())
    print(json.dumps({"problems": problems}))
    return 1 if problems else 0


def cmd_ledger(args: argparse.Namespace) -> int:
    ledger = load(args.ledger)
    steps = [s for s in args.steps.split(",") if s] if args.steps else None
    problems = check_ledger(ledger) if steps is None else [f"{s}: no receipt" for s in missing_receipts(ledger, steps)]
    print(json.dumps({"problems": problems}))
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="explainer_checks", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    clock = sub.add_parser("clock", help="clip and beat spans, frame sheet times and clock problems")
    clock.add_argument("--cut-plan", type=Path, required=True)
    clock.add_argument("--cut", required=True)
    clock.add_argument("--track", type=Path)
    captions = sub.add_parser("captions", help="cues, WebVTT and SRT from a narration track")
    captions.add_argument("--cut-plan", type=Path, required=True)
    captions.add_argument("--cut", required=True)
    captions.add_argument("--track", type=Path, required=True)
    captions.add_argument("--out", type=Path, required=True)
    manifest = sub.add_parser("manifest", help="hash delivered files into a release manifest")
    manifest.add_argument("--root", type=Path, required=True)
    manifest.add_argument("--cut", required=True)
    manifest.add_argument("--title", required=True)
    manifest.add_argument("--out", type=Path, required=True)
    manifest.add_argument("--entry", nargs=3, action="append", required=True, metavar=("PATH", "ROLE", "MEDIA_TYPE"))
    manifest.add_argument("--disclosure", action="append")
    verify = sub.add_parser("verify", help="check files against a release manifest")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--root", type=Path, required=True)
    ledger = sub.add_parser("ledger", help="steps without a receipt")
    ledger.add_argument("--ledger", type=Path, required=True)
    ledger.add_argument("--steps")
    args = parser.parse_args(argv)
    commands = {"clock": cmd_clock, "captions": cmd_captions, "manifest": cmd_manifest, "verify": cmd_verify,
                "ledger": cmd_ledger}
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
