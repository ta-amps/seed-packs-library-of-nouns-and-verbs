"""SPDX license ids, legacy aliases, digest bases and honest example labels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_motion.schemas import (
    ACCEPTED_LICENSE_INPUTS,
    ALLOWED_LICENSES,
    AssetAttribution,
    SceneRecipe,
    canonical_sha256,
)
from video_motion.social import default_asset_catalog, load_bundled_recipes

ROOT = Path(__file__).resolve().parents[1]
SPDX = {"CC0-1.0", "CC-BY-4.0", "MIT", "LicenseRef-Video-Motion-Procedural"}


def test_licenses_are_spdx_and_legacy_labels_normalize() -> None:
    assert ALLOWED_LICENSES == SPDX
    for legacy, spdx in (("CC0", "CC0-1.0"), ("PROCEDURAL", "LicenseRef-Video-Motion-Procedural")):
        attribution = AssetAttribution(asset_id="a", license=legacy, creator="c", sha256="a" * 64)
        assert attribution.license == spdx
    for rejected in ("GPL-3.0-only", "UNKNOWN_RIGHTS", "cc0"):
        with pytest.raises(ValidationError):
            AssetAttribution(asset_id="a", license=rejected, creator="c", sha256="a" * 64)
    schema = SceneRecipe.model_json_schema()["$defs"]["AssetAttribution"]["properties"]
    accepted = SPDX | {"CC0", "PROCEDURAL"}
    assert set(schema["license"]["enum"]) == set(ACCEPTED_LICENSE_INPUTS) == accepted
    assert schema["digest_basis"]["default"] == "declared"


def test_examples_and_catalog_state_what_their_digests_cover() -> None:
    for recipe in load_bundled_recipes():
        for attribution in recipe.attributions:
            assert attribution.license in SPDX
            assert attribution.digest_basis == "illustrative"
    for path in sorted((ROOT / "examples").glob("0*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert {a["license"] for a in raw["attributions"]} <= SPDX
    for entry in default_asset_catalog().list_entries():
        assert entry.digest_basis == "procedural_definition"
        definition = entry.model_dump(exclude={"sha256", "digest_basis"})
        assert entry.sha256 == canonical_sha256(definition)


def test_bundled_scenes_make_no_invented_measurement_claims() -> None:
    labels = [entry.label for entry in default_asset_catalog().list_entries()]
    for recipe in load_bundled_recipes():
        labels += [actor.label for actor in recipe.actors]
        labels += [cue.text for cue in recipe.captions]
    assert not [text for text in labels if "%" in text]
    chart = next(r for r in load_bundled_recipes() if r.recipe_id == "02-kinetic-data-chart")
    assert "not measurements" in chart.synopsis
    assert any("not measured" in actor.label for actor in chart.actors if actor.data_points)
