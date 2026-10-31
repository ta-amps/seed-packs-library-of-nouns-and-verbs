"""CLI entrypoint for deterministic multi-frame scene and cognitive video QA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .evaluators import (
    compile_scene_cognitive_report,
    evaluate_camera_and_slide_stability,
    evaluate_frosted_caption_geometry,
    evaluate_live_web_journey_provenance,
    evaluate_reading_speed_and_cognitive_load,
    evaluate_shot_dwell_and_transitions,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scene_cognitive_qa")
    parser.add_argument("--bundle", type=Path, required=True, help="JSON bundle of multi-frame scene, text, journey and caption observations.")
    args = parser.parse_args(argv)

    doc = json.loads(args.bundle.read_text(encoding="utf-8"))
    r_dwell = evaluate_shot_dwell_and_transitions(doc["shots"], doc.get("transitions", []))
    r_cam = evaluate_camera_and_slide_stability(doc["scene_tracks"])
    r_cog = evaluate_reading_speed_and_cognitive_load(doc["text_items"], doc["speech_cues"])
    r_web = evaluate_live_web_journey_provenance(doc["journeys"])
    r_cap = evaluate_frosted_caption_geometry(doc["caption_band"], doc["caption_cues"])
    summary = compile_scene_cognitive_report(
        media_sha256=doc["media_sha256"],
        dwell_and_transitions=r_dwell,
        slide_stability=r_cam,
        cognitive_load=r_cog,
        web_provenance=r_web,
        caption_geometry=r_cap,
    )
    out = {
        "summary": summary,
        "dwell_and_transitions": r_dwell,
        "slide_stability": r_cam,
        "cognitive_load": r_cog,
        "web_provenance": r_web,
        "caption_geometry": r_cap,
    }
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0 if summary["overall_verdict"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
