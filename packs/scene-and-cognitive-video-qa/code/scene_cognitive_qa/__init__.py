"""Deterministic multi-frame scene, transition, slide stability and cognitive-load QA."""

from .evaluators import (
    compile_scene_cognitive_report,
    evaluate_camera_and_slide_stability,
    evaluate_frosted_caption_geometry,
    evaluate_live_web_journey_provenance,
    evaluate_reading_speed_and_cognitive_load,
    evaluate_shot_dwell_and_transitions,
    wrap_caption_clauses,
)

__all__ = [
    "compile_scene_cognitive_report",
    "evaluate_camera_and_slide_stability",
    "evaluate_frosted_caption_geometry",
    "evaluate_live_web_journey_provenance",
    "evaluate_reading_speed_and_cognitive_load",
    "evaluate_shot_dwell_and_transitions",
    "wrap_caption_clauses",
]
