"""Command line for the extended video QA checks. Reads files, prints JSON rows, writes only where told.

  python -m video_qa_checks captions --vtt FILE [--srt FILE] [--speech FILE] [--fps 30] [--duration-s S]
  python -m video_qa_checks picture --plan PLAN --black LOG --freeze LOG [--ymin FILE --ymax FILE] [--scenes FILE]
  python -m video_qa_checks sound --plan PLAN --ebur128 LOG [--silence LOG] [--astats LOG] [--target-lufs -16]
  python -m video_qa_checks filespec --mp4 FILE --spec SPEC
  python -m video_qa_checks legibility --items ITEMS
  python -m video_qa_checks report --media FILE --plan PLAN --part FILE [--part FILE ...] --out FILE

Logs come from the FFmpeg runs in the pack's measurement rules; this code never runs FFmpeg. Each command
exits 1 when a row fails. Outputs are refused inside the seed-pack library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from . import captions, checks, ffmpeg_logs, mp4, report, rows


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


def read(path: Path | None) -> str:
    return "" if path is None else path.read_text(encoding="utf-8", errors="replace")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> dict[str, str]:
    return {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def captions_row(args: argparse.Namespace) -> dict[str, Any]:
    speech = load(args.speech)["speech_ms"] if args.speech else None
    duration_ms = None if args.duration_s is None else round(args.duration_s * 1000)
    return rows.captions_row(read(args.vtt), read(args.srt) if args.srt else None, speech,
                             {"fps": args.fps, "max_cps": args.max_cps}, duration_ms)


def picture_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    ymin = ffmpeg_logs.parse_metadata_print(read(args.ymin), "lavfi.signalstats.YMIN")
    ymax = ffmpeg_logs.parse_metadata_print(read(args.ymax), "lavfi.signalstats.YMAX")
    scores = ffmpeg_logs.parse_metadata_print(read(args.scenes), "lavfi.scene_score")
    log = read(args.black) if args.black == args.freeze else read(args.black) + "\n" + read(args.freeze)
    return rows.picture_rows(load(args.plan), log, ymin, ymax, scores)


def sound_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    return rows.sound_rows(load(args.plan), read(args.ebur128), read(args.silence) if args.silence else None,
                           read(args.astats) if args.astats else None, {"target_lufs": args.target_lufs})


def filespec_row(args: argparse.Namespace) -> dict[str, Any]:
    return rows.filespec_row(mp4.probe(args.mp4), load(args.spec))


def legibility_row(args: argparse.Namespace) -> dict[str, Any]:
    return rows.legibility_row(load(args.items))


def emit(result: Any, out: Path | None) -> None:
    text = json.dumps(result, indent=1, ensure_ascii=False)
    if out is not None:
        output_path(out).write_text(text + "\n", encoding="utf-8")
    print(text)


def failed(rows: list[dict[str, Any]]) -> int:
    return 1 if any(r["result"] == "fail" for r in rows) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="video_qa_checks", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("captions", help="lint WebVTT and SRT sidecars and time them against speech")
    cap.add_argument("--vtt", type=Path, required=True)
    cap.add_argument("--srt", type=Path)
    cap.add_argument("--speech", type=Path, help='JSON {"speech_ms": [[start, end], ...]}')
    cap.add_argument("--fps", type=int, default=30)
    cap.add_argument("--max-cps", type=float, default=captions.DEFAULT_LIMITS["max_cps"])
    cap.add_argument("--duration-s", type=float)
    pic = sub.add_parser("picture", help="blank, frozen and cadence rows from FFmpeg logs")
    pic.add_argument("--plan", type=Path, required=True)
    pic.add_argument("--black", type=Path, required=True)
    pic.add_argument("--freeze", type=Path, required=True)
    pic.add_argument("--ymin", type=Path)
    pic.add_argument("--ymax", type=Path)
    pic.add_argument("--scenes", type=Path)
    snd = sub.add_parser("sound", help="loudness, silence and clipping rows from FFmpeg logs")
    snd.add_argument("--plan", type=Path, required=True)
    snd.add_argument("--ebur128", type=Path, required=True)
    snd.add_argument("--silence", type=Path)
    snd.add_argument("--astats", type=Path)
    snd.add_argument("--target-lufs", type=float, default=checks.DEFAULTS["target_lufs"])
    spec = sub.add_parser("filespec", help="an MP4's boxes against a delivery spec")
    spec.add_argument("--mp4", type=Path, required=True)
    spec.add_argument("--spec", type=Path, required=True)
    leg = sub.add_parser("legibility", help="text size, reading time and safe areas for known text items")
    leg.add_argument("--items", type=Path, required=True)
    rep = sub.add_parser("report", help="combine rows into one report bound to the file's SHA-256")
    rep.add_argument("--media", type=Path, required=True)
    rep.add_argument("--plan", type=Path, required=True)
    rep.add_argument("--part", type=Path, action="append", required=True)
    for item in (cap, pic, snd, spec, leg, rep):
        item.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "captions":
        result = [captions_row(args)]
    elif args.command == "picture":
        result = picture_rows(args)
    elif args.command == "sound":
        result = sound_rows(args)
    elif args.command == "filespec":
        result = [filespec_row(args)]
    elif args.command == "legibility":
        result = [legibility_row(args)]
    else:
        parts: list[dict[str, Any]] = []
        for path in args.part:
            data = load(path)
            parts += data if isinstance(data, list) else [data]
        media = {"file": args.media.name, "bytes": args.media.stat().st_size, "sha256": report.sha256_file(args.media)}
        compiled = report.compile_report(media, load(args.plan), parts, [digest(p) for p in args.part])
        emit(compiled, args.out)
        return 1 if compiled["verdict"] == "fail" else 0
    emit(result if len(result) > 1 else result[0], args.out)
    return failed(result)


if __name__ == "__main__":
    sys.exit(main())
