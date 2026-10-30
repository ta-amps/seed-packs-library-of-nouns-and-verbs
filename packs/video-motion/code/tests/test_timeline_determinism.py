"""Tests proving pure frame-addressable evaluation and order-invariant SVG rendering."""

from __future__ import annotations

import hashlib

import pytest

from video_motion.errors import FrameOutOfRangeError
from video_motion.schemas import AspectId
from video_motion.social import load_bundled_recipes
from video_motion.timeline import (
    evaluate_easing,
    evaluate_frame,
    render_contact_sheet_svg,
    render_svg_frame,
    seeded_unit,
)


@pytest.mark.parametrize("aspect", ["reels_9x16", "feed_4x5"])
def test_forward_backward_and_shuffled_frame_evaluation_identical(aspect: AspectId) -> None:
    recipes = load_bundled_recipes()
    assert len(recipes) == 3

    for recipe in recipes:
        indices = list(range(recipe.total_frames))

        forward_states = {
            idx: evaluate_frame(recipe, idx, aspect=aspect).model_dump_json() for idx in indices
        }
        backward_states = {
            idx: evaluate_frame(recipe, idx, aspect=aspect).model_dump_json()
            for idx in reversed(indices)
        }
        shuffled = sorted(
            indices,
            key=lambda idx: hashlib.sha256(f"{recipe.seed + 17}:{idx}".encode()).hexdigest(),
        )
        shuffled_states = {
            idx: evaluate_frame(recipe, idx, aspect=aspect).model_dump_json() for idx in shuffled
        }

        assert forward_states == backward_states
        assert forward_states == shuffled_states

        # Also verify byte-for-byte identical SVG rendering across arbitrary access order
        sample_check = [
            0,
            recipe.total_frames // 3,
            (2 * recipe.total_frames) // 3,
            recipe.total_frames - 1,
        ]
        svg_pass_one = [
            render_svg_frame(evaluate_frame(recipe, f_idx, aspect=aspect), show_safe_zones=True)
            for f_idx in sample_check
        ]
        svg_pass_two = [
            render_svg_frame(evaluate_frame(recipe, f_idx, aspect=aspect), show_safe_zones=True)
            for f_idx in reversed(sample_check)
        ]
        assert svg_pass_one == list(reversed(svg_pass_two))


def test_easing_primitives_and_out_of_range_guard() -> None:
    for kind in ("linear", "ease_out_cubic", "ease_in_out_cubic", "spring_pop", "step_hold"):
        assert evaluate_easing(kind, 0.0) == 0.0
        assert evaluate_easing(kind, 1.0) == 1.0

    # spring_pop overshoots 1.0 mid-trajectory before settling cleanly at 1.0
    assert evaluate_easing("spring_pop", 0.45) > 1.0
    assert evaluate_easing("step_hold", 0.99) == 0.0

    # Pure O(1) seeded_unit has zero call-history drift
    first = seeded_unit(42, "sparkle", 120)
    _ = seeded_unit(99, "other", 5)
    second = seeded_unit(42, "sparkle", 120)
    assert first == second
    assert 0.0 <= first < 1.0

    recipe = load_bundled_recipes()[0]
    sheet = render_contact_sheet_svg(recipe, sample_count=6, aspect="reels_9x16")
    assert sheet.startswith("<svg ")
    assert "sha256:" in sheet

    with pytest.raises(FrameOutOfRangeError):
        evaluate_frame(recipe, -1)
    with pytest.raises(FrameOutOfRangeError):
        evaluate_frame(recipe, recipe.total_frames)
