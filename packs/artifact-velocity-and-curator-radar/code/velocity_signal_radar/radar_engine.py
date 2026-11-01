"""Sanctioned multi-source velocity normalization, 64-bit SimHash deduplication, hype filtering and proposal emission."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit

from .grid_config import GridLedger, NodeGrid, OperationCostLedger

GITHUB_PATH_RE = re.compile(r"^/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+.-]*")


@dataclass(frozen=True)
class UpstreamSignalRecord:
    """Single sanctioned public sighting of a repository or release artifact."""

    signal_id: str
    source_channel: str
    source_url: str
    repository_url: str
    created_at_iso: str
    stars: int
    forks: int
    hn_points: int
    hf_upvotes: int
    repo_size_kb: int
    spdx_license: str
    primary_language: str
    topics: tuple[str, ...]
    summary_text: str
    readme_excerpt: str
    curator_lens_hint: str = ""

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> UpstreamSignalRecord:
        return cls(
            signal_id=str(raw["signal_id"]),
            source_channel=str(raw["source_channel"]),
            source_url=str(raw["source_url"]),
            repository_url=str(raw["repository_url"]),
            created_at_iso=str(raw["created_at_iso"]),
            stars=max(0, int(raw.get("stars", 0))),
            forks=max(0, int(raw.get("forks", 0))),
            hn_points=max(0, int(raw.get("hn_points", 0))),
            hf_upvotes=max(0, int(raw.get("hf_upvotes", 0))),
            repo_size_kb=max(0, int(raw.get("repo_size_kb", 0))),
            spdx_license=str(raw.get("spdx_license") or "NONE"),
            primary_language=str(raw.get("primary_language") or "unknown"),
            topics=tuple(str(t).strip().lower() for t in raw.get("topics", ()) if str(t).strip()),
            summary_text=str(raw.get("summary_text") or "").strip(),
            readme_excerpt=str(raw.get("readme_excerpt") or "").strip(),
            curator_lens_hint=str(raw.get("curator_lens_hint") or "").strip(),
        )


@dataclass(frozen=True)
class CuratorLensProfile:
    """Declarative curator lens profile storing topic heuristics without wall scraping."""

    lens_id: str
    reference_urls: tuple[str, ...]
    keywords: tuple[str, ...]
    authenticated_wall_scraping_prohibited: bool = True

    def validate(self, grid: NodeGrid) -> None:
        if grid.allow_authenticated_wall_scraping or not self.authenticated_wall_scraping_prohibited:
            raise ValueError("authenticated_wall_scraping_must_remain_prohibited")
        if not self.lens_id.strip():
            raise ValueError("lens_id must be non-empty")
        if not self.keywords:
            raise ValueError("keywords must be non-empty")


@dataclass(frozen=True)
class VelocitySignalDossier:
    """Normalized, deduplicated and scored breakout dossier for an open-source repository."""

    canonical_repo_key: str
    canonical_repo_url: str
    created_at_iso: str
    age_days: float
    stars: int
    forks: int
    stars_per_day: float
    fork_ratio: float
    corroborated_channels: tuple[str, ...]
    spdx_license: str
    permissive_license: bool
    primary_language: str
    quickstart_commands: tuple[str, ...]
    runtime_footprints: tuple[str, ...]
    capability_facet_ids: tuple[str, ...]
    curator_lens_ids: tuple[str, ...]
    simhash64_hex: str
    lsh_bands: tuple[str, ...]
    already_in_seed_archive: bool
    linked_archive_key: str
    axis_scores: dict[str, float]
    utility_score_milli: int
    hype_penalty_milli: int
    breakout_score_milli: int
    passes_breakout_gate: bool
    problem_solved: str
    integration_hooks: tuple[str, ...]
    demo_potential: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_repo_key": self.canonical_repo_key,
            "canonical_repo_url": self.canonical_repo_url,
            "created_at_iso": self.created_at_iso,
            "age_days": self.age_days,
            "stars": self.stars,
            "forks": self.forks,
            "stars_per_day": self.stars_per_day,
            "fork_ratio": self.fork_ratio,
            "corroborated_channels": list(self.corroborated_channels),
            "spdx_license": self.spdx_license,
            "permissive_license": self.permissive_license,
            "primary_language": self.primary_language,
            "quickstart_commands": list(self.quickstart_commands),
            "runtime_footprints": list(self.runtime_footprints),
            "capability_facet_ids": list(self.capability_facet_ids),
            "curator_lens_ids": list(self.curator_lens_ids),
            "simhash64_hex": self.simhash64_hex,
            "lsh_bands": list(self.lsh_bands),
            "already_in_seed_archive": self.already_in_seed_archive,
            "linked_archive_key": self.linked_archive_key,
            "axis_scores": dict(self.axis_scores),
            "utility_score_milli": self.utility_score_milli,
            "hype_penalty_milli": self.hype_penalty_milli,
            "breakout_score_milli": self.breakout_score_milli,
            "passes_breakout_gate": self.passes_breakout_gate,
            "problem_solved": self.problem_solved,
            "integration_hooks": list(self.integration_hooks),
            "demo_potential": self.demo_potential,
        }


@dataclass(frozen=True)
class BoundedVerbProposal:
    """Bounded follow-up task proposal compatible with task queue submission envelopes."""

    proposal_id: str
    proposal_kind: str
    tier: str
    verb_kind: str
    parent_task_id: str
    source_task_id: str
    generation_depth: int
    priority: int
    complexity_milli: int
    target_repo_key: str
    title: str
    prompt: str
    facet_axes: tuple[str, ...]
    search_hints: tuple[str, ...]
    auto_enqueue_permitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.proposal_id,
            "proposal_kind": self.proposal_kind,
            "tier": self.tier,
            "verb_kind": self.verb_kind,
            "parent_task_id": self.parent_task_id,
            "source_task_id": self.source_task_id,
            "generation_depth": self.generation_depth,
            "priority": self.priority,
            "complexity_milli": self.complexity_milli,
            "target_repo_key": self.target_repo_key,
            "title": self.title,
            "prompt": self.prompt,
            "facet_axes": list(self.facet_axes),
            "search_hints": list(self.search_hints),
            "auto_enqueue_permitted": self.auto_enqueue_permitted,
        }


def validate_sanctioned_source_url(url: str, grid: NodeGrid) -> str:
    """Reject direct scraping of login-gated walls and require https sanctioned URLs."""
    parsed = urlsplit(str(url).strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme != "https" or not host:
        raise ValueError("sanctioned_public_api_or_search_lens_only")
    for blocked in grid.prohibited_wall_hosts:
        if host == blocked or host.endswith("." + blocked):
            raise ValueError("sanctioned_public_api_or_search_lens_only")
    return host


def canonicalize_repository_key(url_or_slug: str) -> tuple[str, str]:
    """Normalize a GitHub repository URL or owner/repo string to (github:owner/repo, https_url)."""
    raw = str(url_or_slug).strip()
    if raw.startswith("github:"):
        raw = "https://github.com/" + raw.split(":", 1)[1]
    elif "://" not in raw and "/" in raw:
        raw = "https://github.com/" + raw
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower()
    if host not in ("github.com", "www.github.com"):
        raise ValueError(f"unsupported_repository_host:{host}")
    match = GITHUB_PATH_RE.match(parsed.path)
    if match is None:
        raise ValueError(f"invalid_github_repository_path:{parsed.path}")
    owner = match.group(1)
    repo = match.group(1 + 1)
    canonical_slug = f"{owner.lower()}/{repo.lower()}"
    return f"github:{canonical_slug}", f"https://github.com/{owner}/{repo}"


def _parse_iso_utc(iso_text: str) -> datetime:
    cleaned = str(iso_text).strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_shingle_simhash64(text: str, grid: NodeGrid) -> tuple[str, tuple[str, ...]]:
    """Compute a deterministic 64-bit word-shingle SimHash hex digest and LSH bands."""
    tokens = TOKEN_RE.findall(str(text).lower())
    shingle_n = max(1, grid.default_shingle_size)
    if not tokens:
        shingles = ["empty"]
    elif len(tokens) < shingle_n:
        shingles = [" ".join(tokens)]
    else:
        shingles = [
            " ".join(tokens[idx : idx + shingle_n])
            for idx in range(len(tokens) - shingle_n + 1)
        ]

    bit_width = grid.simhash_bit_width
    weights = [0] * bit_width
    for shingle in shingles:
        digest = hashlib.sha256(shingle.encode("utf-8")).digest()
        for bit_idx in range(bit_width):
            byte_idx = bit_idx // grid.bits_per_byte
            bit_offset = bit_idx % grid.bits_per_byte
            bit_set = (digest[byte_idx] >> bit_offset) & 1
            weights[bit_idx] += 1 if bit_set == 1 else -1

    simhash_val = 0
    for bit_idx, accum in enumerate(weights):
        if accum >= 0:
            simhash_val |= 1 << bit_idx

    simhash_hex = f"{simhash_val:0{grid.simhash_hex_nibbles}x}"
    bands: list[str] = []
    step = grid.lsh_nibbles_per_band
    for band_idx in range(grid.lsh_band_count):
        start = band_idx * step
        bands.append(f"b{band_idx}:{simhash_hex[start : start + step]}")
    return simhash_hex, tuple(bands)


def simhash_hamming_distance(hex_a: str, hex_b: str, grid: NodeGrid) -> int:
    """Compute bit-level Hamming distance between two hex SimHash digests."""
    base = grid.simhash_hex_nibbles
    xor_val = int(hex_a, base) ^ int(hex_b, base)
    return int(xor_val.bit_count())


def extract_quickstart_commands(readme_excerpt: str, grid: NodeGrid) -> tuple[str, ...]:
    """Extract deterministic runnable quickstart/install commands from a README snippet."""
    commands: list[str] = []
    for raw_line in str(readme_excerpt).splitlines():
        cleaned = raw_line.strip().lstrip("$> ").strip("`").strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        if any(lower.startswith(prefix) for prefix in grid.quickstart_command_prefixes):
            if cleaned not in commands:
                commands.append(cleaned)
    return tuple(commands)


def match_curator_lenses(corpus_text: str, hint: str, grid: NodeGrid) -> tuple[str, ...]:
    """Match repository corpus against configured curator-lens topic profiles."""
    lowered = f"{corpus_text} {hint}".lower()
    matched: list[str] = []
    for lens in grid.spec.get("curator_lenses", []):
        lens_id = str(lens["lens_id"])
        if hint and hint == lens_id:
            matched.append(lens_id)
            continue
        if any(str(kw).lower() in lowered for kw in lens.get("keywords", [])):
            matched.append(lens_id)
    return tuple(sorted(set(matched)))


def match_capability_facets(corpus_text: str, grid: NodeGrid) -> tuple[str, ...]:
    """Map repository text onto polyhierarchical capability ontology facet IDs."""
    lowered = str(corpus_text).lower()
    matched: list[str] = []
    for rule in grid.spec.get("capability_facet_rules", []):
        facet_id = str(rule["facet_id"])
        if any(str(kw).lower() in lowered for kw in rule.get("keywords", [])):
            matched.append(facet_id)
    if not matched:
        matched.append("general_software_engineering_primitive")
    return tuple(sorted(set(matched)))


def infer_runtime_footprints(
    primary_language: str,
    repo_size_kb: int,
    corpus_text: str,
    grid: NodeGrid,
) -> tuple[str, ...]:
    """Infer lightweight, CLI, container and cluster runtime footprints."""
    lowered = f"{primary_language} {corpus_text}".lower()
    norms = grid.scoring_normalization()
    footprints: list[str] = []
    if (
        primary_language.lower() in ("rust", "go", "c", "zig")
        or "onnx" in lowered
        or "cpu" in lowered
        or "sqlite" in lowered
        or "cli" in lowered
        or float(repo_size_kb) <= norms["substantial_repo_kb"]
    ):
        footprints.append("runs_on_small_4gb_laptop")
    if any(tok in lowered for tok in ("cli", "zero-dep", "stdlib", "npx ", "uvx ", "cargo install")):
        footprints.append("cli_or_single_command_runner")
    if any(tok in lowered for tok in ("docker", "self-hosted", "compose")):
        footprints.append("self_hosted_container")
    if any(tok in lowered for tok in ("kubernetes", "k8s", "helm", "grpc", "opentelemetry")):
        footprints.append("kubernetes_production_ready")
    if not footprints:
        footprints.append("standard_developer_workstation")
    return tuple(sorted(set(footprints)))


def infer_integration_hooks(corpus_text: str, quickstart_commands: Sequence[str]) -> tuple[str, ...]:
    """Identify protocol and automation integration hooks exposed by a repository."""
    lowered = str(corpus_text).lower()
    hooks: list[str] = []
    if "mcp" in lowered or "model context protocol" in lowered:
        hooks.append("mcp_tool_server_or_client")
    if any(tok in lowered for tok in ("rest", "openapi", "http", "fastapi", "webhook")):
        hooks.append("http_json_or_webhook_endpoint")
    if any(tok in lowered for tok in ("n8n", "workflow", "automation", "cron")):
        hooks.append("workflow_automation_node")
    if quickstart_commands:
        hooks.append("reproducible_cli_invocation")
    if not hooks:
        hooks.append("library_import_adapter")
    return tuple(sorted(set(hooks)))


def normalize_and_coalesce_signals(
    raw_signals: Sequence[Mapping[str, Any] | UpstreamSignalRecord],
    grid: NodeGrid,
    *,
    reference_utc_iso: str,
    active_cell: Mapping[str, Any] | None = None,
    known_archive_repos: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Validate sanctioned sources, reject wall-scrape URLs, and coalesce duplicates via canonical key + SimHash."""
    cell = grid.clamp_cell(active_cell)
    ref_dt = _parse_iso_utc(reference_utc_iso)
    archive_map = {str(k).lower(): str(v) for k, v in (known_archive_repos or {}).items()}
    lookback_days = float(cell["lookback_window_days"])
    max_hamming = int(cell["simhash_hamming_dedup_max"])

    refused_sources: list[dict[str, str]] = []
    grouped: dict[str, dict[str, Any]] = {}

    for item in raw_signals:
        rec = item if isinstance(item, UpstreamSignalRecord) else UpstreamSignalRecord.from_dict(item)
        try:
            validate_sanctioned_source_url(rec.source_url, grid)
            validate_sanctioned_source_url(rec.repository_url, grid)
            repo_key, canonical_url = canonicalize_repository_key(rec.repository_url)
        except ValueError as exc:
            refused_sources.append({
                "signal_id": rec.signal_id,
                "source_url": rec.source_url,
                "reason": str(exc),
            })
            continue

        created_dt = _parse_iso_utc(rec.created_at_iso)
        age_days = max(0.0, (ref_dt - created_dt).total_seconds() / float(grid.seconds_per_day))
        repo_slug_lower = repo_key.split(":", 1)[1]
        in_archive = repo_slug_lower in archive_map or repo_key in archive_map
        if age_days > lookback_days and not in_archive:
            continue

        corpus = " ".join([
            canonical_url,
            rec.summary_text,
            rec.readme_excerpt,
            " ".join(rec.topics),
            rec.primary_language,
        ])
        simhash_hex, lsh_bands = compute_shingle_simhash64(corpus, grid)

        target_key = repo_key
        if target_key not in grouped:
            for existing_key, existing_entry in grouped.items():
                dist = simhash_hamming_distance(simhash_hex, existing_entry["simhash64_hex"], grid)
                if dist <= max_hamming and existing_entry["summary_text"].strip().lower() == rec.summary_text.strip().lower():
                    target_key = existing_key
                    break

        if target_key not in grouped:
            grouped[target_key] = {
                "canonical_repo_key": repo_key,
                "canonical_repo_url": canonical_url,
                "created_at_iso": rec.created_at_iso,
                "age_days": round(age_days, grid.float_round_digits),
                "stars": rec.stars,
                "forks": rec.forks,
                "hn_points": rec.hn_points,
                "hf_upvotes": rec.hf_upvotes,
                "repo_size_kb": rec.repo_size_kb,
                "spdx_license": rec.spdx_license,
                "primary_language": rec.primary_language,
                "topics": set(rec.topics),
                "channels": {rec.source_channel},
                "summary_text": rec.summary_text,
                "readme_excerpt": rec.readme_excerpt,
                "curator_lens_hint": rec.curator_lens_hint,
                "simhash64_hex": simhash_hex,
                "lsh_bands": lsh_bands,
                "already_in_seed_archive": in_archive,
                "linked_archive_key": archive_map.get(repo_slug_lower, archive_map.get(repo_key, "")),
                "merged_signal_ids": [rec.signal_id],
            }
        else:
            entry = grouped[target_key]
            entry["stars"] = max(int(entry["stars"]), rec.stars)
            entry["forks"] = max(int(entry["forks"]), rec.forks)
            entry["hn_points"] = max(int(entry["hn_points"]), rec.hn_points)
            entry["hf_upvotes"] = max(int(entry["hf_upvotes"]), rec.hf_upvotes)
            entry["repo_size_kb"] = max(int(entry["repo_size_kb"]), rec.repo_size_kb)
            if entry["spdx_license"] in ("NONE", "NOASSERTION", "") and rec.spdx_license not in ("NONE", ""):
                entry["spdx_license"] = rec.spdx_license
            entry["topics"].update(rec.topics)
            entry["channels"].add(rec.source_channel)
            if len(rec.readme_excerpt) > len(entry["readme_excerpt"]):
                entry["readme_excerpt"] = rec.readme_excerpt
            if len(rec.summary_text) > len(entry["summary_text"]):
                entry["summary_text"] = rec.summary_text
            if not entry["curator_lens_hint"] and rec.curator_lens_hint:
                entry["curator_lens_hint"] = rec.curator_lens_hint
            entry["merged_signal_ids"].append(rec.signal_id)

    return {
        "coalesced": list(grouped.values()),
        "refused_sources": refused_sources,
    }


def score_breakout_dossier(
    entry: Mapping[str, Any],
    grid: NodeGrid,
    *,
    active_cell: Mapping[str, Any] | None = None,
) -> VelocitySignalDossier:
    """Compute utility axes, apply anti-hype penalties, and produce a typed VelocitySignalDossier."""
    cell = grid.clamp_cell(active_cell)
    regime = str(cell["radar_regime"])
    weights = grid.regime_weights(regime)
    norms = grid.scoring_normalization()
    scale_milli = float(grid.score_scale_milli)

    age_days = max(1.0, float(entry["age_days"]))
    stars = int(entry["stars"])
    forks = int(entry["forks"])
    stars_per_day = round(float(stars) / age_days, grid.float_round_digits)
    fork_ratio = round(float(forks) / float(max(1, stars)), grid.float_round_digits)

    readme_excerpt = str(entry["readme_excerpt"])
    summary_text = str(entry["summary_text"])
    topics_sorted = sorted(str(t) for t in entry["topics"])
    corpus = " ".join([summary_text, readme_excerpt, " ".join(topics_sorted), str(entry["primary_language"])])

    quickstarts = extract_quickstart_commands(readme_excerpt, grid)
    curator_lenses = match_curator_lenses(corpus, str(entry.get("curator_lens_hint", "")), grid)
    capability_facets = match_capability_facets(corpus, grid)
    footprints = infer_runtime_footprints(
        str(entry["primary_language"]),
        int(entry["repo_size_kb"]),
        corpus,
        grid,
    )
    hooks = infer_integration_hooks(corpus, quickstarts)

    spdx = str(entry["spdx_license"])
    permissive = spdx in grid.permissive_spdx_licenses

    star_vel_norm = min(1.0, stars_per_day / norms["stars_per_day_ceiling"])
    hn_norm = min(1.0, float(entry["hn_points"]) / norms["hn_points_ceiling"])
    hf_norm = min(1.0, float(entry["hf_upvotes"]) / norms["hf_upvotes_ceiling"])
    velocity_axis = min(1.0, star_vel_norm + hn_norm * (1.0 - star_vel_norm) + hf_norm * (1.0 - star_vel_norm))

    quickstart_axis = 1.0 if len(quickstarts) > 1 else (float(len(quickstarts)) if quickstarts else 0.0)
    size_kb = float(entry["repo_size_kb"])
    size_norm = min(1.0, size_kb / norms["substantial_repo_kb"])
    fork_norm = min(1.0, fork_ratio / norms["healthy_fork_ratio_ceiling"])
    substance_axis = min(1.0, (size_norm + fork_norm) / (1.0 + 1.0))

    license_axis = 1.0 if permissive else (0.0 if spdx in ("NONE", "NOASSERTION", "") else (1.0 / (1.0 + 1.0)))
    channels_sorted = tuple(sorted(str(c) for c in entry["channels"]))
    corroboration_axis = min(1.0, float(len(channels_sorted)) / norms["corroboration_sources_ceiling"])
    lens_axis = 1.0 if len(curator_lenses) > 1 else (float(len(curator_lenses)) if curator_lenses else 0.0)

    axis_scores = {
        "velocity_momentum": round(velocity_axis, grid.float_round_digits),
        "quickstart_reproducibility": round(quickstart_axis, grid.float_round_digits),
        "code_and_architecture_substance": round(substance_axis, grid.float_round_digits),
        "license_and_reuse_clarity": round(license_axis, grid.float_round_digits),
        "cross_source_corroboration": round(corroboration_axis, grid.float_round_digits),
        "curator_lens_alignment": round(lens_axis, grid.float_round_digits),
    }

    weighted_sum = sum(axis_scores[ax] * weights[ax] for ax in grid.rubric_axes)
    utility_milli = int(round(weighted_sum * scale_milli))
    if bool(entry.get("already_in_seed_archive")):
        utility_milli = min(int(scale_milli), utility_milli + int(norms["archive_enrichment_bonus_milli"]))

    penalty_milli = 0
    if spdx in ("NONE", "NOASSERTION", ""):
        penalty_milli += int(norms["no_license_penalty_milli"])
    if size_kb < norms["min_substance_repo_kb"]:
        penalty_milli += int(norms["empty_or_tiny_repo_penalty_milli"])
    lower_corpus = corpus.lower()
    if any(phrase in lower_corpus for phrase in grid.hype_marker_phrases):
        penalty_milli += int(norms["hype_phrase_penalty_milli"])
    if not quickstarts:
        penalty_milli += int(norms["missing_quickstart_penalty_milli"])

    breakout_milli = max(0, min(int(scale_milli), utility_milli - penalty_milli))
    license_gate_ok = permissive if bool(cell["require_permissive_license"]) else True
    passes_gate = breakout_milli >= int(cell["min_breakout_score_milli"]) and license_gate_ok

    demo_potential = (
        "high_interactive_or_cli_demo"
        if quickstarts and permissive
        else ("moderate_adapter_fixture_only" if permissive else "blocked_pending_license_or_quickstart")
    )

    return VelocitySignalDossier(
        canonical_repo_key=str(entry["canonical_repo_key"]),
        canonical_repo_url=str(entry["canonical_repo_url"]),
        created_at_iso=str(entry["created_at_iso"]),
        age_days=float(entry["age_days"]),
        stars=stars,
        forks=forks,
        stars_per_day=stars_per_day,
        fork_ratio=fork_ratio,
        corroborated_channels=channels_sorted,
        spdx_license=spdx,
        permissive_license=permissive,
        primary_language=str(entry["primary_language"]),
        quickstart_commands=quickstarts,
        runtime_footprints=footprints,
        capability_facet_ids=capability_facets,
        curator_lens_ids=curator_lenses,
        simhash64_hex=str(entry["simhash64_hex"]),
        lsh_bands=tuple(entry["lsh_bands"]),
        already_in_seed_archive=bool(entry.get("already_in_seed_archive")),
        linked_archive_key=str(entry.get("linked_archive_key") or ""),
        axis_scores=axis_scores,
        utility_score_milli=utility_milli,
        hype_penalty_milli=penalty_milli,
        breakout_score_milli=breakout_milli,
        passes_breakout_gate=passes_gate,
        problem_solved=summary_text or "Open-source engineering utility candidate",
        integration_hooks=hooks,
        demo_potential=demo_potential,
    )


def emit_bounded_verb_proposals(
    dossier: VelocitySignalDossier,
    grid: NodeGrid,
    *,
    active_cell: Mapping[str, Any] | None = None,
    parent_task_id: str = "radar_root_seed",
    source_task_id: str = "radar_root_seed",
    generation_depth: int = 0,
) -> list[BoundedVerbProposal]:
    """Emit bounded follow-up verb proposals without automatic enqueue authority."""
    if not dossier.passes_breakout_gate:
        return []
    cell = grid.clamp_cell(active_cell)
    max_proposals = int(cell["max_proposals_per_artifact"])
    next_depth = generation_depth + 1
    slug_clean = re.sub(r"[^a-z0-9]+", "_", dossier.canonical_repo_key.lower()).strip("_")
    digest = hashlib.sha256(f"{parent_task_id}:{dossier.canonical_repo_key}".encode("utf-8")).hexdigest()[: grid.lsh_nibbles_per_band + grid.lsh_nibbles_per_band]
    hints = tuple(sorted(set(
        list(dossier.capability_facet_ids)
        + list(dossier.curator_lens_ids)
        + [dossier.primary_language.lower(), dossier.canonical_repo_key]
    )))

    templates = [
        (
            "verify_quickstart",
            "worker_self_directed",
            grid.high_priority,
            grid.default_complexity_milli,
            f"Verify clean-room quickstart and license receipt for {dossier.canonical_repo_url}",
            f"Execute clean-room quickstart verification for {dossier.canonical_repo_url} ({dossier.spdx_license}), record exact exit codes and runtime footprint across {list(dossier.runtime_footprints)}.",
        ),
        (
            "link_capability_ontology",
            "meta_generator",
            grid.default_priority,
            grid.default_complexity_milli,
            f"Map {dossier.canonical_repo_key} into polyhierarchical capability ontology facets",
            f"Attach {dossier.canonical_repo_key} to polyhierarchical capability facets {list(dossier.capability_facet_ids)} with typed I/O port contract signature and benchmark comparators.",
        ),
        (
            "synthesize_skill_or_mcp_adapter",
            "worker_self_directed",
            grid.default_priority,
            grid.default_complexity_milli,
            f"Author typed adapter contract for {dossier.canonical_repo_key}",
            f"Wrap {dossier.canonical_repo_url} hooks {list(dossier.integration_hooks)} into a zero-side-effect typed tool card and smoke test fixture.",
        ),
        (
            "build_runnable_component_demo",
            "worker_self_directed",
            grid.low_priority,
            grid.demo_complexity_milli,
            f"Build deterministic component demo and walkthrough for {dossier.canonical_repo_key}",
            f"Create a self-contained deterministic demo fixture and storyboard walkthrough demonstrating {dossier.problem_solved}.",
        ),
    ]

    proposals: list[BoundedVerbProposal] = []
    for idx, (pkind, vkind, prio, cmplx, title, prompt) in enumerate(templates[:max_proposals]):
        proposals.append(
            BoundedVerbProposal(
                proposal_id=f"radar_{slug_clean}_{idx}_{digest}",
                proposal_kind=pkind,
                tier="public_general",
                verb_kind=vkind,
                parent_task_id=parent_task_id,
                source_task_id=source_task_id,
                generation_depth=next_depth,
                priority=prio,
                complexity_milli=cmplx,
                target_repo_key=dossier.canonical_repo_key,
                title=title,
                prompt=prompt,
                facet_axes=dossier.capability_facet_ids,
                search_hints=hints,
                auto_enqueue_permitted=False,
            )
        )
    return proposals


def evaluate_radar_bundle(bundle: Mapping[str, Any], grid: NodeGrid | None = None) -> dict[str, Any]:
    """Run deterministic end-to-end radar normalization, anti-hype scoring and bounded proposal generation."""
    active_grid = grid or NodeGrid()
    ledger = GridLedger(active_grid)
    cost_ledger = OperationCostLedger(active_grid, ledger)
    regime = str(bundle.get("radar_regime") or active_grid.param_by_name["radar_regime"].default)
    resolved = cost_ledger.resolve_for_regime(regime)
    active_cell = active_grid.clamp_cell(bundle.get("cell_overrides") or resolved["cell"])

    coalesced_res = normalize_and_coalesce_signals(
        bundle.get("signals", []),
        active_grid,
        reference_utc_iso=str(bundle["reference_utc_iso"]),
        active_cell=active_cell,
        known_archive_repos=bundle.get("known_archive_repos") or {},
    )

    dossiers = [
        score_breakout_dossier(entry, active_grid, active_cell=active_cell)
        for entry in coalesced_res["coalesced"]
    ]
    dossiers.sort(key=lambda d: (-d.breakout_score_milli, d.canonical_repo_key))

    parent_id = str(bundle.get("parent_task_id") or "radar_seed_bundle")
    proposals: list[dict[str, Any]] = []
    for dossier in dossiers:
        for prop in emit_bounded_verb_proposals(
            dossier,
            active_grid,
            active_cell=active_cell,
            parent_task_id=parent_id,
            source_task_id=parent_id,
            generation_depth=int(bundle.get("generation_depth", 0)),
        ):
            proposals.append(prop.to_dict())

    admitted_keys = [d.canonical_repo_key for d in dossiers if d.passes_breakout_gate]
    filtered_hype_keys = [d.canonical_repo_key for d in dossiers if not d.passes_breakout_gate]

    body = {
        "grid_cell_id": active_grid.cell_id(active_cell),
        "radar_regime": regime,
        "allow_authenticated_wall_scraping": active_grid.allow_authenticated_wall_scraping,
        "total_coalesced_repositories": len(dossiers),
        "admitted_breakout_keys": admitted_keys,
        "filtered_hype_or_incomplete_keys": filtered_hype_keys,
        "refused_wall_or_unsanctioned_sources": coalesced_res["refused_sources"],
        "top_breakout_repo_key": admitted_keys[0] if admitted_keys else None,
        "dossiers": [d.to_dict() for d in dossiers],
        "bounded_verb_proposals": proposals,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return body
