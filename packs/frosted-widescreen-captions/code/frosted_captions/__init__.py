"""Frosted widescreen captions: v6 line breaking, cue timing checks, pill geometry and an SVG band renderer."""
from .ast_gate import ZeroHardcodedValuesAstGate
from .cues import Cue, check, visible_spans
from .geometry import CENTER, pill_box
from .render import band_svg
from .wrap import split_cues, wrap_balanced

__all__ = [
    "Cue",
    "ZeroHardcodedValuesAstGate",
    "check",
    "visible_spans",
    "CENTER",
    "pill_box",
    "band_svg",
    "split_cues",
    "wrap_balanced",
]
