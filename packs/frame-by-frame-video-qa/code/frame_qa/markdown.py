"""REPORT.md for a film's findings: files, counts per detector, the top issues, sampled precision, how
findings map to shots, the transitions found, the reviewer's notes, and the method's limits."""

from __future__ import annotations

from .detectors import SEVERITY_RANK
from .report import rank_key
from .spec import DETECTORS


def _ts(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:05.2f}"


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def report_markdown(doc: dict, spec: dict, notes: str | None = None) -> str:
    cuts = doc["cuts"]
    everything = [f for cut in cuts for f in cut["findings"]]
    by_id = {f["id"]: f for f in everything}
    out: list[str] = []
    out.append("# Frame-by-frame video QA report")
    out.append("")
    out.append(f"Made by frame-by-frame video QA {doc['tool']['version']} with spec `{doc['spec_digest'][:12]}`"
               f"{' (with overrides)' if doc['spec_overrides'] else ''}. Every finding is a candidate a detector measured on "
               "the exact bytes named below; a person decides what it means. Notes are listed but never block.")
    out.append("")
    out.append("## Files")
    out.append("")
    out.append("| Cut | File | SHA-256 | Frames | Captions | Text engine |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    for cut in cuts:
        v = cut["video"]
        cap = f"{cut['captions']['path']} ({cut['captions']['cues']} cues)" if cut["captions"] else "none"
        out.append(f"| {cut['label']} | {v['path']} ({v['width']}x{v['height']}, {v['fps']:g} fps, {v['duration_s']:g} s) | "
                   f"`{v['sha256'][:16]}` | {cut['frames']} ({cut['spatial_frames']} with text measured) | {cap} | "
                   f"{cut['engine']['engine']} |")
    out.append("")
    out.append("## Counts per detector")
    out.append("")
    header = "| Detector | " + " | ".join(f"{c['label']}" for c in cuts) + " | Blocker | Major | Minor | Note |"
    out.append(header)
    out.append("| --- " * (len(cuts) + 5) + "|")
    for name in DETECTORS:
        rows = [f for f in everything if f["detector"] == name]
        per_cut = " | ".join(str(c["counts"][name]["findings"]) for c in cuts)
        sev = " | ".join(str(sum(1 for f in rows if f["severity"] == s)) for s in ("blocker", "major", "minor", "note"))
        out.append(f"| {name} | {per_cut} | {sev} |")
    total_cut = " | ".join(str(len(c["findings"])) for c in cuts)
    total_sev = " | ".join(str(sum(1 for f in everything if f["severity"] == s)) for s in ("blocker", "major", "minor", "note"))
    out.append(f"| **all** | {total_cut} | {total_sev} |")
    out.append("")
    kinds: dict[tuple[str, str], int] = {}
    for f in everything:
        kinds[(f["detector"], f["kind"])] = kinds.get((f["detector"], f["kind"]), 0) + 1
    out.append("By kind: " + "; ".join(f"{d}/{k} {n}" for (d, k), n in sorted(kinds.items())) + ".")
    out.append("")
    out.append("## Top issues")
    out.append("")
    out.append("Ranked by severity, then by how much a viewer depends on the detector's subject, then by duration.")
    out.append("")
    out.append("| # | Finding | Cut | Time | Shot | Storyboard | Severity | What | Text | Image |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for k, fid in enumerate(doc["top"], 1):
        f = by_id[fid]
        text = "; ".join(f.get("text") or [])[:80]
        image = f"[png]({f['image_path']})" if f.get("image_path") else ""
        out.append(f"| {k} | {f['id']} | {f['cut']} | {_ts(f['t_start'])}-{_ts(f['t_end'])} | {f['shot']} | "
                   f"{f.get('storyboard_shot') or ''} | {f['severity']} | {_cell(f['summary'])} | {_cell(text)} | {image} |")
    out.append("")
    out.append("## Precision from a sampled review")
    out.append("")
    review = doc.get("review")
    if not review:
        out.append("Not reviewed yet. A person or a different worker labels `review/sample.json` (each row `true_positive` or "
                   "`false_positive`, and whether it is actionable), then the report is rebuilt with `--labels`.")
    else:
        p = review["precision"]
        who = review.get("reviewer") or "unnamed reviewer"
        independent = "an independent reviewer" if review.get("independent") else "not independent of the tool's author"
        out.append(f"{p['labelled']} sampled findings were labelled by {who} ({independent}), from `{review['labels_file']}` "
                   f"(`{review['labels_sha256'][:12]}`). A true positive means the flagged condition is really in the frame; "
                   "actionable means a person would change the cut for it.")
        out.append("")
        out.append("| Detector | Findings | Labelled | True | False | Precision | Wilson 95% | Actionable | Estimated false findings |")
        out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for name in DETECTORS:
            row = p["detectors"].get(name)
            n_all = sum(1 for f in everything if f["detector"] == name)
            if not row:
                out.append(f"| {name} | {n_all} | 0 | | | not sampled | | | |")
                continue
            est = round(n_all * (1 - row["precision"]))
            interval = f"{row['wilson_95'][0]:.2f}-{row['wilson_95'][1]:.2f}" if row["wilson_95"] else ""
            out.append(f"| {name} | {n_all} | {row['labelled']} | {row['true_positive']} | {row['false_positive']} | "
                       f"{row['precision']:.2f} | {interval} | {row['actionable']} | {est} |")
        o = p["overall"]
        if o["precision"] is not None:
            interval = f"{o['wilson_95'][0]:.2f}-{o['wilson_95'][1]:.2f}"
            out.append(f"| **all** | {len(everything)} | {o['labelled']} | {o['true_positive']} | {o['labelled'] - o['true_positive']} | "
                       f"{o['precision']:.2f} | {interval} | {o['actionable']} | {round(len(everything) * (1 - o['precision']))} |")
        out.append("")
        out.append("The false-finding estimate scales each detector's sampled false share to all its findings. With one to a few "
                   "labels per detector the intervals are wide; treat them as a first calibration, not a measured rate.")
    out.append("")
    out.append("## How findings map to shots")
    out.append("")
    for cut in cuts:
        out.append(f"### {cut['label']}")
        out.append("")
        out.append("Shots come from the detected cuts and dissolves; the storyboard column is the storyboard row whose start "
                   "time precedes the shot, when a storyboard was given.")
        out.append("")
        out.append("| Shot | Time | Storyboard | Major | Minor | Note | Worst finding |")
        out.append("| --- | --- | --- | --- | --- | --- | --- |")
        for shot in cut["shots"]:
            rows = [f for f in cut["findings"] if f["shot"] == shot["id"]]
            if not rows:
                continue
            worst = sorted(rows, key=rank_key)[0]
            board = sorted({f.get("storyboard_shot") for f in rows if f.get("storyboard_shot")})
            out.append(f"| {shot['id']} | {_ts(shot['start_s'])}-{_ts(shot['end_s'])} | {', '.join(board)} | "
                       f"{sum(1 for f in rows if f['severity'] in ('blocker', 'major'))} | {sum(1 for f in rows if f['severity'] == 'minor')} | "
                       f"{sum(1 for f in rows if f['severity'] == 'note')} | {worst['id']}: {_cell(worst['summary'][:90])} |")
        out.append("")
        tr = cut["transitions"]["counts"]
        out.append("Transitions measured: " + ", ".join(f"{n} {k}" for k, n in tr.items()) + ".")
        out.append("")
    if notes:
        out.append("## Reviewer's notes")
        out.append("")
        out.append(notes.strip())
        out.append("")
    out.append("## Method and limits")
    out.append("")
    s = spec["sampling"]
    out.append(f"- Every frame is decoded. Frame differences, black and blank frames, freezes, camera motion and edge density "
               f"are measured on every frame; text, panels and chips on every {s['spatial_every_frames']}nd frame. {s['why_every_second_frame']}")
    out.append(f"- {spec['text']['font_size_rule']}")
    out.append(f"- {spec['safe_areas']['rule']}")
    out.append("- Caption collisions use each cue's line position and an estimated player box; players draw captions differently, "
               "so text in the band beside the estimated box is reported as minor, under it as major.")
    out.append("- Contrast is measured on the encoded frame after chroma subsampling and anti-aliasing, so thin small text "
               "reads lower than its design colours.")
    out.append("- A detector sees pixels, not intent: a deliberately cropped page, a planned hold or a fade-out reads the same as "
               "a mistake. Severity follows the video review pack's guide; only a person approves a cut.")
    out.append("")
    return "\n".join(out)
