"""Command line for the frame-by-frame video QA verbs.

    python -m frame_qa film --dir FILM_FOLDER --out OUT            # every cut in a folder, one command
    python -m frame_qa run --video CUT.mp4 [--vtt CUT.vtt] --out OUT
    python -m frame_qa sample --video CUT.mp4 --cache DIR          # the sample verb alone
    python -m frame_qa detect --video CUT.mp4 --cache DIR --detector NAME --out hits.json
    python -m frame_qa cluster --cache DIR --hits hits.json [--hits ...] --label L --out findings.json
    python -m frame_qa review-sample --findings findings.json --size 20 --seed 1 --out sample.json
    python -m frame_qa precision --labels labels.json
    python -m frame_qa spec                                        # the default detector spec
    python -m frame_qa synth --out DIR                             # the made-up test clips

Nothing here publishes, uploads, enqueues or calls a model API; output goes only where --out points.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .captions import load_vtt
from .cluster import cluster_hits
from .detectors import DETECTOR_FUNCTIONS, Context, Hit, run_all, shots
from .media import MediaError, find_ffmpeg, probe
from .pipeline import OutputError, discover, guard_output, run_film
from .report import build_findings, dumps, parse_storyboard
from .review import draw_sample, precision
from .sampler import load, sample
from .spec import DEFAULT_SPEC, load_spec


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _storyboards(items: list[str]) -> dict[str, Path]:
    out = {}
    for item in items or []:
        label, _, path = item.partition("=")
        if not path:
            raise SystemExit("--storyboard takes LABEL=PATH")
        out[label] = Path(path)
    return out


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--spec", help="JSON file of spec overrides")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--engine", choices=["auto", "ocr", "cv"], default="auto")
    p.add_argument("--ffmpeg", help="FFmpeg executable (default: FRAME_QA_FFMPEG, imageio-ffmpeg, PATH)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m frame_qa", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    film = sub.add_parser("film", help="run every cut in a folder and write one report")
    film.add_argument("--dir", required=True, type=Path)
    film.add_argument("--out", required=True, type=Path)
    film.add_argument("--include", default="*.mp4")
    film.add_argument("--exclude", action="append", default=None, help="glob to skip (default: *open-captions*)")
    film.add_argument("--storyboard", action="append", default=[], help="LABEL=PATH of a markdown storyboard")
    film.add_argument("--cache", type=Path, help="measurement cache root (default: OUT/cache)")
    film.add_argument("--labels", type=Path, help="labelled review sample, for precision")
    film.add_argument("--notes", type=Path, help="reviewer's notes to include in REPORT.md")
    film.add_argument("--noticed-at", help="date for findings records (default: today, UTC)")
    film.add_argument("--sample-size", type=int, default=20)
    film.add_argument("--seed", type=int, default=1)
    _common(film)

    run = sub.add_parser("run", help="run one cut")
    run.add_argument("--video", required=True, type=Path)
    run.add_argument("--vtt", type=Path)
    run.add_argument("--label")
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--storyboard", type=Path)
    run.add_argument("--cache", type=Path)
    run.add_argument("--labels", type=Path)
    run.add_argument("--notes", type=Path)
    run.add_argument("--noticed-at")
    run.add_argument("--sample-size", type=int, default=20)
    run.add_argument("--seed", type=int, default=1)
    _common(run)

    smp = sub.add_parser("sample", help="measure every frame into a cache folder")
    smp.add_argument("--video", required=True, type=Path)
    smp.add_argument("--cache", required=True, type=Path)
    _common(smp)

    det = sub.add_parser("detect", help="run one detector (or all) on a cache and write its hits")
    det.add_argument("--video", required=True, type=Path)
    det.add_argument("--cache", required=True, type=Path)
    det.add_argument("--vtt", type=Path)
    det.add_argument("--detector", choices=sorted(DETECTOR_FUNCTIONS), action="append")
    det.add_argument("--out", required=True, type=Path)
    det.add_argument("--spec")

    clu = sub.add_parser("cluster", help="join hits into findings for one cut")
    clu.add_argument("--cache", required=True, type=Path)
    clu.add_argument("--hits", required=True, type=Path, action="append")
    clu.add_argument("--label", required=True)
    clu.add_argument("--storyboard", type=Path)
    clu.add_argument("--noticed-at", default="1970-01-01")
    clu.add_argument("--out", required=True, type=Path)
    clu.add_argument("--spec")

    rs = sub.add_parser("review-sample", help="draw a seeded, stratified sample of findings to label")
    rs.add_argument("--findings", required=True, type=Path)
    rs.add_argument("--size", type=int, default=20)
    rs.add_argument("--seed", type=int, default=1)
    rs.add_argument("--out", required=True, type=Path)

    pr = sub.add_parser("precision", help="precision per detector from a labelled sample")
    pr.add_argument("--labels", required=True, type=Path)

    sub.add_parser("spec", help="print the default detector spec")

    syn = sub.add_parser("synth", help="render the made-up test clips")
    syn.add_argument("--out", required=True, type=Path)
    syn.add_argument("--ffmpeg")

    args = parser.parse_args(argv)
    try:
        if args.command == "spec":
            print(dumps(DEFAULT_SPEC), end="")
            return 0
        if args.command == "film":
            exclude = args.exclude if args.exclude is not None else ["*open-captions*"]
            pairs = discover(args.dir, args.include, exclude)
            if not pairs:
                raise SystemExit(f"no video matching {args.include} in {args.dir}")
            doc = run_film(pairs, args.out, spec_path=args.spec, cache_root=args.cache, workers=args.workers, engine=args.engine,
                           storyboards=_storyboards(args.storyboard), noticed_at=args.noticed_at, labels_path=args.labels,
                           notes_path=args.notes, sample_size=args.sample_size, seed=args.seed, log=_log, ffmpeg=args.ffmpeg)
            print(json.dumps({"findings": sum(len(c["findings"]) for c in doc["cuts"]), "out": str(args.out)}))
            return 0
        if args.command == "run":
            label = [args.label] if args.label else None
            boards = {args.label or args.video.stem.split("-")[-1]: args.storyboard} if args.storyboard else {}
            doc = run_film([(args.video, args.vtt)], args.out, spec_path=args.spec, cache_root=args.cache, workers=args.workers,
                           engine=args.engine, storyboards=boards, noticed_at=args.noticed_at, labels_path=args.labels,
                           notes_path=args.notes, sample_size=args.sample_size, seed=args.seed, log=_log, ffmpeg=args.ffmpeg,
                           labels=label)
            print(json.dumps({"findings": sum(len(c["findings"]) for c in doc["cuts"]), "out": str(args.out)}))
            return 0
        if args.command == "sample":
            guard_output(args.cache)
            meta = sample(args.video, load_spec(args.spec), args.cache, workers=args.workers, engine=args.engine,
                          ffmpeg=args.ffmpeg, log=_log)
            print(json.dumps({"frames": meta.get("frames"), "cache": str(args.cache)}))
            return 0
        if args.command == "detect":
            guard_output(args.out.parent)
            spec = load_spec(args.spec)
            meta, temporal, records = load(args.cache)
            info = meta["video"]
            cues = load_vtt(args.vtt) if args.vtt else []
            ctx = Context(info["width"], info["height"], info["fps"], len(records), spec, temporal, records, cues)
            hits = run_all(ctx, only=args.detector)
            args.out.write_text(dumps({"format": "frame-qa.hits.v1", "video_sha256": info["sha256"], "detectors": args.detector or sorted(DETECTOR_FUNCTIONS),
                                       "hits": [asdict(h) for h in hits]}), encoding="utf-8")
            print(json.dumps({"hits": len(hits)}))
            return 0
        if args.command == "cluster":
            guard_output(args.out.parent)
            spec = load_spec(args.spec)
            meta, temporal, records = load(args.cache)
            info = meta["video"]
            hits = []
            for path in args.hits:
                doc = json.loads(path.read_text(encoding="utf-8"))
                if doc.get("video_sha256") != info["sha256"]:
                    raise SystemExit(f"{path} is about different bytes than the cache")
                for h in doc["hits"]:
                    hits.append(Hit(h["detector"], h["kind"], h["frame"], h["severity"], tuple(h["box"]) if h["box"] else None,
                                    h["score"], h["detail"], h["key"]))
            ctx = Context(info["width"], info["height"], info["fps"], len(records), spec, temporal, records, [])
            run_all(ctx, only=[])
            clusters = cluster_hits(hits, spec, info["fps"])
            board = parse_storyboard(args.storyboard.read_text(encoding="utf-8")) if args.storyboard else []
            findings = build_findings(clusters, args.label, info["fps"], info["width"], info["height"], len(records), shots(ctx),
                                      board, info["path"], args.noticed_at)
            args.out.write_text(dumps({"format": "frame-qa.cut-findings.v1", "video_sha256": info["sha256"], "findings": findings}), encoding="utf-8")
            print(json.dumps({"findings": len(findings)}))
            return 0
        if args.command == "review-sample":
            guard_output(args.out.parent)
            doc = json.loads(args.findings.read_text(encoding="utf-8"))
            findings = [f for cut in doc.get("cuts", []) for f in cut["findings"]] or doc.get("findings", [])
            rows = draw_sample(findings, args.size, args.seed)
            args.out.write_text(dumps({"format": "frame-qa.review-sample.v1", "seed": args.seed, "size": args.size, "rows": rows}), encoding="utf-8")
            print(json.dumps({"rows": len(rows)}))
            return 0
        if args.command == "precision":
            labelled = json.loads(args.labels.read_text(encoding="utf-8"))
            print(dumps(precision(labelled["rows"])), end="")
            return 0
        if args.command == "synth":
            guard_output(args.out)
            from .synth import make_clips

            clips = make_clips(find_ffmpeg(args.ffmpeg), args.out)
            print(json.dumps({k: str(v) for k, v in clips.items()}))
            return 0
    except (MediaError, OutputError, ValueError, FileNotFoundError) as exc:
        print(f"frame_qa: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
