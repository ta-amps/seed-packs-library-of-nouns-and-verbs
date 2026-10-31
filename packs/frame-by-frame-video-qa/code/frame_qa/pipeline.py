"""One command for a cut or a whole film folder: sample, detect, cluster, annotate and report.

The verbs stay separate steps a worker can run on their own (see __main__); this module only runs them in
order for one person's local use. It writes only under the output folder it is given.
"""

from __future__ import annotations

import datetime as _dt
import fnmatch
import hashlib
import json
from pathlib import Path

from . import __version__
from .annotate import render_all
from .captions import load_vtt
from .cluster import cluster_hits
from .detectors import Context, run_all, shots as find_shots
from .media import find_ffmpeg, probe
from .report import FINDINGS_FORMAT, attach_records, build_findings, counts, draw_timeline, dumps, parse_storyboard, rank_key, write_timeline_csv
from .review import draw_sample, precision
from .sampler import load, sample
from .spec import load_spec, spec_digest
from .text import make_engine
from .markdown import report_markdown


class OutputError(ValueError):
    """The output folder is not allowed."""


def guard_output(out: Path) -> None:
    """Refuse an output folder inside a seed-pack library checkout: the library only ever holds packs."""
    for parent in [out.resolve(), *out.resolve().parents]:
        if (parent / "scripts" / "build_packs.py").is_file() and (parent / "packs").is_dir():
            raise OutputError(f"refusing to write inside the seed-pack library at {parent}")


def label_for(path: Path, others: list[Path]) -> str:
    token = path.stem.split("-")[-1] or path.stem
    if sum(1 for p in others if (p.stem.split("-")[-1] or p.stem) == token) > 1:
        return path.stem
    return token


def analyze_cut(video: Path, out: Path, *, label: str, vtt: Path | None, spec: dict, cache: Path, workers: int,
                engine: str, storyboard: Path | None, noticed_at: str, log=print, ffmpeg: str | None = None) -> dict:
    ffmpeg = find_ffmpeg(ffmpeg)
    meta = sample(video, spec, cache, workers=workers, engine=engine, ffmpeg=ffmpeg, log=log)
    meta, temporal, records = load(cache)
    info = probe(video, ffmpeg)
    if info.sha256 != meta["video"]["sha256"]:
        raise RuntimeError("the measurements are of different bytes than the video")
    cues = load_vtt(vtt) if vtt else []
    ctx = Context(info.width, info.height, info.fps, len(records), spec, temporal, records, cues)
    hits = run_all(ctx)
    clusters = cluster_hits(hits, spec, info.fps)
    shot_list = find_shots(ctx)
    board = parse_storyboard(storyboard.read_text(encoding="utf-8")) if storyboard else []
    findings = build_findings(clusters, label, info.fps, info.width, info.height, len(records), shot_list, board, video.name, noticed_at)
    images = out / "images" / label
    recognizer = None
    engine_obj = make_engine(engine)
    if getattr(engine_obj, "name", "") == "ocr":
        recognizer = engine_obj.recognize
    render_all(video, ffmpeg, info, findings, spec, images, recognizer=recognizer, log=log)
    for f in findings:
        f["cut"] = label
        f["image_path"] = f"images/{label}/{f['image']}" if f.get("image") else None
        f.pop("frames_total", None)
    attach_records(findings, label, video.name, noticed_at)
    vtt_info = None
    if vtt:
        data = vtt.read_bytes()
        vtt_info = {"path": vtt.name, "sha256": hashlib.sha256(data).hexdigest(), "cues": len(cues)}
    types: dict[str, int] = {}
    for event in ctx.transitions:
        types[event["type"]] = types.get(event["type"], 0) + 1
    return {
        "label": label,
        "video": meta["video"],
        "captions": vtt_info,
        "engine": meta["engine"],
        "frames": len(records),
        "spatial_frames": sum(1 for r in records if "text" in r),
        "transitions": {"counts": dict(sorted(types.items())), "events": ctx.transitions},
        "shots": shot_list,
        "storyboard": board,
        "counts": counts(findings),
        "findings": findings,
        "meta": {"ffmpeg": meta["ffmpeg"], "versions": meta["versions"], "sampling_digest": meta["sampling_digest"],
                 "detector_digest": meta.get("detector_digest")},
    }


def discover(folder: Path, include: str, exclude: list[str]) -> list[tuple[Path, Path | None]]:
    videos = sorted(p for p in folder.iterdir() if p.is_file() and fnmatch.fnmatch(p.name, include)
                    and not any(fnmatch.fnmatch(p.name, pattern) for pattern in exclude))
    pairs = []
    for video in videos:
        vtt = video.with_suffix(".vtt")
        pairs.append((video, vtt if vtt.is_file() else None))
    return pairs


def run_film(videos: list[tuple[Path, Path | None]], out: Path, *, spec_path: str | None = None, cache_root: Path | None = None,
             workers: int = 4, engine: str = "auto", storyboards: dict[str, Path] | None = None, noticed_at: str | None = None,
             labels_path: Path | None = None, notes_path: Path | None = None, sample_size: int = 20, seed: int = 1,
             log=print, ffmpeg: str | None = None, labels: list[str] | None = None) -> dict:
    guard_output(out)
    out.mkdir(parents=True, exist_ok=True)
    spec = load_spec(spec_path)
    noticed_at = noticed_at or _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    cache_root = cache_root or (out / "cache")
    storyboards = storyboards or {}
    cuts = []
    paths = [v for v, _ in videos]
    for k, (video, vtt) in enumerate(videos):
        label = labels[k] if labels else label_for(video, paths)
        log(f"film: {label}: {video.name}" + (f" with {vtt.name}" if vtt else " without captions"))
        cuts.append(analyze_cut(video, out, label=label, vtt=vtt, spec=spec, cache=cache_root / label, workers=workers,
                                engine=engine, storyboard=storyboards.get(label), noticed_at=noticed_at, log=log, ffmpeg=ffmpeg))
    for cut in cuts:
        draw_timeline(out / f"timeline-{cut['label']}.png", cut)
    write_timeline_csv(out / "timeline.csv", cuts)
    everything = [f for cut in cuts for f in cut["findings"]]
    sample_rows = draw_sample(everything, sample_size, seed)
    review_dir = out / "review"
    review_dir.mkdir(exist_ok=True)
    (review_dir / "sample.json").write_text(dumps({"format": "frame-qa.review-sample.v1", "seed": seed, "size": sample_size,
                                                   "rows": sample_rows}), encoding="utf-8")
    review = None
    if labels_path and labels_path.is_file():
        labelled = json.loads(labels_path.read_text(encoding="utf-8"))
        review = {"labels_file": labels_path.name, "labels_sha256": hashlib.sha256(labels_path.read_bytes()).hexdigest(),
                  "reviewer": labelled.get("reviewer"), "independent": labelled.get("independent"),
                  "precision": precision(labelled["rows"])}
    doc = {
        "format": FINDINGS_FORMAT,
        "tool": {"name": "frame-by-frame video QA", "version": __version__},
        "spec_digest": spec_digest(spec),
        "spec_overrides": spec_path is not None,
        "noticed_at": noticed_at,
        "cuts": cuts,
        "top": [f["id"] for f in sorted(everything, key=rank_key)[:15]],
        "review": review,
    }
    (out / "findings.json").write_text(dumps(doc), encoding="utf-8")
    notes = notes_path.read_text(encoding="utf-8") if notes_path and notes_path.is_file() else None
    (out / "REPORT.md").write_text(report_markdown(doc, spec, notes), encoding="utf-8")
    log(f"film: wrote {out / 'findings.json'} with {len(everything)} findings")
    return doc
