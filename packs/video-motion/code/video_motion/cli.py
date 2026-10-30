"""Command-line interface for the video and motion tools: recipes, rendering, every-frame QA, motion learning and demo."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from video_motion.errors import VideoMotionError
from video_motion.media import MediaAsset, materialize_generated
from video_motion.motion import learn_motion_profile, retarget_motion
from video_motion.qa import audit_recipe
from video_motion.schemas import (
    AspectId,
    AssetAttribution,
    CastMember,
    MotionObservationTrace,
    SceneRecipe,
    canonical_sha256,
)
from video_motion.sequence import VideoSequence, audit_sequence, plan_sequence
from video_motion.social import (
    ConceptBrief,
    ConceptRoleSpec,
    SceneFactory,
    compile_deliverable,
    examples_dir,
    load_bundled_recipes,
    load_sample_motion_trace,
    write_deliverable_bundle,
)
from video_motion.timeline import evaluate_frame


def _parse_aspects(raw: str) -> list[AspectId]:
    out: list[AspectId] = []
    for item in (part.strip() for part in raw.split(",") if part.strip()):
        if item == "reels_9x16":
            out.append("reels_9x16")
        elif item == "feed_4x5":
            out.append("feed_4x5")
        elif item == "landscape_16x9":
            out.append("landscape_16x9")
        else:
            msg = f"Unsupported aspect {item!r}; expected reels_9x16, feed_4x5 or landscape_16x9."
            raise ValueError(msg)
    return out or ["reels_9x16", "feed_4x5"]


def _cmd_recipes() -> int:
    recipes = load_bundled_recipes()
    for recipe in recipes:
        print(
            f"{recipe.recipe_id:30s}  {recipe.duration_s:5.1f}s @ {recipe.fps}fps "
            f"({recipe.total_frames:3d}f)  actors={len(recipe.actors)}  "
            f"captions={len(recipe.captions)}  {recipe.title}"
        )
    return 0


def _cmd_render(recipe_path: Path, out_dir: Path, aspects: list[AspectId]) -> int:
    recipe = SceneRecipe.model_validate(json.loads(recipe_path.read_text(encoding="utf-8")))
    deliverable = compile_deliverable(recipe, aspects=aspects, require_qa_pass=True)
    written = write_deliverable_bundle(deliverable, out_dir)
    summary = {
        "recipe_id": recipe.recipe_id,
        "out_dir": str(out_dir),
        "aspects": list(deliverable.aspects.keys()),
        "qa_passed": deliverable.qa_report.passed,
        "qa_score": deliverable.qa_report.score,
        "qa_receipt_sha256": deliverable.qa_report.qa_receipt_sha256,
        "bundle_sha256": deliverable.post_manifest.bundle_sha256,
        "files_written": sorted(p.relative_to(out_dir).as_posix() for p in written.values()),
    }
    print(json.dumps(summary, indent=2))
    return 0


def _cmd_qa(recipe_path: Path, aspects: list[AspectId]) -> int:
    recipe = SceneRecipe.model_validate(json.loads(recipe_path.read_text(encoding="utf-8")))
    report = audit_recipe(recipe, aspects=aspects)
    print(json.dumps(report.model_dump(), indent=2))
    return 0 if report.passed else 1


def _cmd_learn(trace_path: Path, out_path: Path | None) -> int:
    trace = MotionObservationTrace.model_validate(
        json.loads(trace_path.read_text(encoding="utf-8"))
    )
    profile = learn_motion_profile(trace)
    serialized = json.dumps(profile.model_dump(), indent=2, sort_keys=True) + "\n"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


def _verify_random_access_order_invariance(recipe: SceneRecipe) -> str:
    indices = list(range(recipe.total_frames))
    forward = [evaluate_frame(recipe, i, aspect="reels_9x16").frame_hash_sha256 for i in indices]
    backward_map = {
        i: evaluate_frame(recipe, i, aspect="reels_9x16").frame_hash_sha256
        for i in reversed(indices)
    }
    shuffled = sorted(
        indices,
        key=lambda idx: hashlib.sha256(f"{recipe.seed}:{idx}".encode()).hexdigest(),
    )
    shuffled_map = {
        i: evaluate_frame(recipe, i, aspect="reels_9x16").frame_hash_sha256 for i in shuffled
    }
    for i in indices:
        if forward[i] != backward_map[i] or forward[i] != shuffled_map[i]:
            msg = f"Non-deterministic frame evaluation detected at frame {i} of {recipe.recipe_id}"
            raise RuntimeError(msg)
    return hashlib.sha256(":".join(forward).encode("utf-8")).hexdigest()


def _cmd_demo(out_root: Path | None) -> int:
    target_root = (
        out_root if out_root is not None else Path(tempfile.mkdtemp(prefix="video-motion-demo-"))
    )
    recipes = load_bundled_recipes()

    # 1. Prove order-invariant frame-addressable determinism + dual-aspect compilation on all 3 examples
    compiled_summaries: list[dict[str, object]] = []
    for recipe in recipes:
        timeline_sha = _verify_random_access_order_invariance(recipe)
        deliverable = compile_deliverable(recipe, aspects=("reels_9x16", "feed_4x5"))
        write_deliverable_bundle(deliverable, target_root / recipe.recipe_id)
        compiled_summaries.append(
            {
                "recipe_id": recipe.recipe_id,
                "frames": recipe.total_frames,
                "order_invariant_timeline_sha256": timeline_sha[:16],
                "qa_passed": deliverable.qa_report.passed,
                "qa_score": deliverable.qa_report.score,
                "qa_receipt_sha256": deliverable.qa_report.qa_receipt_sha256[:16],
                "bundle_sha256": deliverable.post_manifest.bundle_sha256[:16],
            }
        )

    # 2. Learn MotionProfile from synthetic observation trace & retarget to a new 12.0s scene
    trace = load_sample_motion_trace()
    learned_profile = learn_motion_profile(trace)
    retargeted = retarget_motion(
        learned_profile,
        cast=[
            CastMember(
                actor_id="host_lead",
                kind="character",
                label="Motion Host",
                asset_id="proc-motion-host",
                attribution=AssetAttribution(
                    asset_id="proc-motion-host",
                    license="LicenseRef-Video-Motion-Procedural",
                    creator="video-motion vector studio",
                    source_uri="urn:video-motion:procedural:motion-host",
                    sha256=canonical_sha256({"asset": "proc-motion-host"}),
                    digest_basis="procedural_definition",
                ),
                role_label="HOST",
                line_text="Learned beat ratios snap cleanly onto any target duration.",
            )
        ],
        duration_s=12.0,
        title="Retargeted 12s Cadence Scene",
    )
    retargeted_deliv = compile_deliverable(retargeted, aspects=("reels_9x16", "feed_4x5"))
    write_deliverable_bundle(retargeted_deliv, target_root / retargeted.recipe_id)

    # 3. License-gated SceneFactory casting & QA scorecard ranking
    factory = SceneFactory()
    winner, ranked = factory.cast_and_rank(
        ConceptBrief(
            brief_id="factory-demo",
            title="Factory Cast Dual-Aspect Showcase",
            synopsis="Cast from verified open-licensed catalog and ranked by every-frame QA.",
            duration_s=14.0,
            roles=[
                ConceptRoleSpec(
                    actor_id="lead_eng",
                    asset_id="char-sre-lead",
                    role_label="ENGINEER",
                    spoken_line="License-gated casting rejects unknown rights before frame zero.",
                ),
                ConceptRoleSpec(
                    actor_id="co_bot",
                    asset_id="char-deploy-bot",
                    role_label="BOT",
                    spoken_line="Candidate layouts are ranked by every-frame QA scorecards.",
                ),
            ],
        )
    )

    demo_report = {
        "demo": "video-motion-v0.1.0",
        "output_directory": str(target_root),
        "bundled_recipes_verified": compiled_summaries,
        "motion_learning": {
            "source_trace_id": trace.trace_id,
            "profile_id": learned_profile.profile_id,
            "dominant_easing": learned_profile.dominant_easing,
            "median_cut_cadence_s": learned_profile.median_cut_cadence_s,
            "profile_sha256": learned_profile.profile_sha256[:16],
            "retargeted_recipe_id": retargeted.recipe_id,
            "retargeted_qa_passed": retargeted_deliv.qa_report.passed,
        },
        "scene_factory": {
            "candidates_evaluated": len(ranked),
            "winning_recipe_id": winner.recipe_id,
            "winning_qa_score": ranked[0][1].score,
            "rejected_lower_ranked_score": ranked[-1][1].score,
        },
    }
    print(json.dumps(demo_report, indent=2))
    return 0


def _load_sequence(path: Path) -> VideoSequence:
    return VideoSequence.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _load_media_nouns(path: Path) -> list[MediaAsset]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [MediaAsset.model_validate(item) for item in raw["assets"]]


def _cmd_video_plan(sequence_path: Path) -> int:
    sequence = _load_sequence(sequence_path)
    plan = plan_sequence(sequence)
    reports = {aspect: audit_sequence(sequence, aspect) for aspect in sequence.outputs}
    print(
        json.dumps(
            {
                "plan": plan.model_dump(mode="json"),
                "prerender_qa": {a: r.model_dump(mode="json") for a, r in reports.items()},
            },
            indent=2,
        )
    )
    return 0 if all(r.passed for r in reports.values()) else 1


def _cmd_video_probe(ffmpeg: str | None, chromium: str | None) -> int:
    from video_motion.video_worker import Rasterizer, locate_ffmpeg, probe_ffmpeg, probe_playwright

    cards = [probe_ffmpeg(locate_ffmpeg(ffmpeg)), probe_playwright()]
    with Rasterizer(chromium) as raster:
        cards.insert(1, raster.card)
    print(json.dumps([card.model_dump(mode="json") for card in cards], indent=2))
    return 0 if not cards[0].missing_capabilities else 1


def _video_summary(out_dir: Path, reports: list[Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"out_dir": str(out_dir), "aspects": {}}
    for report in reports:
        manifest = json.loads((out_dir / report.aspect / "render-manifest.json").read_text("utf-8"))
        summary["aspects"][report.aspect] = {
            "mp4": manifest["outputs"]["mp4"],
            "mp4_sha256": manifest["outputs"]["mp4_sha256"],
            "mp4_bytes": manifest["outputs"]["mp4_bytes"],
            "frames": manifest["total_frames"],
            "qa_passed": report.passed,
            "qa_receipt_sha256": report.receipt_sha256,
            "checks": {c.check: {"passed": c.passed, "detail": c.detail} for c in report.checks},
        }
    summary["all_passed"] = all(r.passed for r in reports)
    return summary


def _cmd_video_render(
    sequence_path: Path,
    media_path: Path,
    out_dir: Path,
    aspects: list[AspectId] | None,
    processes: int,
    ffmpeg: str | None,
    chromium: str | None,
    check: bool,
) -> int:
    from video_motion.video_worker import check_rendered_video, render_sequence

    sequence = _load_sequence(sequence_path)
    library = materialize_generated(_load_media_nouns(media_path), out_dir / "library")
    manifests = render_sequence(
        sequence,
        library,
        out_dir / "render",
        aspects=aspects,
        ffmpeg=ffmpeg,
        chromium=chromium,
        processes=processes,
    )
    if not check:
        print(json.dumps([m.outputs for m in manifests], indent=2))
        return 0
    reports = [
        check_rendered_video(sequence, out_dir / "render", m.aspect, ffmpeg=ffmpeg)
        for m in manifests
    ]
    summary = _video_summary(out_dir / "render", reports)
    print(json.dumps(summary, indent=2))
    return 0 if summary["all_passed"] else 1


def _cmd_video_check(
    sequence_path: Path, render_dir: Path, aspects: list[AspectId] | None, ffmpeg: str | None
) -> int:
    from video_motion.video_worker import check_rendered_video

    sequence = _load_sequence(sequence_path)
    reports = [
        check_rendered_video(sequence, render_dir, aspect, ffmpeg=ffmpeg)
        for aspect in (aspects or sequence.outputs)
    ]
    summary = _video_summary(render_dir, reports)
    print(json.dumps(summary, indent=2))
    return 0 if summary["all_passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-motion",
        description="Video and motion tools: deterministic video-as-code, motion learning and every-frame QA.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("recipes", help="List bundled example SceneRecipe definitions")

    p_render = sub.add_parser(
        "render", help="Compile dual-aspect SVGs, captions, QA, and post.json"
    )
    p_render.add_argument("recipe", type=Path, help="Path to SceneRecipe JSON")
    p_render.add_argument("--out", type=Path, required=True, help="Output bundle directory")
    p_render.add_argument(
        "--aspects",
        default="reels_9x16,feed_4x5",
        help="Comma-separated aspect profiles (default: reels_9x16,feed_4x5)",
    )

    p_qa = sub.add_parser("qa", help="Run the 8-check deterministic every-frame QA gate")
    p_qa.add_argument("recipe", type=Path, help="Path to SceneRecipe JSON")
    p_qa.add_argument(
        "--aspects",
        default="reels_9x16,feed_4x5",
        help="Comma-separated aspect profiles (default: reels_9x16,feed_4x5)",
    )

    p_learn = sub.add_parser(
        "learn", help="Learn a reusable MotionProfile from an observation trace"
    )
    p_learn.add_argument("trace", type=Path, help="Path to MotionObservationTrace JSON")
    p_learn.add_argument(
        "--out", type=Path, default=None, help="Optional output file for MotionProfile JSON"
    )

    p_demo = sub.add_parser(
        "demo", help="Run full random-access, motion-learning, and dual-aspect QA demo"
    )
    p_demo.add_argument(
        "--out", type=Path, default=None, help="Optional directory to persist demo artifacts"
    )

    p_video = sub.add_parser(
        "video", help="Plan, render and check video sequences (render/check need the video extra)"
    )
    video = p_video.add_subparsers(dest="video_command", required=True)
    v_plan = video.add_parser("plan", help="Frame plan and pre-render QA for a sequence (pure)")
    v_plan.add_argument("sequence", type=Path, help="VideoSequence JSON")
    v_probe = video.add_parser("probe-tools", help="Print external tool cards (ffmpeg, Chromium)")
    v_render = video.add_parser("render", help="Render a sequence to MP4 per aspect, then check")
    v_render.add_argument("sequence", type=Path, help="VideoSequence JSON")
    v_render.add_argument("--media", type=Path, required=True, help="Media nouns JSON")
    v_render.add_argument("--out", type=Path, required=True, help="Output directory")
    v_render.add_argument("--no-check", action="store_true", help="Skip post-encode QA")
    v_check = video.add_parser("check", help="Post-encode QA of an existing render directory")
    v_check.add_argument("sequence", type=Path, help="VideoSequence JSON")
    v_check.add_argument("--render-dir", type=Path, required=True, help="Directory with manifests")
    v_demo = video.add_parser(
        "demo", help="Render and check the bundled hackathon demo sequence (16:9 and 9:16)"
    )
    v_demo.add_argument("--out", type=Path, required=True, help="Output directory")
    for command in (v_probe, v_render, v_check, v_demo):
        command.add_argument("--ffmpeg", default=None, help="ffmpeg binary (default: auto)")
    for command in (v_probe, v_render, v_demo):
        command.add_argument("--chromium", default=None, help="Chromium binary (default: auto)")
    for command in (v_render, v_demo):
        command.add_argument("--processes", type=int, default=4, help="Rasterizer processes")
    for command in (v_render, v_check):
        command.add_argument("--aspects", default=None, help="Comma-separated subset of outputs")

    return parser


def _dispatch_video(args: argparse.Namespace) -> int:
    aspects = _parse_aspects(args.aspects) if getattr(args, "aspects", None) else None
    if args.video_command == "plan":
        return _cmd_video_plan(args.sequence)
    if args.video_command == "probe-tools":
        return _cmd_video_probe(args.ffmpeg, args.chromium)
    if args.video_command == "render":
        return _cmd_video_render(
            args.sequence,
            args.media,
            args.out,
            aspects,
            args.processes,
            args.ffmpeg,
            args.chromium,
            not args.no_check,
        )
    if args.video_command == "check":
        return _cmd_video_check(args.sequence, args.render_dir, aspects, args.ffmpeg)
    folder = examples_dir() / "sequences"
    return _cmd_video_render(
        folder / "hackathon-demo.json",
        folder / "hackathon-demo.media.json",
        args.out,
        None,
        args.processes,
        args.ffmpeg,
        args.chromium,
        True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "recipes":
            return _cmd_recipes()
        if args.command == "render":
            return _cmd_render(args.recipe, args.out, _parse_aspects(args.aspects))
        if args.command == "qa":
            return _cmd_qa(args.recipe, _parse_aspects(args.aspects))
        if args.command == "learn":
            return _cmd_learn(args.trace, args.out)
        if args.command == "demo":
            return _cmd_demo(args.out)
        if args.command == "video":
            return _dispatch_video(args)
    except VideoMotionError as exc:
        print(json.dumps(exc.to_problem(), indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
