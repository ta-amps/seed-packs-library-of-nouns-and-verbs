"""Standard-library repository readiness and weighted evaluation rubric auditor."""

from .auditor import (
    DEFAULT_RUBRIC_PILLARS,
    audit_repository_manifest,
    build_manifest_from_directory,
)

__all__ = [
    "DEFAULT_RUBRIC_PILLARS",
    "audit_repository_manifest",
    "build_manifest_from_directory",
]
