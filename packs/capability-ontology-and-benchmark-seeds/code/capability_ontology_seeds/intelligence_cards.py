"""Typed intelligence card validation, canonical I/O-port signature hashing and OSS release diffing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .grid_config import NodeGrid


@dataclass(frozen=True)
class ToolProfile:
    """Universal typed intelligence card for AI tools, MCP servers, feeds, queues, patterns and releases."""

    profile_id: str
    subject_kind: str
    title: str
    parent_ids: tuple[str, ...]
    facet_labels: tuple[str, ...]
    input_ports: tuple[dict[str, str], ...]
    output_ports: tuple[dict[str, str], ...]
    port_signature_sha256: str
    spdx_license: str
    execution_mode: str
    min_ram_mb: int
    cost_per_1k_ops_usd: float
    mcp_transport: str
    mcp_tools: tuple[str, ...]
    feed_cadence: str
    failure_modes: tuple[str, ...]
    verification_command: str
    metadata: dict[str, Any]


def _normalize_ports(ports: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    normalized = [
        {
            "name": str(item["name"]).strip(),
            "media_type": str(item["media_type"]).strip().lower(),
            "schema_ref": str(item["schema_ref"]).strip(),
        }
        for item in ports
    ]
    for port in normalized:
        if not port["name"] or not port["media_type"] or not port["schema_ref"]:
            raise ValueError(f"incomplete I/O port specification: {port}")
    normalized.sort(key=lambda item: (item["media_type"], item["schema_ref"], item["name"]))
    return tuple(normalized)


def compute_io_port_signature(
    input_ports: Sequence[Mapping[str, Any]],
    output_ports: Sequence[Mapping[str, Any]],
    *,
    grid: NodeGrid,
) -> str:
    """Compute canonical SHA-256 signature over input and output media_type + schema_ref contracts."""
    norm_in = _normalize_ports(input_ports)
    norm_out = _normalize_ports(output_ports)
    contract_shape = {
        "inputs": [{"media_type": p["media_type"], "schema_ref": p["schema_ref"]} for p in norm_in],
        "outputs": [{"media_type": p["media_type"], "schema_ref": p["schema_ref"]} for p in norm_out],
    }
    encoded = json.dumps(contract_shape, sort_keys=True, separators=(",", ":")).encode("utf-8")
    full_hex = hashlib.sha256(encoded).hexdigest()
    return full_hex[: grid.sha256_prefix_chars] if grid.sha256_prefix_chars < 0 else full_hex


def validate_and_normalize_profile(
    raw: Mapping[str, Any],
    *,
    grid: NodeGrid,
    known_node_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Validate an intelligence card dictionary and return a normalized ToolProfile with I/O signature."""
    errors: list[str] = []
    profile_id = str(raw.get("profile_id", "")).strip()
    title = str(raw.get("title", "")).strip()
    subject_kind = str(raw.get("subject_kind", "")).strip()
    spdx_license = str(raw.get("spdx_license", "")).strip()
    execution_mode = str(raw.get("execution_mode", "")).strip()
    mcp_transport = str(raw.get("mcp_transport", "none")).strip()
    verification_command = str(raw.get("verification_command", "")).strip()

    allowed_kinds = set(grid.spec["allowed_subject_kinds"])
    allowed_modes = set(grid.spec["allowed_execution_modes"])
    allowed_transports = set(grid.spec["allowed_mcp_transports"])

    if not profile_id:
        errors.append("missing_profile_id")
    if not title:
        errors.append("missing_title")
    if subject_kind not in allowed_kinds:
        errors.append(f"invalid_subject_kind:{subject_kind}")
    if not spdx_license:
        errors.append("missing_spdx_license")
    if execution_mode not in allowed_modes:
        errors.append(f"invalid_execution_mode:{execution_mode}")
    if mcp_transport not in allowed_transports:
        errors.append(f"invalid_mcp_transport:{mcp_transport}")
    if not verification_command:
        errors.append("missing_verification_command")

    parents = tuple(dict.fromkeys(str(p).strip() for p in raw.get("parent_ids", ()) if str(p).strip()))
    if not parents:
        errors.append("missing_parent_ids")
    elif known_node_ids is not None:
        unknown_parents = [pid for pid in parents if pid not in known_node_ids]
        if unknown_parents:
            errors.append(f"unknown_parent_ids:{','.join(sorted(unknown_parents))}")

    failure_modes = tuple(dict.fromkeys(str(f).strip() for f in raw.get("failure_modes", ()) if str(f).strip()))
    if not failure_modes:
        errors.append("missing_failure_modes")

    mcp_tools = tuple(dict.fromkeys(str(t).strip() for t in raw.get("mcp_tools", ()) if str(t).strip()))
    if subject_kind == "mcp_server" and (mcp_transport == "none" or not mcp_tools):
        errors.append("mcp_server_requires_transport_and_tools")

    try:
        in_ports = _normalize_ports(raw.get("input_ports", ()))
        out_ports = _normalize_ports(raw.get("output_ports", ()))
        if not in_ports or not out_ports:
            errors.append("missing_io_ports")
    except (KeyError, TypeError, ValueError):
        in_ports = ()
        out_ports = ()
        errors.append("malformed_io_ports")

    min_ram_mb = int(raw.get("min_ram_mb", 0))
    cost_per_1k = float(raw.get("cost_per_1k_ops_usd", 0.0))
    if min_ram_mb < 0:
        errors.append("negative_min_ram_mb")
    if cost_per_1k < 0.0:
        errors.append("negative_cost_per_1k_ops")

    if errors:
        return {"valid": False, "errors": errors, "profile": None}

    sig = compute_io_port_signature(in_ports, out_ports, grid=grid)
    profile = ToolProfile(
        profile_id=profile_id,
        subject_kind=subject_kind,
        title=title,
        parent_ids=parents,
        facet_labels=tuple(dict.fromkeys(str(f).strip() for f in raw.get("facet_labels", ()) if str(f).strip())),
        input_ports=in_ports,
        output_ports=out_ports,
        port_signature_sha256=sig,
        spdx_license=spdx_license,
        execution_mode=execution_mode,
        min_ram_mb=min_ram_mb,
        cost_per_1k_ops_usd=round(cost_per_1k, grid.float_round_digits),
        mcp_transport=mcp_transport,
        mcp_tools=mcp_tools,
        feed_cadence=str(raw.get("feed_cadence", "on_release")).strip(),
        failure_modes=failure_modes,
        verification_command=verification_command,
        metadata=dict(raw.get("metadata", {})),
    )
    return {"valid": True, "errors": [], "profile": profile}


def group_interchangeable_profiles(
    profiles: Sequence[ToolProfile],
    *,
    grid: NodeGrid,
) -> dict[str, list[str]]:
    """Cluster ToolProfiles by identical canonical I/O-port signature for hot-swappable head-to-head runs."""
    _ = grid
    clusters: dict[str, list[str]] = {}
    for prof in profiles:
        clusters.setdefault(prof.port_signature_sha256, []).append(prof.profile_id)
    for sig in clusters:
        clusters[sig].sort()
    return dict(sorted(clusters.items()))


def diff_release_into_profile(
    prior: ToolProfile | None,
    release_event: Mapping[str, Any],
    *,
    grid: NodeGrid,
    known_node_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Harvest and diff a new OSS release, paper or hackathon entry into a typed ToolProfile."""
    normalized = validate_and_normalize_profile(release_event, grid=grid, known_node_ids=known_node_ids)
    if not normalized["valid"]:
        return {"valid": False, "errors": normalized["errors"], "diff": None, "profile": None}
    updated: ToolProfile = normalized["profile"]
    if prior is None:
        return {
            "valid": True,
            "errors": [],
            "profile": updated,
            "diff": {
                "change_kind": "new_capability_entry",
                "io_signature_changed": True,
                "license_changed": False,
                "added_mcp_tools": list(updated.mcp_tools),
                "removed_mcp_tools": [],
                "ram_delta_mb": updated.min_ram_mb,
            },
        }
    added_tools = sorted(set(updated.mcp_tools) - set(prior.mcp_tools))
    removed_tools = sorted(set(prior.mcp_tools) - set(updated.mcp_tools))
    return {
        "valid": True,
        "errors": [],
        "profile": updated,
        "diff": {
            "change_kind": "incremental_release_diff",
            "io_signature_changed": updated.port_signature_sha256 != prior.port_signature_sha256,
            "license_changed": updated.spdx_license != prior.spdx_license,
            "added_mcp_tools": added_tools,
            "removed_mcp_tools": removed_tools,
            "ram_delta_mb": updated.min_ram_mb - prior.min_ram_mb,
        },
    }
