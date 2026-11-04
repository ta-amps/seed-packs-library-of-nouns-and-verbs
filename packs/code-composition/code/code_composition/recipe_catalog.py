"""Authored recipe catalog and made-up sample inputs, shared by checkouts and installed wheels.

The canonical JSON files live in `examples/recipes/`. The wheel ships the same files as package
data at `code_composition/recipes/` (see `[tool.hatch.build.targets.wheel.force-include]`), so an
installed package and a source checkout load identical recipes. A missing or empty catalog is an
error; there is no substitute recipe.
"""

from __future__ import annotations

import copy
import json
import tomllib
from pathlib import Path
from typing import Any

from code_composition.errors import RecipeCatalogError
from code_composition.schemas import RecipeSpec

# The distribution name in pyproject.toml; it marks the source tree that holds this package.
DISTRIBUTION = "code-composition"
PACKAGED_RECIPES_DIR = "recipes"
CHECKOUT_RECIPES_DIR = ("examples", "recipes")

_INCIDENT_NOTES = (
    "  [INC-101] gateway: Minor cache warm-up completed\n\n"
    "  [INC-102] payments: Critical timeout spike during checkout\n"
    "  [INC-102] payments: Critical timeout and degraded upstream outage\n"
    "  [INC-103] auth: Token refresh healthy\n"
    "  [INC-104] storage: Emergency rollback after critical latency timeout\n"
)
_AB_CASES = (
    "case_id,cohort,errors,requests,latency_ms,label\n"
    "c01,enterprise,18,100,420,1\n"
    "c02,enterprise,1,120,45,0\n"
    "c03,growth,22,90,510,1\n"
    "c04,growth,2,150,55,0\n"
    "c05,enterprise,15,80,390,1\n"
    "c06,starter,0,200,38,0\n"
    "c07,starter,19,85,460,1\n"
    "c08,growth,1,140,49,0\n"
    "c09,enterprise,25,95,530,1\n"
    "c10,starter,2,180,42,0\n"
    "c11,enterprise,12,100,480,1\n"
    "c12,growth,0,160,41,0\n"
)
_TRIAGE_INPUTS: dict[str, Any] = {
    "ingest_events.raw_csv": (
        "event_id,service,errors,requests,latency_ms\n"
        "ev1,checkout,1,200,48\n"
        "ev1,checkout,1,200,48\n"
        "ev2,checkout,2,210,52\n"
        "ev3,search,0,300,39\n"
        "ev4,checkout,28,120,490\n"
        "ev5,billing,,150,44\n"
        "ev6,billing,24,100,520\n"
    ),
    "ingest_owners.raw_csv": (
        "service,team\ncheckout,commerce-core\nsearch,discovery\nbilling,ledger-ops\n"
    ),
}
_SAMPLE_INPUTS: dict[str, dict[str, Any]] = {
    "document-signal-digest": {"raw_text": _INCIDENT_NOTES},
    "ab-candidate-selection": {"raw_csv": _AB_CASES},
    "ab-candidate-selection-v2": {"raw_csv": _AB_CASES},
    "tabular-anomaly-triage": _TRIAGE_INPUTS,
}


def is_source_checkout(root: Path) -> bool:
    """True only for the source tree that contains this package, never an unrelated parent."""
    try:
        meta = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    project = meta.get("project")
    return isinstance(project, dict) and project.get("name") == DISTRIBUTION


def recipes_dir() -> Path:
    """Locate the authored recipes: wheel package data first, then the source checkout."""
    package_dir = Path(__file__).resolve().parent
    packaged = package_dir / PACKAGED_RECIPES_DIR
    if packaged.is_dir():
        return packaged
    root = package_dir.parent
    checkout = root.joinpath(*CHECKOUT_RECIPES_DIR)
    if checkout.is_dir() and is_source_checkout(root):
        return checkout
    raise RecipeCatalogError(
        "Authored recipes were not found as package data (code_composition/recipes) or in a "
        "source checkout (examples/recipes). Reinstall the package; no substitute recipe is used."
    )


def load_catalog_recipes(directory: Path | None = None) -> list[tuple[str, RecipeSpec]]:
    """Load every authored RecipeSpec with its repository path (`examples/recipes/<file>`).

    The path names the canonical source file in the repository, so a wheel and a checkout
    report the same provenance even though the wheel stores the file under
    `code_composition/recipes/`.
    """
    folder = directory if directory is not None else recipes_dir()
    if not folder.is_dir():
        raise RecipeCatalogError(f"Recipe directory {folder.name!r} does not exist.")
    paths = sorted(folder.glob("*.json"))
    if not paths:
        raise RecipeCatalogError(f"Recipe directory {folder.name!r} contains no recipe JSON.")
    prefix = "/".join(CHECKOUT_RECIPES_DIR)
    return [
        (
            f"{prefix}/{path.name}",
            RecipeSpec.model_validate(json.loads(path.read_text(encoding="utf-8"))),
        )
        for path in paths
    ]


def load_example_recipes(directory: Path | None = None) -> list[RecipeSpec]:
    """Load and validate every authored RecipeSpec JSON file, sorted by file name."""
    return [recipe for _path, recipe in load_catalog_recipes(directory)]


def has_sample_inputs(recipe_id: str) -> bool:
    """True when the catalog defines made-up sample inputs for this recipe identifier."""
    return recipe_id in _SAMPLE_INPUTS


def sample_inputs_for_recipe(recipe_id: str) -> dict[str, Any]:
    """Deterministic made-up inputs for the reference recipes.

    Unknown identifiers keep the historical tabular triage default used by the demo surfaces.
    Seed export checks `has_sample_inputs` and refuses a recipe without its own inputs.
    """
    return copy.deepcopy(_SAMPLE_INPUTS.get(recipe_id, _TRIAGE_INPUTS))
