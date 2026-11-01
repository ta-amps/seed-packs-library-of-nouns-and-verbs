"""Standard-library alignment of segmentation masks, speech word timings, and layout safe zones."""

from .aligner import (
    DEFAULT_SAFE_ZONES,
    align_multimodal_timeline,
    box_intersection_area,
    box_iou,
    group_words_into_utterances,
    mask_intrusion_ratio,
    polygon_to_bbox_and_area,
)

__all__ = [
    "DEFAULT_SAFE_ZONES",
    "align_multimodal_timeline",
    "box_intersection_area",
    "box_iou",
    "group_words_into_utterances",
    "mask_intrusion_ratio",
    "polygon_to_bbox_and_area",
]
