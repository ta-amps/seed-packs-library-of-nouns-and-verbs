"""Combinatorial niche-cell forge, page-cursor ledger and rotating search-path builder."""

from __future__ import annotations

import hashlib
import json
from typing import Any

INTENTS: tuple[str, ...] = (
    "toolkit",
    "template",
    "framework",
    "editor",
    "tutorial",
    "awesome-list",
    "dataset",
    "generator",
    "plugin",
    "starter-kit",
    "design-pattern",
    "benchmark",
)

ANGLES: tuple[str, ...] = (
    "indie-creators",
    "beginners",
    "professionals",
    "open-source-alternative",
    "workflow",
    "case-study",
)

INDUSTRY_VERTICALS: tuple[str, ...] = (
    "nonprofit-ops",
    "healthcare",
    "education",
    "disaster-relief",
    "legal-aid",
    "housing-clinics",
    "accessibility",
    "civic-data",
    "environmental-monitoring",
    "public-transit",
    "multilingual-services",
    "labor-rights",
    "food-security",
    "archival-preservation",
    "open-science",
    "rural-connectivity",
)

PLATFORMS: tuple[str, ...] = ("web", "desktop", "mobile", "browser-extension")

ROTATING_LICENSES: tuple[str, ...] = ("MIT", "Apache-2.0", "BSD-3-Clause", "CC0-1.0")
ROTATING_DAY_WINDOWS: tuple[int, ...] = (7, 30, 365)
ROTATING_STAR_BANDS: tuple[str, ...] = ("0..10", "10..100", "100..1000")

NEGATIVE_GUARD_TERMS: tuple[str, ...] = ("-interview", "-leetcode", "-homework")

DOMAIN_SEEDS: dict[str, dict[str, tuple[str, ...]]] = {
    "game-design": {
        "facets": ("level design", "narrative design", "economy balancing", "procedural generation", "playtest telemetry"),
        "stacks": ("Godot", "Unity", "Unreal", "Python", "TypeScript"),
    },
    "blender-and-3d": {
        "facets": ("geometry nodes", "procedural materials", "rigging automation", "low-poly blockout"),
        "stacks": ("Blender Python", "glTF", "OpenUSD"),
    },
    "godot-design": {
        "facets": ("tilemap editor", "dialogue graph", "state machine", "CSG greybox"),
        "stacks": ("GDScript", "Godot 4", "C#"),
    },
    "ocr-and-document-ai": {
        "facets": ("handwritten intake OCR", "table layout extraction", "multilingual receipt OCR", "PDF form parser"),
        "stacks": ("Tesseract", "PaddleOCR", "ONNX", "Python"),
    },
    "threejs-and-webgpu": {
        "facets": ("spatial scene graph", "shader postprocessing", "instanced terrain", "WebXR inspector"),
        "stacks": ("Three.js", "React Three Fiber", "WebGPU"),
    },
    "privacy-tools": {
        "facets": ("local PII redaction", "differential privacy analytics", "metadata scrubber", "zero-knowledge proof"),
        "stacks": ("Rust", "WebAssembly", "Python"),
    },
    "gis-and-maps": {
        "facets": ("offline vector tiles", "isochrone routing", "disaster shelter mapping", "cartography grammar"),
        "stacks": ("MapLibre", "GeoJSON", "PostGIS"),
    },
    "design-systems-and-ui": {
        "facets": ("accessible color contrast", "typography scale", "motion token spec", "wireframe kit"),
        "stacks": ("CSS", "SVG", "HTML"),
    },
    "llm-and-agent-harnesses": {
        "facets": ("MCP tool server", "context knapsack", "deterministic verifier", "lease queue worker"),
        "stacks": ("Python", "TypeScript", "SQLite"),
    },
    "robotics-and-iot": {
        "facets": ("kinematic planner", "URDF workbench", "sensor calibration"),
        "stacks": ("ROS2", "Python", "C++"),
    },
}

CROSS_DOMAIN_HYBRIDS: tuple[dict[str, str], ...] = (
    {
        "domain": "ocr-and-document-ai",
        "niche": "invoice and handwritten intake OCR for community healthcare clinics",
        "query": '"intake" "OCR" (Tesseract OR PaddleOCR) -interview -leetcode',
    },
    {
        "domain": "gis-and-maps",
        "niche": "offline GIS shelter map design for disaster-relief teams",
        "query": '"offline map" ("shelter" OR "relief") (MapLibre OR GeoJSON) -interview',
    },
    {
        "domain": "privacy-tools",
        "niche": "privacy-preserving local PII redaction for nonprofit intake forms",
        "query": '"PII redaction" ("local" OR "offline") -interview -leetcode',
    },
    {
        "domain": "threejs-and-webgpu",
        "niche": "accessible WebGPU and Three.js spatial storyboard deck",
        "query": '("Three.js" OR "WebGPU") "storyboard" -interview -leetcode',
    },
)


def _cell_id(domain: str, facet: str, intent: str, modifier: str) -> str:
    digest = hashlib.sha256(f"{domain}|{facet}|{intent}|{modifier}".encode("utf-8")).hexdigest()[:12]
    slug = domain.replace(" ", "-").lower()
    return f"cell.{slug}.{digest}"


def mint_combinatorial_niche_catalog(
    *,
    domains: list[str] | None = None,
    custom_phrases: list[str] | None = None,
    max_intents: int = 4,
    max_angles: int = 2,
    max_verticals: int = 2,
) -> dict[str, Any]:
    """Deterministically cross domain facets with intents, angles, stacks, verticals and hybrids."""
    selected = domains if domains is not None else sorted(DOMAIN_SEEDS.keys())
    cells: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for dom in selected:
        spec = DOMAIN_SEEDS.get(dom)
        if not spec:
            continue
        facets = spec["facets"]
        stacks = spec["stacks"]
        for facet in facets:
            for intent in INTENTS[:max_intents]:
                for angle in ANGLES[:max_angles]:
                    cid = _cell_id(dom, facet, intent, f"angle:{angle}")
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        q = f'"{facet}" "{intent}" {angle.replace("-", " ")} {" ".join(NEGATIVE_GUARD_TERMS)}'
                        cells.append({
                            "cell_id": cid,
                            "domain": dom,
                            "facet": facet,
                            "intent": intent,
                            "modifier": angle,
                            "family": "base_grid",
                            "query": q,
                            "page_cursor": 1,
                            "max_pages": 5,
                        })
                for stack in stacks[:2]:
                    cid = _cell_id(dom, facet, intent, f"stack:{stack}")
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        q = f'"{facet}" "{intent}" "{stack}" {" ".join(NEGATIVE_GUARD_TERMS)}'
                        cells.append({
                            "cell_id": cid,
                            "domain": dom,
                            "facet": facet,
                            "intent": intent,
                            "modifier": stack,
                            "family": "stack_cross",
                            "query": q,
                            "page_cursor": 1,
                            "max_pages": 5,
                        })
                for vertical in INDUSTRY_VERTICALS[:max_verticals]:
                    for platform in PLATFORMS[:1]:
                        cid = _cell_id(dom, facet, intent, f"vertical:{vertical}:{platform}")
                        if cid not in seen_ids:
                            seen_ids.add(cid)
                            q = f'"{facet}" "{vertical.replace("-", " ")}" {platform} {" ".join(NEGATIVE_GUARD_TERMS)}'
                            cells.append({
                                "cell_id": cid,
                                "domain": dom,
                                "facet": facet,
                                "intent": intent,
                                "modifier": f"{vertical}:{platform}",
                                "family": "vertical_platform",
                                "query": q,
                                "page_cursor": 1,
                                "max_pages": 5,
                            })

    for hyb in CROSS_DOMAIN_HYBRIDS:
        if hyb["domain"] in selected:
            cid = _cell_id(hyb["domain"], hyb["niche"], "hybrid", "cross")
            if cid not in seen_ids:
                seen_ids.add(cid)
                cells.append({
                    "cell_id": cid,
                    "domain": hyb["domain"],
                    "facet": hyb["niche"],
                    "intent": "hybrid",
                    "modifier": "cross-domain",
                    "family": "cross_hybrid",
                    "query": hyb["query"],
                    "page_cursor": 1,
                    "max_pages": 5,
                })

    for phrase in custom_phrases or []:
        clean = phrase.strip()
        if not clean:
            continue
        cid = _cell_id("custom-injected", clean, "toolkit", "custom")
        if cid not in seen_ids:
            seen_ids.add(cid)
            cells.append({
                "cell_id": cid,
                "domain": "custom-injected",
                "facet": clean,
                "intent": "toolkit",
                "modifier": "injected",
                "family": "custom_domain",
                "query": f'"{clean}" (toolkit OR framework OR template) {" ".join(NEGATIVE_GUARD_TERMS)}',
                "page_cursor": 1,
                "max_pages": 5,
            })

    catalog_sha = hashlib.sha256(
        json.dumps([c["cell_id"] for c in cells], separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "domain_count": len(set(c["domain"] for c in cells)),
        "cell_count": len(cells),
        "catalog_sha256": catalog_sha,
        "cells": cells,
    }


def advance_cell_page_cursor(cell: dict[str, Any]) -> dict[str, Any]:
    """Return the next uncovered page request for a cell without repeating covered pages."""
    cur = int(cell.get("page_cursor", 1))
    max_p = int(cell.get("max_pages", 5))
    exhausted = cur > max_p
    updated = dict(cell)
    if not exhausted:
        updated["page_cursor"] = cur + 1
    return {
        "cell_id": cell["cell_id"],
        "fetched_page": None if exhausted else cur,
        "exhausted": exhausted,
        "updated_cell": updated,
    }


def build_rotating_domain_paths(domain: str, facet: str, cycle_index: int) -> list[dict[str, str]]:
    """Build 8 orthogonal rotating search paths (license, radar, star-band, in:readme, multilingual)."""
    lic = ROTATING_LICENSES[cycle_index % len(ROTATING_LICENSES)]
    days = ROTATING_DAY_WINDOWS[cycle_index % len(ROTATING_DAY_WINDOWS)]
    stars = ROTATING_STAR_BANDS[cycle_index % len(ROTATING_STAR_BANDS)]
    guards = " ".join(NEGATIVE_GUARD_TERMS)
    return [
        {"family": "base_grid", "query": f'"{facet}" toolkit {guards}'},
        {"family": "license_free", "query": f'"{facet}" license:{lic} {guards}'},
        {"family": "new_repo_radar", "query": f'"{facet}" created:>=-{days}d stars:<100 {guards}'},
        {"family": "star_band_middle", "query": f'"{facet}" stars:{stars} {guards}'},
        {"family": "in_readme_deep", "query": f'"{facet}" in:readme stars:0..25 {guards}'},
        {"family": "awesome_list", "query": f'"awesome" "{facet}" in:name,readme'},
        {"family": "dataset_benchmark", "query": f'"{facet}" (dataset OR benchmark) license:{lic} {guards}'},
        {"family": "active_unknowns", "query": f'"{facet}" pushed:>=-30d stars:<20 {guards}'},
    ]
