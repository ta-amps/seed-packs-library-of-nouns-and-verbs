"""Tests for the 8-check deterministic every-frame QA gate, dual-aspect compiler, and SceneFactory."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_motion.errors import (
    ContributorTierRefusedError,
    QAGateFailureError,
    UnlicensedAssetError,
)
from video_motion.qa import audit_recipe
from video_motion.schemas import (
    AudioCue,
    Box2D,
    CaptionCue,
    MotionTrack,
    SceneActor,
    TrackKeyframe,
)
from video_motion.social import (
    AssetCatalog,
    CatalogAssetRecord,
    ConceptBrief,
    ConceptRoleSpec,
    SceneFactory,
    compile_deliverable,
    default_asset_catalog,
    load_bundled_recipes,
    write_deliverable_bundle,
)


def test_bundled_recipes_compile_dual_aspect_and_export_captions(tmp_path: Path) -> None:
    for recipe in load_bundled_recipes():
        deliverable = compile_deliverable(recipe, aspects=("reels_9x16", "feed_4x5"))
        assert deliverable.qa_report.passed
        assert deliverable.qa_report.score == 100.0
        assert set(deliverable.aspects.keys()) == {"reels_9x16", "feed_4x5"}
        assert deliverable.aspects["reels_9x16"].height == 1920
        assert deliverable.aspects["feed_4x5"].height == 1350
        assert "-->" in deliverable.srt
        assert deliverable.webvtt.startswith("WEBVTT")

        out_dir = tmp_path / recipe.recipe_id
        written = write_deliverable_bundle(deliverable, out_dir)
        assert (out_dir / "post.json").is_file()
        assert (out_dir / "captions.srt").is_file()
        assert (out_dir / "captions.vtt").is_file()
        assert (out_dir / "reels_9x16" / "contact_sheet.svg").is_file()
        assert (out_dir / "feed_4x5" / "contact_sheet.svg").is_file()
        assert len(written) == 8


def test_every_frame_qa_catches_all_eight_violation_classes() -> None:
    base = load_bundled_recipes()[0]

    # 1. Platform UI keep-out: reclaimed_lower_right is legal on 4:5 Feed, but collides with Reels right-rail buttons on raw 9:16
    reclaimed_cue = base.captions[1].model_copy(update={"anchor": "reclaimed_lower_right"})
    reclaimed_recipe = base.model_copy(
        update={"captions": [base.captions[0], reclaimed_cue, *base.captions[2:]]}
    )
    report_feed = audit_recipe(reclaimed_recipe, aspects=("feed_4x5",))
    assert report_feed.passed
    report_reels = audit_recipe(reclaimed_recipe, aspects=("reels_9x16",))
    assert not report_reels.passed
    assert any(f.check == "platform_ui_keep_out" for f in report_reels.findings)
    # Dual-aspect compiler automatically adapts reclaimed_lower_right onto safe lower_third for 9:16
    adapted_bundle = compile_deliverable(reclaimed_recipe, aspects=("reels_9x16", "feed_4x5"))
    assert adapted_bundle.qa_report.passed

    # 2. Minimum font size (< 38px) and orphan line break
    tiny_cue = base.captions[0].model_copy(
        update={"font_px": 28.0, "text": "Deterministic frame indexing prevents drift\nok"}
    )
    bad_font_recipe = base.model_copy(update={"captions": [tiny_cue, *base.captions[1:]]})
    rep_font = audit_recipe(bad_font_recipe, aspects=("reels_9x16",))
    assert any(f.check == "min_font_and_line_balance" for f in rep_font.findings)

    # 3. Subject/face keep-out occlusion
    face_box = Box2D(x=210.0, y=430.0, width=320.0, height=110.0, label="over-face")
    occluding_cue = base.captions[1].model_copy(update={"box_override": {"reels_9x16": face_box}})
    bad_occ_recipe = base.model_copy(
        update={"captions": [base.captions[0], occluding_cue, *base.captions[2:]]}
    )
    rep_occ = audit_recipe(bad_occ_recipe, aspects=("reels_9x16",))
    assert any(f.check == "subject_keep_out_occlusion" for f in rep_occ.findings)

    # 4. Inter-frame caption flicker (1-frame blink gap + 2-frame flash cue)
    flicker_a = CaptionCue(
        cue_id="flk-1",
        text="First caption block holds steady.",
        start_s=0.0,
        end_s=1.0,
        font_px=42.0,
    )
    flicker_b = CaptionCue(
        cue_id="flk-2",
        text="Blinks back after 1 frame.",
        start_s=1.034,
        end_s=1.09,
        font_px=42.0,
    )
    rep_flicker = audit_recipe(
        base.model_copy(update={"captions": [flicker_a, flicker_b]}), aspects=("reels_9x16",)
    )
    assert any(f.check == "caption_flicker_jitter" for f in rep_flicker.findings)

    # 5. Black/empty and unintended frozen frame runs
    invisible_actor = SceneActor(
        actor_id="ghost",
        kind="card",
        label="Ghost",
        asset_id="char-sre-lead",
        tracks=[MotionTrack(property="opacity", keyframes=[TrackKeyframe(t_s=0.0, value=0.0)])],
    )
    dark_recipe = base.model_copy(
        update={"background_hex": "#000000", "actors": [invisible_actor], "captions": []}
    )
    rep_dark = audit_recipe(dark_recipe, aspects=("reels_9x16",))
    assert any(f.check == "black_or_frozen_frames" for f in rep_dark.findings)

    # 6. Luminance flash rate (> 3 flashes/sec photosensitivity guard)
    strobe_kfs = [
        TrackKeyframe(t_s=round(i * 0.08, 3), value=float(i % 2), easing="step_hold")
        for i in range(12)
    ]
    strobe_actor = SceneActor(
        actor_id="strobe",
        kind="background",
        label="Strobe",
        asset_id="char-sre-lead",
        width=1080.0,
        height=1920.0,
        fill_hex="#ffffff",
        accent_hex="#ffffff",
        tracks=[
            MotionTrack(property="x", keyframes=[TrackKeyframe(t_s=0.0, value=540.0)]),
            MotionTrack(property="y", keyframes=[TrackKeyframe(t_s=0.0, value=960.0)]),
            MotionTrack(property="opacity", keyframes=strobe_kfs),
        ],
    )
    rep_flash = audit_recipe(
        base.model_copy(update={"actors": [strobe_actor, *base.actors]}), aspects=("reels_9x16",)
    )
    assert any(f.check == "luminance_flash_rate" for f in rep_flash.findings)

    # 7. Audio peak clipping (> -1.0 dBFS) and caption timing overlap
    hot_audio = AudioCue(
        cue_id="clip-hit",
        stem_kind="sfx_hit",
        asset_id="stem-vo-skit",
        start_s=0.5,
        duration_s=0.5,
        peak_dbfs=-0.2,
    )
    overlap_cue = base.captions[2].model_copy(
        update={"cue_id": "overlap-cue", "start_s": 2.4, "end_s": 3.5}
    )
    bad_audio_recipe = base.model_copy(
        update={
            "audio_cues": [*base.audio_cues, hot_audio],
            "captions": [*base.captions, overlap_cue],
        }
    )
    rep_audio = audit_recipe(bad_audio_recipe, aspects=("reels_9x16",))
    assert any(f.check == "audio_peak_and_caption_overlap" for f in rep_audio.findings)

    # 8. Missing source-rights AssetAttribution
    unattributed = base.model_copy(update={"attributions": base.attributions[1:]})
    rep_attr = audit_recipe(unattributed, aspects=("reels_9x16",))
    assert any(f.check == "asset_attribution_completeness" for f in rep_attr.findings)

    with pytest.raises(QAGateFailureError):
        compile_deliverable(unattributed, require_qa_pass=True)


def test_scene_factory_license_gate_and_contributor_tier_refusal() -> None:
    catalog = default_asset_catalog()
    catalog.register(
        CatalogAssetRecord(
            asset_id="scraped-unknown-clip",
            kind="character",
            label="Unverified Clip",
            license="UNKNOWN_RIGHTS",
            creator="Unknown",
            sha256="9" * 64,
        )
    )
    factory = SceneFactory(catalog=catalog)

    bad_brief = ConceptBrief(
        brief_id="bad-rights",
        title="Unlicensed Draft",
        roles=[
            ConceptRoleSpec(
                actor_id="rogue",
                asset_id="scraped-unknown-clip",
                spoken_line="Should never pass casting.",
            )
        ],
    )
    with pytest.raises(UnlicensedAssetError):
        factory.cast_and_rank(bad_brief)

    good_brief = ConceptBrief(
        brief_id="clean-skit",
        title="Verified Open-Rights Draft",
        duration_s=12.0,
        roles=[
            ConceptRoleSpec(
                actor_id="eng",
                asset_id="char-sre-lead",
                role_label="SRE",
                spoken_line="Pure frame evaluation eliminates timing drift.",
            )
        ],
    )
    with pytest.raises(ContributorTierRefusedError):
        factory.cast_and_rank(good_brief, model_id="muse-spark-contributor")

    class _ContributorAdapter:
        model_id = "llama-4-maverick-contributor"

        def refine_lines(self, brief: ConceptBrief) -> list[str]:
            return [r.spoken_line for r in brief.roles]

    with pytest.raises(ContributorTierRefusedError):
        SceneFactory(
            catalog=AssetCatalog(catalog.list_entries()), adapter=_ContributorAdapter()
        ).cast_and_rank(good_brief)

    winner, ranked = factory.cast_and_rank(good_brief, model_id="muse-spark")
    assert len(ranked) == 4
    assert ranked[0][1].passed
    assert ranked[0][1].score > ranked[-1][1].score
    assert winner.recipe_id == ranked[0][0].recipe_id
