"""Dual-aspect social video deliverable compiler and license-gated SceneFactory."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from video_motion.captions import export_srt, export_webvtt
from video_motion.errors import (
    BundledDataMissingError,
    ContributorTierRefusedError,
    QAGateFailureError,
    RecipeNotFoundError,
    UnlicensedAssetError,
)
from video_motion.motion import retarget_motion
from video_motion.qa import audit_recipe
from video_motion.schemas import (
    ALLOWED_LICENSES,
    ASPECT_PROFILES,
    SHA256_RE,
    ActorKind,
    AspectDeliverable,
    AspectId,
    AssetAttribution,
    BeatProportion,
    CaptionAnchor,
    CastMember,
    CompiledDeliverable,
    DigestBasis,
    LearnedTrajectory,
    MotionObservationTrace,
    MotionProfile,
    PostingKitManifest,
    QAReport,
    SceneRecipe,
    TrajectoryWaypoint,
    canonical_sha256,
    spdx_license,
)
from video_motion.timeline import (
    evaluate_frame,
    render_contact_sheet_svg,
    render_svg_frame,
    sample_frame_indices,
)


def enforce_standard_model(model_id: str | None) -> None:
    """Refuse contributor-tier ('-contributor') model IDs deterministically."""
    if model_id and "-contributor" in model_id.lower():
        raise ContributorTierRefusedError(model_id)


class CatalogAssetRecord(BaseModel):
    """Registered visual or audio asset entry inside a license-gated AssetCatalog."""

    model_config = ConfigDict(extra="forbid", strict=True)

    asset_id: str = Field(min_length=1)
    kind: ActorKind | str
    label: str = Field(min_length=1)
    license: str
    creator: str
    source_uri: str = "urn:video-motion:procedural"
    sha256: str
    fill_hex: str = "#1e293b"
    accent_hex: str = "#38bdf8"
    digest_basis: DigestBasis = "declared"


class ConceptRoleSpec(BaseModel):
    """Single role/element request inside a ConceptBrief."""

    model_config = ConfigDict(extra="forbid", strict=True)

    actor_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    role_label: str = ""
    spoken_line: str = Field(min_length=1)
    data_points: list[float] = Field(default_factory=list)


class ConceptBrief(BaseModel):
    """Structured social skit, kinetic chart, or simulation concept brief for SceneFactory."""

    model_config = ConfigDict(extra="forbid", strict=True)

    brief_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    synopsis: str = ""
    duration_s: float = Field(default=16.0, gt=1.0, le=180.0)
    fps: int = Field(default=30, ge=12, le=120)
    seed: int = 42
    roles: list[ConceptRoleSpec] = Field(min_length=1)


class ConceptAdapter(Protocol):
    """Optional external LLM or heuristic concept-refinement adapter."""

    model_id: str

    def refine_lines(self, brief: ConceptBrief) -> list[str]: ...


class AssetCatalog:
    """License-gated asset registry enforcing open licensing and creator attribution."""

    def __init__(self, entries: Sequence[CatalogAssetRecord] = ()) -> None:
        self._entries: dict[str, CatalogAssetRecord] = {e.asset_id: e for e in entries}

    def register(self, entry: CatalogAssetRecord) -> None:
        self._entries[entry.asset_id] = entry

    def list_entries(self) -> list[CatalogAssetRecord]:
        return [self._entries[k] for k in sorted(self._entries)]

    def resolve_verified(self, asset_id: str) -> tuple[CatalogAssetRecord, AssetAttribution]:
        entry = self._entries.get(asset_id)
        if entry is None:
            raise UnlicensedAssetError(asset_id, "asset_id is not registered in AssetCatalog.")
        typed_license = spdx_license(entry.license)
        if typed_license is None:
            raise UnlicensedAssetError(
                asset_id,
                f"license {entry.license!r} is not in allowlisted open licenses {sorted(ALLOWED_LICENSES)}.",
            )
        if not entry.creator.strip():
            raise UnlicensedAssetError(asset_id, "creator attribution is empty.")
        if not SHA256_RE.fullmatch(entry.sha256.lower()):
            raise UnlicensedAssetError(asset_id, "sha256 content digest is missing or malformed.")

        attribution = AssetAttribution(
            asset_id=entry.asset_id,
            license=typed_license,
            creator=entry.creator,
            source_uri=entry.source_uri,
            sha256=entry.sha256.lower(),
            digest_basis=entry.digest_basis,
        )
        return entry.model_copy(update={"license": typed_license}), attribution


def default_asset_catalog() -> AssetCatalog:
    """Create the default made-up catalog of procedural vector asset definitions.

    These assets are drawn by this package's own SVG renderer; there are no media files. Each `sha256`
    therefore covers the canonical definition (`digest_basis="procedural_definition"`), not media
    bytes, and the creator names are made-up example labels rather than verified rights holders.
    """
    specs: list[tuple[str, ActorKind, str, str, str, str, str]] = [
        (
            "char-sre-lead",
            "character",
            "On-Call Engineer",
            "LicenseRef-Video-Motion-Procedural",
            "video-motion vector studio",
            "#172554",
            "#38bdf8",
        ),
        (
            "char-deploy-bot",
            "character",
            "Deploy Bot",
            "CC0-1.0",
            "video-motion open rig pack",
            "#1e1b4b",
            "#a78bfa",
        ),
        (
            "chart-latency-bars",
            "chart",
            "Frame Seek Latency (ms)",
            "CC-BY-4.0",
            "video-motion data graphics",
            "#0f172a",
            "#34d399",
        ),
        (
            "card-metric-callout",
            "card",
            "Frame Hash Callout",
            "MIT",
            "video-motion UI primitives",
            "#111827",
            "#fbbf24",
        ),
        (
            "mech-wallclock-lane",
            "mechanism",
            "Wall-Clock Recorder",
            "LicenseRef-Video-Motion-Procedural",
            "video-motion mechanism kit",
            "#27151d",
            "#fb7185",
        ),
        (
            "mech-frameseek-lane",
            "mechanism",
            "Deterministic Seek(f)",
            "LicenseRef-Video-Motion-Procedural",
            "video-motion mechanism kit",
            "#0f2922",
            "#2dd4bf",
        ),
    ]
    records = []
    for aid, kind, label, lic, creator, fill, accent in specs:
        definition = {
            "asset_id": aid,
            "kind": kind,
            "label": label,
            "license": lic,
            "creator": creator,
            "source_uri": f"urn:video-motion:catalog:{aid}",
            "fill_hex": fill,
            "accent_hex": accent,
        }
        records.append(
            CatalogAssetRecord(
                **definition,
                sha256=canonical_sha256(definition),
                digest_basis="procedural_definition",
            )
        )
    return AssetCatalog(records)


def default_motion_profiles() -> list[MotionProfile]:
    """Built-in parametric motion formulas used by SceneFactory candidate ranking."""
    snappy_beats = [
        BeatProportion(
            phase="hook",
            start_ratio=0.0,
            end_ratio=0.04,
            mean_energy=0.88,
            dominant_easing="spring_pop",
            fit_rmse=0.01,
        ),
        BeatProportion(
            phase="orientation",
            start_ratio=0.04,
            end_ratio=0.13,
            mean_energy=0.58,
            dominant_easing="ease_out_cubic",
            fit_rmse=0.01,
        ),
        BeatProportion(
            phase="setup",
            start_ratio=0.13,
            end_ratio=0.38,
            mean_energy=0.45,
            dominant_easing="ease_in_out_cubic",
            fit_rmse=0.01,
        ),
        BeatProportion(
            phase="escalation",
            start_ratio=0.38,
            end_ratio=0.69,
            mean_energy=0.76,
            dominant_easing="ease_in_out_cubic",
            fit_rmse=0.01,
        ),
        BeatProportion(
            phase="punchline",
            start_ratio=0.69,
            end_ratio=0.92,
            mean_energy=0.92,
            dominant_easing="spring_pop",
            fit_rmse=0.01,
        ),
        BeatProportion(
            phase="hold",
            start_ratio=0.92,
            end_ratio=1.0,
            mean_energy=0.12,
            dominant_easing="step_hold",
            fit_rmse=0.0,
        ),
    ]
    waypoints = [
        TrajectoryWaypoint(ratio=0.0, norm_x=0.22, norm_y=0.38, scale=0.92, easing="spring_pop"),
        TrajectoryWaypoint(
            ratio=0.04, norm_x=0.35, norm_y=0.34, scale=1.02, easing="ease_out_cubic"
        ),
        TrajectoryWaypoint(
            ratio=0.13, norm_x=0.42, norm_y=0.36, scale=1.0, easing="ease_in_out_cubic"
        ),
        TrajectoryWaypoint(
            ratio=0.38, norm_x=0.52, norm_y=0.40, scale=1.04, easing="ease_in_out_cubic"
        ),
        TrajectoryWaypoint(ratio=0.69, norm_x=0.48, norm_y=0.32, scale=1.08, easing="spring_pop"),
        TrajectoryWaypoint(ratio=0.92, norm_x=0.48, norm_y=0.32, scale=1.05, easing="step_hold"),
        TrajectoryWaypoint(ratio=1.0, norm_x=0.48, norm_y=0.32, scale=1.05, easing="step_hold"),
    ]
    traj = [LearnedTrajectory(role_slot="lead", waypoints=waypoints)]
    p1_sha = canonical_sha256(
        {"id": "prof-snappy-skit", "beats": [b.model_dump() for b in snappy_beats]}
    )
    p2_sha = canonical_sha256(
        {"id": "prof-measured-explainer", "beats": [b.model_dump() for b in snappy_beats]}
    )
    return [
        MotionProfile(
            profile_id="prof-snappy-skit",
            title="Snappy POV Skit Formula",
            source_trace_id="builtin-snappy",
            reference_duration_s=16.0,
            median_cut_cadence_s=2.4,
            mean_motion_intensity=0.64,
            dominant_easing="spring_pop",
            beat_proportions=snappy_beats,
            trajectories=traj,
            profile_sha256=p1_sha,
        ),
        MotionProfile(
            profile_id="prof-measured-explainer",
            title="Measured Technical Explainer Formula",
            source_trace_id="builtin-explainer",
            reference_duration_s=16.0,
            median_cut_cadence_s=3.1,
            mean_motion_intensity=0.49,
            dominant_easing="ease_out_cubic",
            beat_proportions=[
                bp.model_copy(
                    update={
                        "dominant_easing": "ease_out_cubic" if bp.phase != "hold" else "step_hold"
                    }
                )
                for bp in snappy_beats
            ],
            trajectories=traj,
            profile_sha256=p2_sha,
        ),
    ]


class SceneFactory:
    """Casts structured concepts strictly from a license-gated AssetCatalog and ranks by QA scorecards."""

    def __init__(
        self,
        catalog: AssetCatalog | None = None,
        adapter: ConceptAdapter | None = None,
    ) -> None:
        self.catalog = catalog if catalog is not None else default_asset_catalog()
        self.adapter = adapter

    def cast_and_rank(
        self,
        brief: ConceptBrief,
        candidate_profiles: Sequence[MotionProfile] | None = None,
        *,
        model_id: str | None = None,
    ) -> tuple[SceneRecipe, list[tuple[SceneRecipe, QAReport]]]:
        """Cast verified open-licensed assets, score candidate drafts by QA, and return the best recipe."""
        enforce_standard_model(model_id)
        if self.adapter is not None:
            enforce_standard_model(self.adapter.model_id)
            refined_lines = self.adapter.refine_lines(brief)
        else:
            refined_lines = [r.spoken_line for r in brief.roles]

        cast_members: list[CastMember] = []
        for idx, role in enumerate(brief.roles):
            entry, attribution = self.catalog.resolve_verified(role.asset_id)
            actor_kind: ActorKind
            if entry.kind == "character":
                actor_kind = "character"
            elif entry.kind == "chart":
                actor_kind = "chart"
            elif entry.kind == "mechanism":
                actor_kind = "mechanism"
            elif entry.kind == "background":
                actor_kind = "background"
            else:
                actor_kind = "card"
            line = refined_lines[idx] if idx < len(refined_lines) else role.spoken_line
            cast_members.append(
                CastMember(
                    actor_id=role.actor_id,
                    kind=actor_kind,
                    label=entry.label,
                    asset_id=entry.asset_id,
                    attribution=attribution,
                    role_label=role.role_label or entry.label.upper(),
                    line_text=line,
                    fill_hex=entry.fill_hex,
                    accent_hex=entry.accent_hex,
                    is_subject_focus=(actor_kind == "character"),
                    data_points=list(role.data_points),
                )
            )

        profiles = list(candidate_profiles) if candidate_profiles else default_motion_profiles()
        anchor_variants: tuple[CaptionAnchor, ...] = ("lower_third", "reclaimed_lower_right")

        scored: list[tuple[SceneRecipe, QAReport]] = []
        for prof in profiles:
            for anchor in anchor_variants:
                draft = retarget_motion(
                    prof,
                    cast_members,
                    duration_s=brief.duration_s,
                    fps=brief.fps,
                    title=brief.title,
                    recipe_id=f"{brief.brief_id}-{prof.profile_id}-{anchor}",
                    seed=brief.seed,
                )
                draft = draft.model_copy(
                    update={
                        "synopsis": brief.synopsis or draft.synopsis,
                        "captions": [
                            c.model_copy(update={"anchor": anchor}) for c in draft.captions
                        ],
                    }
                )
                report = audit_recipe(draft, aspects=("reels_9x16", "feed_4x5"))
                scored.append((draft, report))

        scored.sort(
            key=lambda item: (
                item[1].passed,
                item[1].score,
                -len(item[1].findings),
                item[0].recipe_id,
            ),
            reverse=True,
        )
        return scored[0][0], scored


def _adapt_recipe_for_aspect(recipe: SceneRecipe, aspect: AspectId) -> SceneRecipe:
    """Adapt caption anchors so reclaimed_lower_right maps cleanly on 9:16 Reels.

    Only 9:16 has a right-rail button column; 4:5 and 16:9 keep the lower-right placement.
    """
    if aspect != "reels_9x16":
        return recipe
    adapted_captions = [
        cue.model_copy(update={"anchor": "lower_third"})
        if cue.anchor == "reclaimed_lower_right" and aspect not in cue.box_override
        else cue
        for cue in recipe.captions
    ]
    return recipe.model_copy(update={"captions": adapted_captions})


def compile_deliverable(
    recipe: SceneRecipe,
    aspects: Sequence[AspectId] = ("reels_9x16", "feed_4x5"),
    *,
    sample_count: int = 6,
    require_qa_pass: bool = True,
) -> CompiledDeliverable:
    """Compile layout-adapted 9:16 + 4:5 SVGs, SRT/WebVTT captions, QA receipt, and post.json manifest."""
    aspect_list: list[AspectId] = (
        list(dict.fromkeys(aspects)) if aspects else ["reels_9x16", "feed_4x5"]
    )

    # Audit each aspect after dual-aspect layout adaptation
    per_aspect_reports: list[QAReport] = []
    aspect_deliverables: dict[AspectId, AspectDeliverable] = {}
    aspect_digests: dict[str, str] = {}

    for aspect in aspect_list:
        adapted = _adapt_recipe_for_aspect(recipe, aspect)
        sub_report = audit_recipe(adapted, aspects=(aspect,))
        per_aspect_reports.append(sub_report)

        profile = ASPECT_PROFILES[aspect]
        cover_state = evaluate_frame(adapted, adapted.cover_frame_index, aspect=aspect)
        cover_svg = render_svg_frame(cover_state, show_safe_zones=False)
        sheet_svg = render_contact_sheet_svg(
            adapted,
            sample_count=sample_count,
            aspect=aspect,
            show_safe_zones=True,
        )
        indices = sample_frame_indices(adapted.total_frames, sample_count=sample_count)
        hashes = {
            str(idx): evaluate_frame(adapted, idx, aspect=aspect).frame_hash_sha256
            for idx in indices
        }
        aspect_deliverables[aspect] = AspectDeliverable(
            aspect=aspect,
            width=profile.width,
            height=profile.height,
            total_frames=adapted.total_frames,
            cover_svg=cover_svg,
            contact_sheet_svg=sheet_svg,
            sample_frame_hashes=hashes,
        )
        aspect_digests[aspect] = canonical_sha256(
            {
                "cover_sha256": canonical_sha256(cover_svg),
                "sheet_sha256": canonical_sha256(sheet_svg),
                "sample_frame_hashes": hashes,
            }
        )

    # Combine QA reports across compiled aspects
    combined_findings = [f for rep in per_aspect_reports for f in rep.findings]
    total_frames_audited = sum(rep.frames_audited for rep in per_aspect_reports)
    merged_checks = (
        per_aspect_reports[0].checks
        if len(per_aspect_reports) == 1
        else [
            c.model_copy(
                update={
                    "error_count": sum(
                        next(sc.error_count for sc in r.checks if sc.check == c.check)
                        for r in per_aspect_reports
                    ),
                    "warning_count": sum(
                        next(sc.warning_count for sc in r.checks if sc.check == c.check)
                        for r in per_aspect_reports
                    ),
                    "passed": all(
                        next(sc.passed for sc in r.checks if sc.check == c.check)
                        for r in per_aspect_reports
                    ),
                }
            )
            for c in per_aspect_reports[0].checks
        ]
    )
    total_errs = sum(c.error_count for c in merged_checks)
    total_warns = sum(c.warning_count for c in merged_checks)
    merged_score = round(max(0.0, 100.0 - 15.0 * total_errs - 3.0 * total_warns), 2)
    credit_line = per_aspect_reports[0].attribution_credit_line
    qa_sha = canonical_sha256(
        {
            "recipe_id": recipe.recipe_id,
            "aspects_checked": aspect_list,
            "frames_audited": total_frames_audited,
            "passed": total_errs == 0,
            "score": merged_score,
            "checks": [c.model_dump() for c in merged_checks],
            "findings": [f.model_dump() for f in combined_findings],
            "attribution_credit_line": credit_line,
        }
    )
    qa_report = QAReport(
        recipe_id=recipe.recipe_id,
        aspects_checked=aspect_list,
        frames_audited=total_frames_audited,
        passed=(total_errs == 0),
        score=merged_score,
        checks=merged_checks,
        findings=combined_findings,
        attribution_credit_line=credit_line,
        qa_receipt_sha256=qa_sha,
    )
    if require_qa_pass and not qa_report.passed:
        raise QAGateFailureError(recipe.recipe_id, total_errs, qa_report.qa_receipt_sha256)

    srt_text = export_srt(recipe)
    vtt_text = export_webvtt(recipe, aspect=aspect_list[0])
    srt_sha = canonical_sha256(srt_text)
    vtt_sha = canonical_sha256(vtt_text)
    actor_labels = ", ".join(a.label for a in recipe.actors if a.label) or recipe.title
    alt_text = f"{recipe.title}: animated scene featuring {actor_labels} ({recipe.duration_s:.1f}s @ {recipe.fps}fps)."

    manifest_core = {
        "recipe_id": recipe.recipe_id,
        "title": recipe.title,
        "synopsis": recipe.synopsis,
        "cover_frame_index": recipe.cover_frame_index,
        "alt_text": alt_text,
        "attribution_credit_line": credit_line,
        "srt_sha256": srt_sha,
        "webvtt_sha256": vtt_sha,
        "qa_receipt_sha256": qa_report.qa_receipt_sha256,
        "aspect_manifests": aspect_digests,
    }
    bundle_sha = canonical_sha256(manifest_core)
    post_manifest = PostingKitManifest(
        recipe_id=recipe.recipe_id,
        title=recipe.title,
        synopsis=recipe.synopsis,
        cover_frame_index=recipe.cover_frame_index,
        alt_text=alt_text,
        attribution_credit_line=credit_line,
        srt_sha256=srt_sha,
        webvtt_sha256=vtt_sha,
        qa_receipt_sha256=qa_report.qa_receipt_sha256,
        aspect_manifests=aspect_digests,
        bundle_sha256=bundle_sha,
    )

    return CompiledDeliverable(
        recipe_id=recipe.recipe_id,
        aspects=aspect_deliverables,
        srt=srt_text,
        webvtt=vtt_text,
        post_manifest=post_manifest,
        qa_report=qa_report,
    )


def write_deliverable_bundle(deliverable: CompiledDeliverable, out_dir: Path) -> dict[str, Path]:
    """Write dual-aspect SVG frames, contact sheets, SRT/WebVTT captions, QA report, and post.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    srt_path = out_dir / "captions.srt"
    srt_path.write_text(deliverable.srt, encoding="utf-8")
    written["srt"] = srt_path

    vtt_path = out_dir / "captions.vtt"
    vtt_path.write_text(deliverable.webvtt, encoding="utf-8")
    written["webvtt"] = vtt_path

    qa_path = out_dir / "qa_report.json"
    qa_path.write_text(
        json.dumps(deliverable.qa_report.model_dump(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written["qa_report"] = qa_path

    post_path = out_dir / "post.json"
    post_path.write_text(
        json.dumps(deliverable.post_manifest.model_dump(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written["post_json"] = post_path

    for aspect_id, item in deliverable.aspects.items():
        aspect_dir = out_dir / aspect_id
        aspect_dir.mkdir(parents=True, exist_ok=True)
        cover_path = aspect_dir / "cover.svg"
        cover_path.write_text(item.cover_svg, encoding="utf-8")
        sheet_path = aspect_dir / "contact_sheet.svg"
        sheet_path.write_text(item.contact_sheet_svg, encoding="utf-8")
        written[f"{aspect_id}_cover"] = cover_path
        written[f"{aspect_id}_contact_sheet"] = sheet_path

    return written


def examples_dir() -> Path:
    """Return the bundled examples folder.

    A wheel ships them as package data in `video_motion/examples`; a source checkout or editable install
    reads the repository's `examples/` folder next to the package.
    """
    package_dir = Path(__file__).resolve().parent
    packaged = package_dir / "examples"
    return packaged if packaged.is_dir() else package_dir.parent / "examples"


def load_bundled_recipes() -> list[SceneRecipe]:
    """Load and validate the bundled example SceneRecipe JSON files; fail if there are none."""
    folder = examples_dir()
    paths = sorted(folder.glob("[0-9][0-9]-*.json"))
    if not paths:
        raise BundledDataMissingError(
            f"No bundled scene recipes found in {folder.name}/; the installation is incomplete."
        )
    return [
        SceneRecipe.model_validate(json.loads(path.read_text(encoding="utf-8"))) for path in paths
    ]


def get_bundled_recipe(recipe_id: str) -> SceneRecipe:
    """Look up one bundled SceneRecipe by recipe_id or raise RecipeNotFoundError."""
    for recipe in load_bundled_recipes():
        if recipe.recipe_id == recipe_id:
            return recipe
    raise RecipeNotFoundError(recipe_id)


def load_sample_motion_trace() -> MotionObservationTrace:
    """Load and validate examples/sample-motion-trace.json."""
    path = examples_dir() / "sample-motion-trace.json"
    if not path.is_file():
        raise BundledDataMissingError(
            "The bundled sample-motion-trace.json is missing; the installation is incomplete."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return MotionObservationTrace.model_validate(payload)
