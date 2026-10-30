"""16:9 output, stage-aware remapping, per-aspect overrides and unchanged legacy frames."""

from __future__ import annotations

import hashlib
from pathlib import Path

from video_motion.captions import export_webvtt
from video_motion.qa import audit_recipe
from video_motion.schemas import ASPECT_PROFILES, AspectOverride, SceneRecipe
from video_motion.social import compile_deliverable, load_bundled_recipes
from video_motion.timeline import evaluate_frame, stage_mapping

ROOT = Path(__file__).resolve().parents[1]

# Every-frame hash digests of recipes 01 and 03 in the two social aspects. Recipe 03's were
# recorded before 16:9 support was added and prove the 9:16 and 4:5 evaluation stayed
# byte-identical. Recipe 01's were re-recorded on October 29, 2026, when the wording of its third
# caption (frames 63 to 173) dropped an old product name; every other frame kept its earlier hash.
LEGACY_TIMELINES = {
    (
        "01-pov-role-skit",
        "reels_9x16",
    ): "b3aa9774dba13fd88623c30587ad6fa3522d0ab591c1c9c543f1a83b8d081020",
    (
        "01-pov-role-skit",
        "feed_4x5",
    ): "0d524951095e90ac4e0434aaabd33f631216d56859dfd9da95607b438e468f62",
    (
        "03-algorithm-race-explainer",
        "reels_9x16",
    ): "5d08aa621ba7e40202b1f30935ea84830ea6b518f929d946d482ca0fe20330e9",
    (
        "03-algorithm-race-explainer",
        "feed_4x5",
    ): "1e7461677c92b4076eab779a403d5bd0ba98dcf7ed448a5c053ddc5248f233c0",
}


def _staged_recipe() -> SceneRecipe:
    """A small 16:9-staged recipe whose connector is hidden on 4:5 and turned upright on 9:16."""
    return SceneRecipe.model_validate(
        {
            "recipe_id": "staged-16x9",
            "title": "Staged in 16:9",
            "fps": 30,
            "duration_s": 2.0,
            "stage_aspect": "landscape_16x9",
            "background_hex": "#1b2744",
            "beats": [
                {"phase": "hook", "start_s": 0.0, "end_s": 1.0},
                {"phase": "hold", "start_s": 1.0, "end_s": 2.0},
            ],
            "actors": [
                {
                    "actor_id": "lane",
                    "kind": "mechanism",
                    "asset_id": "lane",
                    "width": 300.0,
                    "height": 80.0,
                    "tracks": [
                        {"property": "x", "keyframes": [{"t_s": 0.0, "value": 960.0}]},
                        {"property": "y", "keyframes": [{"t_s": 0.0, "value": 540.0}]},
                        {
                            "property": "draw_progress",
                            "keyframes": [
                                {"t_s": 0.0, "value": 0.0},
                                {"t_s": 1.0, "value": 1.0, "easing": "step_hold"},
                            ],
                        },
                    ],
                    "aspect_overrides": {
                        "reels_9x16": {"rotation_offset_deg": 90.0, "scale_mul": 2.0},
                        "feed_4x5": {"opacity_mul": 0.0},
                    },
                }
            ],
            "attributions": [
                {
                    "asset_id": "lane",
                    "license": "MIT",
                    "creator": "Test",
                    "sha256": "2" * 64,
                    "digest_basis": "illustrative",
                }
            ],
        }
    )


def _timeline_digest(recipe: SceneRecipe, aspect: str) -> str:
    digest = hashlib.sha256()
    for index in range(recipe.total_frames):
        digest.update(evaluate_frame(recipe, index, aspect=aspect).frame_hash_sha256.encode())  # type: ignore[arg-type]
    return digest.hexdigest()


def test_legacy_aspects_are_byte_identical_to_before_16x9() -> None:
    recipes = {recipe.recipe_id: recipe for recipe in load_bundled_recipes()}
    for (recipe_id, aspect), expected in LEGACY_TIMELINES.items():
        assert _timeline_digest(recipes[recipe_id], aspect) == expected


def test_landscape_profile_safe_zones_and_bundled_recipes_pass() -> None:
    profile = ASPECT_PROFILES["landscape_16x9"]
    assert (profile.width, profile.height) == (1920, 1080)
    safe = profile.safe_canvas
    assert safe.inside_viewport(1920, 1080)
    assert all(not safe.intersects(keep_out) for keep_out in profile.ui_keep_outs)
    for recipe in load_bundled_recipes():
        report = audit_recipe(recipe, aspects=("landscape_16x9",))
        assert report.passed, report.findings
        deliverable = compile_deliverable(recipe, aspects=("landscape_16x9", "reels_9x16"))
        assert deliverable.aspects["landscape_16x9"].width == 1920
        for index in (0, recipe.total_frames // 2, recipe.total_frames - 1):
            state = evaluate_frame(recipe, index, aspect="landscape_16x9")
            for caption in state.captions:
                assert caption.box.x >= safe.x and caption.box.right <= safe.right
                assert caption.box.bottom <= safe.bottom
    vtt = export_webvtt(load_bundled_recipes()[0], aspect="landscape_16x9")
    assert "line:82% position:50% align:center" in vtt


def test_stage_mapping_round_trips_and_keeps_legacy_rule() -> None:
    assert stage_mapping(470.0, 760.0, "reels_9x16", "reels_9x16") == (470.0, 760.0, 1.0)
    x, _y, factor = stage_mapping(470.0, 760.0, "reels_9x16", "feed_4x5")
    assert (x, factor) == (470.0, 1.0)
    for stage, target in (("landscape_16x9", "reels_9x16"), ("reels_9x16", "landscape_16x9")):
        src = ASPECT_PROFILES[stage].safe_canvas
        dst = ASPECT_PROFILES[target].safe_canvas
        mx, my, factor = stage_mapping(src.x, src.y, stage, target)
        assert (round(mx, 6), round(my, 6)) == (dst.x, dst.y)
        assert factor == min(dst.width / src.width, dst.height / src.height)


def test_per_aspect_overrides_hide_and_rotate_only_where_set() -> None:
    recipe = _staged_recipe()
    lane = {
        aspect: evaluate_frame(recipe, 45, aspect).actors[0]  # type: ignore[arg-type]
        for aspect in ("landscape_16x9", "reels_9x16", "feed_4x5")
    }
    assert (lane["landscape_16x9"].x, lane["landscape_16x9"].y) == (960.0, 540.0)
    assert lane["landscape_16x9"].rotation_deg == 0.0 and lane["reels_9x16"].rotation_deg == 90.0
    assert lane["feed_4x5"].opacity == 0.0 and lane["reels_9x16"].opacity == 1.0
    for aspect in ("landscape_16x9", "reels_9x16", "feed_4x5"):
        assert audit_recipe(recipe, aspects=(aspect,)).passed  # type: ignore[arg-type]
    base = load_bundled_recipes()[0]
    actor = base.actors[0]
    hidden = actor.model_copy(
        update={"aspect_overrides": {"feed_4x5": AspectOverride(opacity_mul=0.0)}}
    )
    edited = base.model_copy(update={"actors": [hidden, *base.actors[1:]]})
    feed = next(
        a for a in evaluate_frame(edited, 30, "feed_4x5").actors if a.actor_id == actor.actor_id
    )
    reels = next(
        a for a in evaluate_frame(edited, 30, "reels_9x16").actors if a.actor_id == actor.actor_id
    )
    assert feed.opacity == 0.0 and reels.opacity > 0.0
