"""Accessible publication-grade SVG compiler for forest plots, progression bars, and message traces."""

from .compiler import (
    DEFAULT_PALETTE,
    audit_svg_document,
    compile_diagram,
    contrast_ratio,
    detect_label_collisions,
)

__all__ = [
    "DEFAULT_PALETTE",
    "audit_svg_document",
    "compile_diagram",
    "contrast_ratio",
    "detect_label_collisions",
]
