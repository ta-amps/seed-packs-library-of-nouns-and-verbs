"""The noun values and pins these tools write match Tessera's own contracts at a pinned commit.

`uv sync --all-groups` installs Tessera at the commit pinned in pyproject.toml. CI sets
VIDEO_MOTION_REQUIRE_TESSERA=1 so a missing Tessera fails these tests instead of skipping them.
The seed pack's own nouns and verbs are validated against Tessera in the pack library.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
from types import ModuleType
from typing import Any

import pytest

from video_motion.media import MEDIA_ROLE, media_noun_value
from video_motion.nouns import (
    DEFAULT_SEED_STORE,
    KEY_PATTERN,
    NAME_PATTERN,
    SHA256_PATTERN,
    NounPin,
    pin_for,
    value_sha256,
)
from video_motion.sequence import load_bundled_sequence
from video_motion.social import examples_dir
from video_motion.toolcards import ExternalToolCard, tool_noun_value


def _tessera(module: str) -> ModuleType:
    if os.environ.get("VIDEO_MOTION_REQUIRE_TESSERA") == "1":
        return importlib.import_module(module)
    return pytest.importorskip(module, reason="Install the integration group: uv sync --all-groups")


def _written_values() -> list[tuple[str, dict[str, Any]]]:
    """Every noun value these tools write for the bundled demo: media and reference tool cards."""
    _, assets = load_bundled_sequence("hackathon-demo")
    raw = json.loads((examples_dir() / "sequences" / "reference-tools.json").read_text("utf-8"))
    cards = [ExternalToolCard.model_validate(card) for card in raw["cards"]]
    values = [(MEDIA_ROLE, media_noun_value(asset)) for asset in assets]
    values += [("external_tool", tool_noun_value(card)) for card in cards]
    assert len(values) == len(assets) + len(cards) >= 4
    return values


def test_noun_digests_and_pins_match_tessera() -> None:
    receipts = _tessera("tessera.receipts")
    models = _tessera("tessera.models")
    sequence, _ = load_bundled_sequence("hackathon-demo")
    samples: list[Any] = [value for _, value in _written_values()]
    samples += [sequence.model_dump(mode="json"), {"n": 1.0}, {"n": 10**16}, {"n": 2**53}]
    for sample in samples:
        expected = hashlib.sha256(receipts.canonical_json(sample).encode()).hexdigest()
        assert value_sha256(sample) == expected
    # NounPin uses Tessera's store and record-key patterns, so every pin names a writable record.
    assert NAME_PATTERN == models.NAME_PATTERN
    key_pattern = models.RecordWrite.model_json_schema()["properties"]["key"]["pattern"]
    assert key_pattern == KEY_PATTERN
    for element in sequence.media_elements():
        pin = element.media
        assert isinstance(pin, NounPin)
        assert re.fullmatch(NAME_PATTERN, pin.store) and re.fullmatch(KEY_PATTERN, pin.key)
        assert re.fullmatch(SHA256_PATTERN, pin.value_sha256) and pin.version == 1


def test_written_noun_values_pass_tessera_record_and_category_checks() -> None:
    tessera = _tessera("tessera")
    ontology = _tessera("tessera.ontology")
    for role, value in _written_values():
        pin = pin_for(role, value)
        category = value["category_id"]
        tags = [f"category:{category}", f"pack:{value['pack']}", "status:quarantined"]
        record = {
            "namespace": "conformance-seeds",
            "visibility_scope": "private",
            "allowed_surfaces": [],
            "target_cohorts": ["all"],
            "store": DEFAULT_SEED_STORE,
            "key": pin.key,
            "expected_version": 0,
            "value": value,
            "tags": tags,
        }
        tessera.RecordWrite.model_validate(record)
        assert ontology.get_category_spec(category).kind == "noun"
        result = ontology.validate_category_payload(
            category, value["dimensions"], value["relations"], tags
        )
        assert result.valid and not result.warnings, (role, result.errors)
