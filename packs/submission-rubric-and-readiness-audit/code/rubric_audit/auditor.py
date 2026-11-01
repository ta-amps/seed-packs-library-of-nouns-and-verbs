"""Weighted evaluation rubric auditor separating wired code evidence from prose-only claims."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

DEFAULT_RUBRIC_PILLARS: dict[str, dict[str, Any]] = {
    "impact_specificity": {
        "title": "Problem Specificity, Target User Clarity & Active Window",
        "weight_pct": 30.0,
        "max_points": 3.0,
    },
    "verified_open_weight_and_multimodal_models": {
        "title": "Verified Open-Weight, Multimodal & SDK Wiring",
        "weight_pct": 25.0,
        "max_points": 2.5,
    },
    "modular_source_tests_ci_depth": {
        "title": "Commit Cadence, Modular Source, Tests, CI & Containers",
        "weight_pct": 20.0,
        "max_points": 2.0,
    },
    "live_endpoint_and_video_completeness": {
        "title": "Verified Live Endpoint & Recorded Video Walkthrough",
        "weight_pct": 25.0,
        "max_points": 2.5,
    },
}

_KNOWN_MODEL_SIGNATURES: dict[str, tuple[str, ...]] = {
    "llama_open_weights": ("llama-3", "llama-4", "llama3", "llama4", "meta-llama", "llama_stack"),
    "sam_segmentation": ("segment_anything", "sam2", "sam3", "sam_predictor", "mask_generator"),
    "speech_audio": ("seamless_communication", "whisper", "mms_tts", "wav2vec2", "audiocraft", "torchaudio"),
    "lora_finetuning": ("peft", "loraconfig", "qlora", "adapter_config.json", "safetensors"),
    "multimodal_vision": ("dinov2", "perception_encoder", "clip_model", "vision_encoder", "open_clip"),
}

_VAGUE_BOILERPLATE_RE = re.compile(
    r"\b(?:revolutionary|synergy|paradigm-shifting|solves everything for everyone|tbd|todo)\b",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s)>\"']+")
_VIDEO_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|loom\.com/share/|vimeo\.com/)[^\s)>\"']+|"
    r"[^\s\"']+\.(?:mp4|webm|mov)\b",
    re.IGNORECASE,
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _detect_model_families(texts: list[str]) -> set[str]:
    joined = "\n".join(texts).lower()
    found: set[str] = set()
    for family, needles in _KNOWN_MODEL_SIGNATURES.items():
        if any(n in joined for n in needles):
            found.add(family)
    return found


def build_manifest_from_directory(
    repo_dir: Path,
    probe_receipts: list[dict[str, Any]] | None = None,
    commits_in_window: int = 0,
    commits_outside_window: int = 0,
) -> dict[str, Any]:
    """Scan a local repository checkout into a deterministic manifest dictionary."""
    readme_text = ""
    for candidate in ("README.md", "readme.md", "README.rst"):
        p = repo_dir / candidate
        if p.is_file():
            readme_text = p.read_text(encoding="utf-8", errors="replace")
            break

    rel_files: list[str] = []
    code_snippets: list[str] = []
    for path in sorted(repo_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_dir).as_posix()
        if any(part in {".git", "node_modules", ".venv", "__pycache__", "dist", "build"} for part in path.parts):
            continue
        rel_files.append(rel)
        if path.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".toml", ".json", ".yaml", ".yml"} and path.stat().st_size <= 131072:
            if path.name.lower() not in {"readme.md"}:
                code_snippets.append(path.read_text(encoding="utf-8", errors="replace"))

    return {
        "repo_id": repo_dir.name,
        "readme_text": readme_text,
        "files": rel_files,
        "code_and_config_blobs": code_snippets,
        "commits_in_window": commits_in_window,
        "commits_outside_window": commits_outside_window,
        "probe_receipts": probe_receipts or [],
    }


def audit_repository_manifest(
    manifest: dict[str, Any],
    pillars: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score a repository manifest across weighted rubric pillars with evidence-backed deductions."""
    spec = pillars or DEFAULT_RUBRIC_PILLARS
    readme = str(manifest.get("readme_text") or "")
    files = [str(f) for f in (manifest.get("files") or [])]
    code_blobs = [str(c) for c in (manifest.get("code_and_config_blobs") or [])]
    in_win = int(manifest.get("commits_in_window") or 0)
    out_win = int(manifest.get("commits_outside_window") or 0)
    probes = list(manifest.get("probe_receipts") or [])

    remediations: list[dict[str, Any]] = []
    blockers: list[str] = []

    # 1. Impact & specificity (max 3.0 by default)
    p1_max = float(spec["impact_specificity"]["max_points"])
    p1_fraction = 0.0
    readme_words = re.findall(r"[A-Za-z0-9]+", readme)
    has_problem = bool(re.search(r"\b(?:problem|challenge|bottleneck|pain|gap|failure)\b", readme, re.IGNORECASE)) and len(readme_words) >= 40
    has_target_user = bool(re.search(r"\b(?:users?|operators?|engineers?|clinicians?|teams?|analysts?|workers?)\b", readme, re.IGNORECASE))
    has_domain_metrics = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:%|ms|s|x|pts|records|frames|tokens)\b", readme, re.IGNORECASE))
    window_dominant = in_win >= 2 and in_win >= out_win
    has_vague = bool(_VAGUE_BOILERPLATE_RE.search(readme))

    if has_problem:
        p1_fraction += 0.35
    else:
        remediations.append({
            "pillar": "impact_specificity",
            "action": "Document a concrete problem statement (>= 40 words) naming the exact operational failure mode.",
            "recoverable_points": round(p1_max * 0.35, 2),
        })
    if has_target_user:
        p1_fraction += 0.25
    else:
        remediations.append({
            "pillar": "impact_specificity",
            "action": "Name the specific target operator or user cohort and workflow boundary in README.md.",
            "recoverable_points": round(p1_max * 0.25, 2),
        })
    if has_domain_metrics:
        p1_fraction += 0.20
    else:
        remediations.append({
            "pillar": "impact_specificity",
            "action": "Include concrete quantitative constraints or measured latency/accuracy/throughput bounds.",
            "recoverable_points": round(p1_max * 0.20, 2),
        })
    if window_dominant:
        p1_fraction += 0.20
    else:
        remediations.append({
            "pillar": "impact_specificity",
            "action": "Verify commit history shows active development inside the evaluation window.",
            "recoverable_points": round(p1_max * 0.20, 2),
        })
    if has_vague:
        p1_fraction = max(0.0, p1_fraction - 0.15)
    p1_pts = round(min(p1_max, p1_max * p1_fraction), 2)

    # 2. Verified open-weight & multimodal models (max 2.5 by default)
    p2_max = float(spec["verified_open_weight_and_multimodal_models"]["max_points"])
    readme_families = _detect_model_families([readme])
    code_families = _detect_model_families(code_blobs + files)
    unverified_prose_claims = sorted(readme_families - code_families)
    verified_families = sorted(code_families)

    if len(verified_families) >= 2:
        p2_fraction = 1.0
    elif len(verified_families) == 1:
        p2_fraction = 0.68
        remediations.append({
            "pillar": "verified_open_weight_and_multimodal_models",
            "action": "Add a second verified open-weight, multimodal segmentation/speech, or fine-tuned adapter integration in source code.",
            "recoverable_points": round(p2_max * 0.32, 2),
        })
    else:
        p2_fraction = 0.0
        blockers.append("No open-weight, multimodal, or adapter model usage verified in source/config files.")
        remediations.append({
            "pillar": "verified_open_weight_and_multimodal_models",
            "action": "Wire open-weight or multimodal SDK/model calls directly in runnable source modules rather than README prose alone.",
            "recoverable_points": round(p2_max, 2),
        })
    if unverified_prose_claims:
        blockers.append(f"README claims model families absent from code: {', '.join(unverified_prose_claims)}")
    p2_pts = round(p2_max * p2_fraction, 2)

    # 3. Technical depth: modular source, tests, CI, container, commit cadence (max 2.0 by default)
    p3_max = float(spec["modular_source_tests_ci_depth"]["max_points"])
    src_modules = [
        f for f in files
        if ("/" in f) and f.endswith((".py", ".ts", ".tsx", ".rs", ".go")) and not f.startswith("tests/") and "test_" not in f
    ]
    test_files = [
        f for f in files
        if f.startswith("tests/") or "/tests/" in f or Path(f).name.startswith("test_") or f.endswith((".test.ts", ".spec.ts"))
    ]
    ci_files = [f for f in files if f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml"))]
    container_files = [
        f for f in files
        if Path(f).name in {"Dockerfile", "Containerfile", "docker-compose.yml", "compose.yaml", "compose.yml"}
    ]

    p3_fraction = 0.0
    if len(src_modules) >= 2:
        p3_fraction += 0.25
    else:
        remediations.append({
            "pillar": "modular_source_tests_ci_depth",
            "action": "Split monolithic scripts into a modular package directory with at least two focused source modules.",
            "recoverable_points": round(p3_max * 0.25, 2),
        })
    if test_files:
        p3_fraction += 0.30
    else:
        blockers.append("No automated unit or integration test files detected.")
        remediations.append({
            "pillar": "modular_source_tests_ci_depth",
            "action": "Add deterministic unit tests under tests/ covering core execution paths and edge cases.",
            "recoverable_points": round(p3_max * 0.30, 2),
        })
    if ci_files:
        p3_fraction += 0.20
    else:
        remediations.append({
            "pillar": "modular_source_tests_ci_depth",
            "action": "Add a .github/workflows/ CI check that compiles and runs the test suite on push/PR.",
            "recoverable_points": round(p3_max * 0.20, 2),
        })
    if container_files:
        p3_fraction += 0.15
    else:
        remediations.append({
            "pillar": "modular_source_tests_ci_depth",
            "action": "Include a reproducible Dockerfile or compose.yaml so reviewers can boot the stack cleanly.",
            "recoverable_points": round(p3_max * 0.15, 2),
        })
    if in_win >= 5:
        p3_fraction += 0.10
    p3_pts = round(min(p3_max, p3_max * p3_fraction), 2)

    # 4. Demo completeness: documented + probe-verified live endpoint & video walkthrough (max 2.5 by default)
    p4_max = float(spec["live_endpoint_and_video_completeness"]["max_points"])
    doc_urls = set(_URL_RE.findall(readme))
    video_urls = [m.group(0) for m in _VIDEO_URL_RE.finditer(readme)]
    verified_live_urls: list[str] = []
    for pr in probes:
        url = str(pr.get("url") or "")
        status = int(pr.get("http_status") or 0)
        digest = str(pr.get("body_sha256") or "")
        if url and status == 200 and _SHA256_RE.match(digest):
            if not doc_urls or url in doc_urls or any(url.startswith(u.rstrip("/")) or u.startswith(url.rstrip("/")) for u in doc_urls):
                verified_live_urls.append(url)

    p4_fraction = 0.0
    if verified_live_urls:
        p4_fraction += 0.55
    elif doc_urls:
        p4_fraction += 0.15
        blockers.append("Live URL cited in README lacks an HTTP 200 + SHA-256 verification probe receipt.")
        remediations.append({
            "pillar": "live_endpoint_and_video_completeness",
            "action": "Record a dated HTTP 200 probe receipt with SHA-256 body digest for the documented live endpoint.",
            "recoverable_points": round(p4_max * 0.40, 2),
        })
    else:
        blockers.append("No public web endpoint URL documented or probe-verified.")
        remediations.append({
            "pillar": "live_endpoint_and_video_completeness",
            "action": "Document a live web endpoint URL in README.md and verify HTTP 200 reachability.",
            "recoverable_points": round(p4_max * 0.55, 2),
        })

    if video_urls:
        p4_fraction += 0.45
    else:
        remediations.append({
            "pillar": "live_endpoint_and_video_completeness",
            "action": "Embed a recorded video walkthrough link in README.md demonstrating the end-to-end user flow.",
            "recoverable_points": round(p4_max * 0.45, 2),
        })
    p4_pts = round(min(p4_max, p4_max * p4_fraction), 2)

    total_pts = round(p1_pts + p2_pts + p3_pts + p4_pts, 2)
    max_total = round(sum(float(v["max_points"]) for v in spec.values()), 2)
    remediations.sort(key=lambda r: (-r["recoverable_points"], r["pillar"]))

    canonical_payload = f"{manifest.get('repo_id', 'repo')}|{len(files)}|{total_pts}"
    audit_sha = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    return {
        "repo_id": str(manifest.get("repo_id") or "unknown-repo"),
        "audit_fingerprint_sha256": audit_sha,
        "total_points": total_pts,
        "max_points": max_total,
        "readiness_tier": (
            "submission_ready" if total_pts >= 8.0 and not blockers
            else "needs_targeted_fixes" if total_pts >= 5.0
            else "incomplete"
        ),
        "pillar_scores": {
            "impact_specificity": {"points": p1_pts, "max_points": p1_max},
            "verified_open_weight_and_multimodal_models": {
                "points": p2_pts,
                "max_points": p2_max,
                "verified_families": verified_families,
                "unverified_prose_claims": unverified_prose_claims,
            },
            "modular_source_tests_ci_depth": {
                "points": p3_pts,
                "max_points": p3_max,
                "source_modules": len(src_modules),
                "test_files": len(test_files),
                "ci_workflows": len(ci_files),
                "container_specs": len(container_files),
            },
            "live_endpoint_and_video_completeness": {
                "points": p4_pts,
                "max_points": p4_max,
                "verified_live_urls": verified_live_urls,
                "video_walkthrough_urls": video_urls,
            },
        },
        "blockers": blockers,
        "prioritized_remediations": remediations,
    }
