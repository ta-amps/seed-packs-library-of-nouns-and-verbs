"""Typed errors mapped deterministically to RFC 9457 problem+json HTTP responses."""

from __future__ import annotations


class VideoMotionError(Exception):
    """Base error carrying one HTTP status code and one machine-readable error code."""

    def __init__(self, status_code: int, code: str, title: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.title = title
        self.detail = detail

    def to_problem(self) -> dict[str, object]:
        return {
            "type": "about:blank",
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
            "code": self.code,
        }


class InvalidRecipeError(VideoMotionError):
    """Raised when a scene recipe violates frame, timing, or schema invariants."""

    def __init__(self, detail: str) -> None:
        super().__init__(422, "invalid_recipe", "Invalid Scene Recipe", detail)


class FrameOutOfRangeError(VideoMotionError):
    """Raised when a requested frame index falls outside [0, total_frames - 1]."""

    def __init__(self, frame_index: int, total_frames: int) -> None:
        super().__init__(
            422,
            "frame_out_of_range",
            "Frame Index Out of Range",
            f"Frame index {frame_index} is outside valid range [0, {total_frames - 1}].",
        )


class UnlicensedAssetError(VideoMotionError):
    """Raised when an asset lacks allowlisted open licensing or creator attribution."""

    def __init__(self, asset_id: str, reason: str) -> None:
        super().__init__(
            403,
            "unlicensed_asset",
            "Unlicensed or Unattributed Asset Refused",
            f"Asset {asset_id!r} cannot be cast: {reason}",
        )


class ContributorTierRefusedError(VideoMotionError):
    """Raised when an external concept adapter or QA call targets a '-contributor' model."""

    def __init__(self, model_id: str) -> None:
        super().__init__(
            403,
            "contributor_tier_refused",
            "Contributor-Tier Model Refused",
            f"These tools run in Standard mode only and refuse contributor-tier model {model_id!r}.",
        )


class QAGateFailureError(VideoMotionError):
    """Raised when compile_deliverable enforces QA and one or more error findings fire."""

    def __init__(self, recipe_id: str, error_count: int, receipt_sha256: str) -> None:
        super().__init__(
            422,
            "qa_gate_failed",
            "Deterministic Every-Frame QA Gate Failed",
            f"Recipe {recipe_id!r} failed every-frame QA with {error_count} error(s) (receipt {receipt_sha256[:16]}...).",
        )


class MotionTraceError(VideoMotionError):
    """Raised when a motion observation trace cannot be segmented or fitted."""

    def __init__(self, detail: str) -> None:
        super().__init__(422, "invalid_motion_trace", "Invalid Motion Observation Trace", detail)


class RecipeNotFoundError(VideoMotionError):
    """Raised when a requested recipe ID is not registered in the bundled catalog."""

    def __init__(self, recipe_id: str) -> None:
        super().__init__(
            404,
            "recipe_not_found",
            "Scene Recipe Not Found",
            f"Scene recipe {recipe_id!r} was not found in the active catalog.",
        )


class BundledDataMissingError(VideoMotionError):
    """Raised when packaged example recipes or traces are absent, instead of returning nothing."""

    def __init__(self, detail: str) -> None:
        super().__init__(500, "bundled_data_missing", "Bundled Data Missing", detail)
