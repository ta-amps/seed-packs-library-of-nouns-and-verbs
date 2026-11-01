"""Universal primitives for emerging artifact velocity normalization, hype filtering and bounded task proposals."""

from __future__ import annotations

from .grid_config import (
    DomainAgnosticNamingGate,
    GridLedger,
    NodeGrid,
    NodeParameter,
    OperationCostLedger,
    ParameterBounds,
    ZeroHardcodedValuesAstGate,
    load_grid_spec,
)
from .radar_engine import (
    BoundedVerbProposal,
    CuratorLensProfile,
    UpstreamSignalRecord,
    VelocitySignalDossier,
    canonicalize_repository_key,
    compute_shingle_simhash64,
    emit_bounded_verb_proposals,
    evaluate_radar_bundle,
    extract_quickstart_commands,
    match_capability_facets,
    match_curator_lenses,
    normalize_and_coalesce_signals,
    score_breakout_dossier,
    simhash_hamming_distance,
    validate_sanctioned_source_url,
)

__all__ = [
    "BoundedVerbProposal",
    "CuratorLensProfile",
    "DomainAgnosticNamingGate",
    "GridLedger",
    "NodeGrid",
    "NodeParameter",
    "OperationCostLedger",
    "ParameterBounds",
    "UpstreamSignalRecord",
    "VelocitySignalDossier",
    "ZeroHardcodedValuesAstGate",
    "canonicalize_repository_key",
    "compute_shingle_simhash64",
    "emit_bounded_verb_proposals",
    "evaluate_radar_bundle",
    "extract_quickstart_commands",
    "load_grid_spec",
    "match_capability_facets",
    "match_curator_lenses",
    "normalize_and_coalesce_signals",
    "score_breakout_dossier",
    "simhash_hamming_distance",
    "validate_sanctioned_source_url",
]
