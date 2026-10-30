"""The video and motion seed pack must describe this code exactly.

This code lives in the pack library at packs/video-motion/code, beside the pack's source.json, the
only definition of the pack's nouns and verbs. The pack's tool card points at this folder, and each
noun that states a fact about the code carries a `tool_facts` object. This test recomputes those
facts from the code and the bundled examples and fails on any drift, so the pack and its code
cannot silently disagree.

Inside the library it reads ../source.json. VIDEO_MOTION_PACK_LIBRARY names another library
checkout instead. Without either it skips; VIDEO_MOTION_REQUIRE_PACK=1 turns that into a failure.
It reads local files only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import os
import re
import tomllib
from pathlib import Path
from typing import Any, get_args

import pytest

from video_motion import __version__
from video_motion.cli import build_parser
from video_motion.ffmpeg_graph import LOUDNORM_LRA, SAMPLE_RATE
from video_motion.media import MIME_KIND, GeneratorTool, MediaAsset, MediaKind, MediaProvenance
from video_motion.motion import BEAT_PHASES, CANONICAL_BOUNDARY_RATIOS, EASING_CANDIDATES
from video_motion.nouns import PACK_ID, PROVENANCE, value_sha256
from video_motion.qa import ALL_QA_CHECKS
from video_motion.schemas import (
    ALLOWED_LICENSES,
    ASPECT_PROFILES,
    MotionObservationTrace,
    SceneRecipe,
    StemKind,
)
from video_motion.sequence import (
    MAX_CAPTION_CPS,
    MIN_CAPTION_S,
    SEQUENCE_CHECKS,
    VideoSequence,
    audit_sequence,
    load_bundled_sequence,
    plan_sequence,
)
from video_motion.social import default_asset_catalog, default_motion_profiles
from video_motion.toolcards import REQUIRED_FFMPEG, ExternalToolCard
from video_motion.video_checks import (
    AAC_SLACK_S,
    BLACK_MIN_S,
    CAPTION_COVERAGE_MIN,
    FREEZE_MIN_S,
    LOUDNESS_TOLERANCE_LU,
    SSIM_MIN,
    VIDEO_CHECKS,
    VideoQAReport,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
COMMIT = re.compile(r"^[0-9a-f]{40}$")
# What the pack's render, check, seek, fit and compile verbs call. Each must resolve to a callable.
ENTRYPOINTS = {
    "seek_frame": "video_motion.timeline:evaluate_frame",
    "render_svg_frame": "video_motion.timeline:render_svg_frame",
    "fit_motion": "video_motion.motion:learn_motion_profile",
    "retarget_motion": "video_motion.motion:retarget_motion",
    "scene_qa": "video_motion.qa:audit_recipe",
    "compile_social_formats": "video_motion.social:compile_deliverable",
    "plan_sequence": "video_motion.sequence:plan_sequence",
    "prerender_qa": "video_motion.sequence:audit_sequence",
    "render_sequence": "video_motion.video_worker:render_sequence",
    "check_video": "video_motion.video_worker:check_rendered_video",
}
RECIPES = {
    "recipe.pov-role-skit": "01-pov-role-skit.json",
    "recipe.kinetic-data-chart": "02-kinetic-data-chart.json",
    "recipe.algorithm-race": "03-algorithm-race-explainer.json",
}


def _file(path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _commands(parser: argparse.ArgumentParser, prefix: str = "") -> list[str]:
    found: list[str] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                nested = _commands(sub, f"{prefix}{name} ")
                found += nested or [f"{prefix}{name}"]
    return found


def _fields(model: Any) -> dict[str, list[str]]:
    fields = model.model_fields
    return {
        "fields": sorted(fields),
        "required": sorted(name for name, info in fields.items() if info.is_required()),
    }


def tool_facts() -> dict[str, dict[str, Any]]:
    """Every fact the pack states about these tools, recomputed from code and bundled files."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = config["project"]
    facts: dict[str, dict[str, Any]] = {}
    facts["tool.video-motion-tools"] = {
        "repository": PROVENANCE["repository"],
        "path": PROVENANCE["path"],
        "python_package": PROVENANCE["python_package"],
        "package_version": __version__,
        "requires_python": project["requires-python"],
        "command": next(iter(project["scripts"])),
        "commands": sorted(_commands(build_parser())),
        "entrypoints": dict(ENTRYPOINTS),
        "optional_extra": {"video": sorted(project["optional-dependencies"]["video"])},
        "required_ffmpeg_components": list(REQUIRED_FFMPEG),
    }
    facts["catalog.assets"] = {
        "assets": [
            entry.model_dump(mode="json") for entry in default_asset_catalog().list_entries()
        ],
        "allowed_licenses": sorted(ALLOWED_LICENSES),
    }
    facts["catalog.motion-formulas"] = {
        "beat_phases": list(BEAT_PHASES),
        "canonical_boundary_ratios": list(CANONICAL_BOUNDARY_RATIOS),
        "easings": list(EASING_CANDIDATES),
        "profiles": [profile.model_dump(mode="json") for profile in default_motion_profiles()],
    }
    facts["rules.aspects"] = {
        "aspects": {
            aid: profile.model_dump(mode="json") for aid, profile in ASPECT_PROFILES.items()
        }
    }
    facts["rules.captions"] = {
        "max_chars_per_second": MAX_CAPTION_CPS,
        "min_display_s": MIN_CAPTION_S,
        "min_font_px": {aid: profile.min_font_px for aid, profile in ASPECT_PROFILES.items()},
        "prerender_checks": list(SEQUENCE_CHECKS),
        "sidecars": ["srt", "webvtt"],
    }
    sequence_fields = VideoSequence.model_fields
    facts["rules.audio"] = {
        "default_loudness_target_lufs": sequence_fields["loudness_target_lufs"].default,
        "default_music_duck_db": sequence_fields["music_duck_db"].default,
        "default_true_peak_limit_dbtp": sequence_fields["true_peak_limit_dbtp"].default,
        "loudness_tolerance_lu": LOUDNESS_TOLERANCE_LU,
        "loudnorm_lra": LOUDNORM_LRA,
        "sample_rate_hz": SAMPLE_RATE,
        "stem_kinds": list(get_args(StemKind)),
    }
    facts["checks.scene"] = {"checks": list(ALL_QA_CHECKS)}
    spot_count = (
        inspect.signature(importlib.import_module("video_motion.video_worker").check_rendered_video)
        .parameters["spot_count"]
        .default
    )
    facts["checks.video"] = {
        "aac_slack_s": AAC_SLACK_S,
        "black_min_s": BLACK_MIN_S,
        "caption_coverage_min": CAPTION_COVERAGE_MIN,
        "checks": list(VIDEO_CHECKS),
        "freeze_min_s": FREEZE_MIN_S,
        "loudness_tolerance_lu": LOUDNESS_TOLERANCE_LU,
        "spot_frames": spot_count,
        "ssim_min": SSIM_MIN,
    }
    for slug, name in RECIPES.items():
        recipe = SceneRecipe.model_validate(json.loads((EXAMPLES / name).read_text("utf-8")))
        facts[slug] = {
            "file": _file(EXAMPLES / name),
            "recipe_id": recipe.recipe_id,
            "title": recipe.title,
            "fps": recipe.fps,
            "duration_s": recipe.duration_s,
            "total_frames": recipe.total_frames,
            "stage_aspect": recipe.stage_aspect,
            "actors": len(recipe.actors),
            "captions": len(recipe.captions),
            "attributions": len(recipe.attributions),
        }
    sequence, assets = load_bundled_sequence("hackathon-demo")
    plan = plan_sequence(sequence)
    facts["sequence.demo"] = {
        "file": _file(EXAMPLES / "sequences" / "hackathon-demo.json"),
        "media_file": _file(EXAMPLES / "sequences" / "hackathon-demo.media.json"),
        "sequence_id": sequence.sequence_id,
        "title": sequence.title,
        "fps": sequence.fps,
        "outputs": list(sequence.outputs),
        "total_frames": plan.total_frames,
        "duration_s": plan.duration_s,
        "plan_sha256": value_sha256(plan.model_dump(mode="json")),
        "prerender_qa": {
            aspect: audit_sequence(sequence, aspect).receipt_sha256 for aspect in sequence.outputs
        },
        "media": [
            {
                "media_id": asset.media_id,
                "media_kind": asset.kind,
                "blob_sha256": asset.blob_sha256,
                "generator": asset.generator.tool if asset.generator else None,
            }
            for asset in sorted(assets, key=lambda item: item.media_id)
        ],
    }
    trace_path = EXAMPLES / "sample-motion-trace.json"
    trace = MotionObservationTrace.model_validate(json.loads(trace_path.read_text("utf-8")))
    facts["trace.sample-motion"] = {
        "file": _file(trace_path),
        "trace_id": trace.trace_id,
        "fps": trace.fps,
        "duration_s": trace.duration_s,
        "samples": len(trace.samples),
    }
    tools_path = EXAMPLES / "sequences" / "reference-tools.json"
    cards = [
        ExternalToolCard.model_validate(card)
        for card in json.loads(tools_path.read_text("utf-8"))["cards"]
    ]
    facts["tools.reference-builds"] = {
        "file": _file(tools_path),
        "cards": [
            {
                "name": card.name,
                "version": card.version,
                "spdx": card.license_spdx,
                "binary_sha256": card.sha256,
            }
            for card in cards
        ],
    }
    facts["template.media"] = {
        **_fields(MediaAsset),
        "media_kinds": list(get_args(MediaKind)),
        "mime_types": sorted(MIME_KIND),
        "provenance": list(get_args(MediaProvenance)),
        "generators": list(get_args(GeneratorTool)),
        "renderer_licenses": sorted(ALLOWED_LICENSES),
    }
    facts["template.scene-recipe"] = _fields(SceneRecipe)
    facts["template.sequence"] = _fields(VideoSequence)
    manifest = importlib.import_module("video_motion.video_worker").RenderManifest
    facts["template.render-manifest"] = {
        "format": manifest.model_fields["format"].default,
        **_fields(manifest),
    }
    facts["template.video-qa-report"] = {
        "format": VideoQAReport.model_fields["format"].default,
        **_fields(VideoQAReport),
        "checks": list(VIDEO_CHECKS),
    }
    return json.loads(json.dumps(facts))


def _library_pack() -> dict[str, Any]:
    location = os.environ.get("VIDEO_MOTION_PACK_LIBRARY")
    source = (
        Path(location) / "packs" / PACK_ID / "source.json"
        if location
        else ROOT.parent / "source.json"
    )
    if not source.is_file():
        if os.environ.get("VIDEO_MOTION_REQUIRE_PACK") == "1":
            pytest.fail(f"VIDEO_MOTION_REQUIRE_PACK=1, but there is no pack source at {source}")
        pytest.skip("Run inside the pack library, or set VIDEO_MOTION_PACK_LIBRARY to a checkout")
    loaded = json.loads(source.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_entrypoints_and_commands_resolve() -> None:
    for name, target in ENTRYPOINTS.items():
        module, _, attribute = target.partition(":")
        assert callable(getattr(importlib.import_module(module), attribute)), name
    commands = tool_facts()["tool.video-motion-tools"]["commands"]
    assert {"video render", "video check", "qa", "learn", "render"} <= set(commands)


def test_library_pack_states_exactly_these_tool_facts() -> None:
    pack = _library_pack()
    assert pack["pack_id"] == PACK_ID
    nouns = {noun["slug"]: noun for noun in pack["nouns"]}
    pin = nouns["tool.video-motion-tools"]["value"]["pin"]
    assert pin["repository"] == PROVENANCE["repository"] and pin["path"] == PROVENANCE["path"]
    assert pin["code"] == {"$code": PACK_ID}, "the tool card pins this code by its digest"
    assert pin["commit"] is None or COMMIT.fullmatch(pin["commit"]), pin
    facts = tool_facts()
    for slug, expected in facts.items():
        assert slug in nouns, f"the pack has no {slug} noun"
        assert nouns[slug]["value"].get("tool_facts") == expected, f"{slug} differs from the tools"
    stating = {slug for slug, noun in nouns.items() if "tool_facts" in noun["value"]}
    assert stating == set(facts), stating ^ set(facts)
