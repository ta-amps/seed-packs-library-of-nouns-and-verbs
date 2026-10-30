"""Tests for motion profile extraction, least-squares easing fitting, and beat retargeting."""

from __future__ import annotations

import pytest

from video_motion.errors import MotionTraceError
from video_motion.motion import fit_easing_primitive, learn_motion_profile, retarget_motion
from video_motion.qa import audit_recipe
from video_motion.schemas import (
    AssetAttribution,
    CastMember,
    EasingKind,
    MotionObservationTrace,
    ObservationSample,
    canonical_sha256,
)
from video_motion.social import load_sample_motion_trace
from video_motion.timeline import evaluate_easing


@pytest.mark.parametrize(
    "expected_easing",
    ["linear", "ease_out_cubic", "ease_in_out_cubic", "spring_pop", "step_hold"],
)
def test_fit_easing_primitive_recovers_exact_curve(expected_easing: EasingKind) -> None:
    u_grid = [i / 20.0 for i in range(21)]
    y_grid = [evaluate_easing(expected_easing, u) for u in u_grid]
    fitted, rmse = fit_easing_primitive(u_grid, y_grid)
    assert fitted == expected_easing
    assert rmse < 1e-6


def test_learn_motion_profile_fits_easing_and_beat_cadence() -> None:
    trace = load_sample_motion_trace()
    profile = learn_motion_profile(trace)

    assert len(profile.beat_proportions) == 6
    assert [bp.phase for bp in profile.beat_proportions] == [
        "hook",
        "orientation",
        "setup",
        "escalation",
        "punchline",
        "hold",
    ]
    assert profile.beat_proportions[0].start_ratio == 0.0
    assert profile.beat_proportions[-1].end_ratio == 1.0
    assert profile.median_cut_cadence_s > 0.0
    assert 0.0 < profile.mean_motion_intensity <= 1.0
    assert profile.beat_proportions[-1].dominant_easing == "step_hold"

    # Re-learning on identical input produces identical SHA-256 profile receipt
    second = learn_motion_profile(trace)
    assert second.profile_sha256 == profile.profile_sha256

    short_trace = MotionObservationTrace(
        trace_id="too-short",
        title="Short",
        duration_s=2.0,
        samples=[ObservationSample(t_s=0.0, frame_diff_energy=0.5)],
    )
    with pytest.raises(MotionTraceError):
        learn_motion_profile(short_trace)


def test_retarget_motion_preserves_frame_addressable_beat_proportions() -> None:
    profile = learn_motion_profile(load_sample_motion_trace())
    cast = [
        CastMember(
            actor_id="presenter",
            kind="character",
            label="Presenter",
            asset_id="proc-presenter",
            attribution=AssetAttribution(
                asset_id="proc-presenter",
                license="PROCEDURAL",
                creator="video-motion vector studio",
                source_uri="urn:video-motion:test:presenter",
                sha256=canonical_sha256({"id": "proc-presenter"}),
            ),
            role_label="HOST",
            line_text="Beat proportions remain locked across target durations.",
        ),
        CastMember(
            actor_id="cohost",
            kind="character",
            label="Co-Host",
            asset_id="cc0-cohost",
            attribution=AssetAttribution(
                asset_id="cc0-cohost",
                license="CC0",
                creator="video-motion open rig pack",
                source_uri="urn:video-motion:test:cohost",
                sha256=canonical_sha256({"id": "cc0-cohost"}),
            ),
            role_label="GUEST",
            line_text="Every actor stays inside dual-aspect safe zones.",
        ),
    ]

    for duration_s in (10.0, 24.0):
        recipe = retarget_motion(profile, cast, duration_s=duration_s, fps=30)
        assert recipe.total_frames == round(duration_s * 30)
        for beat, expected in zip(recipe.beats, profile.beat_proportions, strict=True):
            actual_end_ratio = beat.end_s / recipe.duration_s
            assert abs(actual_end_ratio - expected.end_ratio) <= (1.0 / recipe.total_frames) + 1e-6

        qa_report = audit_recipe(recipe, aspects=("reels_9x16", "feed_4x5"))
        assert qa_report.passed, qa_report.findings
