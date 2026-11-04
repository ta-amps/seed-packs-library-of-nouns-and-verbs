"""Offline candidate nouns and worker seeds using Tessera's existing request shapes.

Export checks the packaged node catalog, the compiler/runtime modules and the authored recipes,
then returns create-only `RecordWrite` and `TaskSpec` payloads. It performs no network,
subprocess, model, enqueue or activation work. It never executes code that exists only in a
node database: self-tests run only for nodes identical to the packaged catalog, and other stored
nodes are exported as unexecuted candidates.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from code_composition import __version__
from code_composition.compiler import DeterministicCompiler
from code_composition.errors import SeedPackError
from code_composition.recipe_catalog import (
    has_sample_inputs,
    is_source_checkout,
    load_catalog_recipes,
    sample_inputs_for_recipe,
)
from code_composition.registry import (
    NodeDatabase,
    load_node_callable,
    run_node_self_test_case,
    verify_node_self_tests,
)
from code_composition.schemas import (
    ALLOWED_SPDX_LICENSES,
    CompiledPlan,
    PrewrittenNode,
    RecipeSpec,
    canonical_json,
    compute_code_sha256,
)
from code_composition.seed_nodes import build_seed_nodes

PACK_FORMAT = "code-composition.seed-pack.preview.v2"
TASK_CONTRACT = "code-composition.compile-dag-seed.v1"
DIMENSION_METHOD = "code-composition.seed-dimensions.v1"
REPOSITORY = "https://github.com/ta-amps/seed-packs-library-of-nouns-and-verbs"
# Where this source tree sits inside REPOSITORY. Provenance source paths are relative to it, and
# a checkout commit is read only when the tree sits exactly here.
REPOSITORY_PATH = "packs/code-composition/code"
PACKAGE = "code_composition"
PACKAGE_SPDX_LICENSE = "MIT"
RUNTIME_MODULES = (
    "compiler.py",
    "errors.py",
    "public_limits.py",
    "registry.py",
    "runtime.py",
    "schemas.py",
)
RUNTIME_ENTRYPOINTS = (
    "code_composition.compiler.DeterministicCompiler.compile",
    "code_composition.compiler.DeterministicCompiler.emit_python_from_plan",
    "code_composition.runtime.DeterministicRuntime.execute",
)
_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")
_COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")

TOOL_DIMENSION_BASIS = {
    "determinism": "Fraction of built-in test cases whose outputs were byte-identical in two runs during export; 0 when stored code was not executed.",
    "evidence_grounding": "Fraction of built-in test cases that assert exact output values (all executed cases passed); 0 when not executed.",
    "token_efficiency": "1 - typed signature length / normalized source length: what a composer reads instead of the code.",
    "safety_compliance": "Fraction of governance checks passed: source digest, status:verified, not quarantined, allowed SPDX license.",
}
RUNTIME_DIMENSION_BASIS = {
    "determinism": "Fraction of bundled recipes whose two compilations produced the same plan digest during export.",
    "evidence_grounding": "Fraction of pinned modules hashed from the files of the imported package.",
    "token_efficiency": "1 - total recipe JSON length / total emitted Python length over the bundled recipes.",
    "safety_compliance": "Fraction of recipe steps compiled after passing the governance lens during export.",
}
RECIPE_DIMENSION_BASIS = {
    "determinism": "1 when two compilations of this recipe produced the same plan digest during export.",
    "evidence_grounding": "Fraction of required graph entry inputs supplied by the bundled made-up sample inputs.",
    "token_efficiency": "1 - recipe JSON length / emitted standalone Python length.",
    "safety_compliance": "Fraction of recipe steps whose nodes passed the governance lens at compile time.",
}
PACK_DIMENSION_BASIS = {
    "determinism": "Minimum determinism of the indexed nouns.",
    "evidence_grounding": "Mean evidence_grounding of the indexed nouns.",
    "token_efficiency": "1 - catalog signature length / raw node source length.",
    "safety_compliance": "Minimum safety_compliance of the indexed nouns.",
}


def canonical_value(value: Any) -> Any:
    """Normalize whole floats before export, matching Tessera's JSON value hashing."""
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) >= 2**53:
        try:
            as_float = float(value)
        except OverflowError as exc:
            raise ValueError("JSON integers must fit IEEE-754") from exc
        if int(as_float) != value:
            raise ValueError("JSON integers must round-trip exactly through IEEE-754")
        return as_float if abs(value) >= 10**16 else value
    if isinstance(value, float) and value.is_integer() and abs(value) < 10**16:
        return int(value)
    if isinstance(value, dict):
        return {key: canonical_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [canonical_value(item) for item in value]
    return value


def value_sha256(value: Any) -> str:
    """SHA-256 of Tessera's canonical JSON for a record value: its `value_sha256` pin."""
    encoded = json.dumps(
        canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def noun_ref(store: str, key: str, value: Any) -> dict[str, Any]:
    """A version-1 pin shaped exactly like Tessera's NounRef (store, key, version, digest)."""
    return {"store": store, "key": key, "version": 1, "value_sha256": value_sha256(value)}


def node_body(node: PrewrittenNode) -> dict[str, Any]:
    """Comparable node definition: everything except the local database revision counter."""
    body: dict[str, Any] = canonical_value(node.model_dump(mode="json", exclude={"revision"}))
    return body


def runtime_module_digests() -> dict[str, str]:
    """SHA-256 of the compiler/runtime modules actually imported (CRLF normalized to LF)."""
    package = resources.files(PACKAGE)
    digests: dict[str, str] = {}
    for name in RUNTIME_MODULES:
        try:
            data = package.joinpath(name).read_bytes()
        except OSError as exc:
            raise SeedPackError(
                f"Cannot read runtime module {PACKAGE}/{name} to pin its digest: {exc}",
                code="seed_runtime_unreadable",
            ) from exc
        digests[f"{PACKAGE}/{name}"] = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
    return digests


def _git_dir(root: Path) -> Path | None:
    dot_git = root / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        text = dot_git.read_text(encoding="utf-8").strip()
        if text.startswith("gitdir:"):
            target = Path(text[len("gitdir:") :].strip())
            return target if target.is_absolute() else (root / target).resolve()
    return None


def _resolve_ref(git_dir: Path, ref: str, depth: int = 0) -> str | None:
    """Read a branch ref from loose or packed refs, including linked worktrees."""
    common = git_dir
    marker = git_dir / "commondir"
    if marker.is_file():
        rel = Path(marker.read_text(encoding="utf-8").strip())
        common = rel if rel.is_absolute() else (git_dir / rel).resolve()
    for base in (git_dir, common):
        loose = base / ref
        if loose.is_file():
            text = loose.read_text(encoding="utf-8").strip()
            if text.startswith("ref:"):
                return _resolve_ref(git_dir, text[4:].strip(), depth + 1) if depth < 4 else None
            return text
    packed = common / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            sha, _, name = line.partition(" ")
            if line[:1] not in {"", "#", "^"} and name.strip() == ref:
                return sha
    return None


def checkout_commit() -> str | None:
    """HEAD commit of the repository checkout holding this source tree at REPOSITORY_PATH, if any.

    Reads `.git` metadata as files; it never starts Git. Uncommitted changes are not
    detected, so the CLI reports when provenance came from a checkout HEAD.
    """
    root = Path(__file__).resolve().parent.parent
    parts = tuple(REPOSITORY_PATH.split("/"))
    if not is_source_checkout(root) or root.parts[-len(parts) :] != parts:
        return None
    git_dir = _git_dir(root.parents[len(parts) - 1])
    if git_dir is None or not (git_dir / "HEAD").is_file():
        return None
    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    commit = _resolve_ref(git_dir, head[4:].strip()) if head.startswith("ref:") else head
    return commit if commit is not None and _COMMIT.fullmatch(commit) else None


def resolve_source_commit(declared: str | None = None) -> tuple[str, str]:
    """Return (commit, how): `declared` or `checkout_head`. Refuse an unknown commit."""
    head = checkout_commit()
    if declared is not None:
        if not _COMMIT.fullmatch(declared):
            raise SeedPackError(
                "The source commit must be a full lowercase hexadecimal Git commit id.",
                code="seed_provenance_invalid",
            )
        if head is not None and head != declared:
            raise SeedPackError(
                f"Declared source commit {declared} differs from this checkout's HEAD {head}.",
                code="seed_provenance_mismatch",
            )
        return declared, "declared"
    if head is None:
        raise SeedPackError(
            "Cannot determine which commit produced these nouns. Outside a Git checkout, "
            "pass --source-commit (source_commit=) with the exact commit this package was built from.",
            code="seed_provenance_unknown",
        )
    return head, "checkout_head"


def _provenance(
    commit: str, source_paths: Sequence[str], *, origin: str = "repository"
) -> dict[str, Any]:
    return {
        "repository": REPOSITORY,
        "path": REPOSITORY_PATH,
        "commit": commit,
        "package": PACKAGE,
        "package_version": __version__,
        "content_origin": origin,
        "source_paths": list(source_paths),
    }


def _ratio(part: float, whole: float) -> float:
    return round(part / whole, 6) if whole > 0 else 0.0


def _saved(compact: int, expanded: int) -> float:
    return round(max(0.0, min(1.0, 1.0 - compact / expanded)), 6) if expanded > 0 else 0.0


def _requires(key: str, category: str, note: str) -> dict[str, Any]:
    """A typed Tessera RelationEdge; the target key embeds the target's value digest."""
    return {
        "relation": "requires_noun",
        "target_id": key,
        "target_category": category,
        "note": note,
    }


def _lens_checks(node: PrewrittenNode) -> dict[str, bool]:
    tags = set(node.governance_tags)
    return {
        "code_sha256_matches_source": compute_code_sha256(node.source_code) == node.code_sha256,
        "status_verified": "status:verified" in tags,
        "not_quarantined": "status:quarantined" not in tags,
        "spdx_license_allowed": node.spdx_license in ALLOWED_SPDX_LICENSES,
    }


def _packaged_self_tests(node: PrewrittenNode) -> dict[str, Any]:
    """Run a packaged node's built-in tests, then replay each case and compare outputs."""
    passed = verify_node_self_tests(node)
    fn = load_node_callable(node)
    replayed = 0
    for index, case in enumerate(node.test_cases):
        first = run_node_self_test_case(node, fn, index, case)
        second = run_node_self_test_case(node, fn, index, case)
        replayed += int(canonical_json(first) == canonical_json(second))
    exact = sum(
        1 for case in node.test_cases if isinstance(case.get("expected"), dict) and case["expected"]
    )
    return {
        "executed": True,
        "source": "packaged catalog",
        "cases": len(node.test_cases),
        "passed": passed,
        "replayed_identically": replayed,
        "exact_value_cases": exact,
    }


def _tool_payload(
    node: PrewrittenNode, packaged: Mapping[str, PrewrittenNode], commit: str
) -> dict[str, Any]:
    lens = _lens_checks(node)
    if not all(lens.values()):
        failed = sorted(name for name, ok in lens.items() if not ok)
        raise SeedPackError(f"Node {node.node_id!r} fails governance checks {failed}.")
    reference = packaged.get(node.node_id)
    cases = len(node.test_cases)
    if reference is not None and node_body(reference) == node_body(node):
        tests = _packaged_self_tests(reference)
        provenance = _provenance(commit, [f"{PACKAGE}/seed_nodes.py"])
        determinism = _ratio(tests["replayed_identically"], cases)
        grounding = _ratio(tests["exact_value_cases"], cases)
        tier = "deterministic_gate"
    else:
        tests = {
            "executed": False,
            "source": "local node database",
            "cases": cases,
            "reason": "Stored code is not executed during export; a claiming worker must run these test cases.",
        }
        provenance = _provenance(commit, [], origin="local_node_database")
        determinism = grounding = 0.0
        tier = "unverified"
    return {
        "title": node.summary,
        "node": node_body(node),
        "local_checks": {
            "code_sha256": node.code_sha256,
            "governance_lens": lens,
            "self_tests": tests,
        },
        "dimensions": {
            "determinism": determinism,
            "evidence_grounding": grounding,
            "token_efficiency": _saved(len(node.signature_line()), len(node.source_code)),
            "safety_compliance": _ratio(sum(lens.values()), len(lens)),
            "verification_tier": tier,
        },
        "dimension_basis": TOOL_DIMENSION_BASIS,
        "relations": [],
        "provenance": provenance,
        "spdx_license": node.spdx_license,
    }


@dataclass(frozen=True)
class _CompiledRecipe:
    source_path: str | None
    document: dict[str, Any]
    plan: CompiledPlan
    replay_identical: bool
    emitted_python: str


def _compile_recipes(
    compiler: DeterministicCompiler, authored: Sequence[tuple[str | None, RecipeSpec]]
) -> list[_CompiledRecipe]:
    compiled: list[_CompiledRecipe] = []
    for path, recipe in sorted(authored, key=lambda item: item[1].recipe_id):
        if not has_sample_inputs(recipe.recipe_id):
            raise SeedPackError(f"Recipe {recipe.recipe_id!r} has no made-up sample inputs.")
        document: dict[str, Any] = canonical_value(recipe.model_dump(mode="json"))
        # Compile exactly the normalized JSON that a worker reads back from the recipe noun.
        plan = compiler.compile(RecipeSpec.model_validate(document))
        replay = compiler.compile(RecipeSpec.model_validate(document))
        compiled.append(
            _CompiledRecipe(
                source_path=path,
                document=document,
                plan=plan,
                replay_identical=plan.plan_sha256 == replay.plan_sha256,
                emitted_python=compiler.emit_python_from_plan(plan),
            )
        )
    return compiled


def _runtime_payload(compiled: Sequence[_CompiledRecipe], commit: str) -> dict[str, Any]:
    digests = runtime_module_digests()
    replayed = sum(int(item.replay_identical) for item in compiled)
    return {
        "title": "Deterministic compiler and runtime",
        "tool": {
            "kind": "code-composition.compiler_runtime",
            "entrypoints": list(RUNTIME_ENTRYPOINTS),
            "module_sha256": digests,
            "digest_rule": "SHA-256 of each module's bytes with CRLF normalized to LF.",
        },
        "local_checks": {"recipes_compiled": len(compiled), "compile_replay_identical": replayed},
        "dimensions": {
            "determinism": _ratio(replayed, len(compiled)),
            "evidence_grounding": _ratio(len(digests), len(RUNTIME_MODULES)),
            "token_efficiency": _saved(
                sum(len(canonical_json(item.document)) for item in compiled),
                sum(len(item.emitted_python) for item in compiled),
            ),
            "safety_compliance": _ratio(
                sum(len(item.plan.steps) for item in compiled),
                sum(len(item.document["steps"]) for item in compiled),
            ),
            "verification_tier": "deterministic_gate",
        },
        "dimension_basis": RUNTIME_DIMENSION_BASIS,
        "relations": [],
        "provenance": _provenance(commit, [f"{PACKAGE}/{name}" for name in RUNTIME_MODULES]),
        "spdx_license": PACKAGE_SPDX_LICENSE,
    }


def _entry_inputs_supplied(plan: CompiledPlan, inputs: Mapping[str, Any]) -> tuple[int, int]:
    names = [entry.port_name for entry in plan.entry_inputs]
    required = [entry for entry in plan.entry_inputs if entry.required]
    supplied = sum(
        1
        for entry in required
        if f"{entry.step_id}.{entry.port_name}" in inputs
        or (entry.port_name in inputs and names.count(entry.port_name) == 1)
    )
    return supplied, len(required)


def _recipe_payload(
    item: _CompiledRecipe,
    runtime_key: str,
    node_keys: Mapping[str, str],
    commit: str,
) -> dict[str, Any]:
    recipe_id = str(item.document["recipe_id"])
    inputs = canonical_value(sample_inputs_for_recipe(recipe_id))
    supplied, required = _entry_inputs_supplied(item.plan, inputs)
    if supplied != required:
        raise SeedPackError(
            f"Recipe {recipe_id!r} sample inputs supply {supplied} of {required} required entry inputs."
        )
    node_ids = sorted({str(step["node_id"]) for step in item.document["steps"]})
    paths = [] if item.source_path is None else [item.source_path, f"{PACKAGE}/recipe_catalog.py"]
    return {
        "title": item.document["title"],
        "recipe": item.document,
        "sample_inputs": inputs,
        "sample_inputs_made_up": True,
        "local_checks": {
            "compiled_plan_sha256": item.plan.plan_sha256,
            "compile_replay_identical": item.replay_identical,
            "required_entry_inputs": required,
            "required_entry_inputs_supplied": supplied,
            "executed_during_export": False,
        },
        "dimensions": {
            "determinism": 1.0 if item.replay_identical else 0.0,
            "evidence_grounding": _ratio(supplied, required) if required else 1.0,
            "token_efficiency": _saved(
                len(canonical_json(item.document)), len(item.emitted_python)
            ),
            "safety_compliance": _ratio(len(item.plan.steps), len(item.document["steps"])),
            "verification_tier": "deterministic_gate",
        },
        "dimension_basis": RECIPE_DIMENSION_BASIS,
        "relations": [
            _requires(runtime_key, "noun.code_node", "Compiler and runtime modules"),
            *(
                _requires(node_keys[node_id], "noun.code_node", f"Prewritten node {node_id}")
                for node_id in node_ids
            ),
        ],
        "provenance": _provenance(
            commit, paths, origin="repository" if item.source_path else "caller_supplied"
        ),
        "spdx_license": PACKAGE_SPDX_LICENSE,
    }


def _task_brief(
    recipe_ref: dict[str, Any], runtime_ref: dict[str, Any], node_refs: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "contract": TASK_CONTRACT,
        "category_id": "verb.compile_dag",
        "project": "code-composition",
        "stage": "compile_execute_verify",
        "outcome": "Compile and execute the pinned recipe with its made-up sample inputs; retain outputs and Python equivalence evidence.",
        "recipe_ref": recipe_ref,
        "runtime_ref": runtime_ref,
        "input_refs": [recipe_ref, runtime_ref, *node_refs],
        "required_capabilities": [
            "read permitted noun versions",
            "code-composition deterministic runtime matching runtime_ref",
        ],
        "guidance": {
            "required": [
                "Claim through Tessera and recheck permissions before reading the pinned nouns.",
                "Read each input_refs version and verify its value_sha256; fail on a missing or changed input.",
                "Require the local compiler/runtime module SHA-256 values to equal the runtime_ref noun's pins.",
                "Use only local verified PrewrittenNodes identical to the pinned tool nouns and rerun their built-in tests; never execute source code copied from a noun.",
                "Recompile the pinned recipe and require its local_checks.compiled_plan_sha256 before executing.",
                "Execute with the bundled made-up sample inputs and verify emitted Python equivalence.",
                "Keep outputs private; submit exact output noun references and the execution receipt.",
            ],
            "preferred": [
                "Run code_composition.seed_worker.execute_seed_task in an already qualified local installation of these tools."
            ],
        },
        "execution": {
            "model_calls": 0,
            "network_required": False,
            "publication_permitted": False,
            "server_fallback": False,
            "maximum_automatically_enqueued_children": 0,
        },
        "output_contract": {
            "required": ["artifact_refs", "execution_receipt", "python_equivalence_verified"],
            "permitted_outcomes": ["candidate_ready", "blocked"],
        },
    }


def _pack_dimensions(
    members: Sequence[Mapping[str, Any]], stats: Mapping[str, int]
) -> dict[str, Any]:
    def axis(name: str) -> list[float]:
        return [float(item[name]) for item in members]

    grounding = axis("evidence_grounding")
    return {
        "determinism": round(min(axis("determinism"), default=0.0), 6),
        "evidence_grounding": round(sum(grounding) / len(grounding), 6) if grounding else 0.0,
        "token_efficiency": _saved(stats["signature_chars"], stats["raw_code_chars"]),
        "safety_compliance": round(min(axis("safety_compliance"), default=0.0), 6),
        "verification_tier": "deterministic_gate"
        if all(item["verification_tier"] == "deterministic_gate" for item in members)
        else "unverified",
    }


def build_seed_pack(
    db: NodeDatabase,
    *,
    namespace: str,
    queue: str,
    store: str = "code-composition.seeds",
    recipes: Sequence[RecipeSpec] | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Check local nodes, runtime and recipes; export create-only requests with no fabric I/O.

    `db` is only read; open a file database with `NodeDatabase.open_existing_read_only`.
    Version-1 pins are conditional on successful create-only writes and readback. This
    document is a local review bundle, not a generic importer API.
    """
    for label, name in (("namespace", namespace), ("queue", queue), ("store", store)):
        if not _NAME.fullmatch(name):
            raise SeedPackError(f"Invalid {label}: use an assigned Tessera name.")
    commit = resolve_source_commit(source_commit)[0]
    scope = {
        "namespace": namespace,
        # Packs are not surfaces: Tessera attributes `surface:tessera` writes to the writing
        # key's own authenticated surface, so the importing team's surface owns these records.
        "producer_surface": "surface:tessera",
        "visibility_scope": "private",
        "allowed_surfaces": [],
        "target_cohorts": ["all"],
    }
    records: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    member_dimensions: list[Mapping[str, Any]] = []

    def noun(category: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Append one create-only RecordWrite and return its NounRef pin."""
        value = canonical_value(
            {
                "category_id": category,
                "role": role,
                "project": "code-composition",
                "dimension_method": DIMENSION_METHOD,
                "fabric_admission": "pending",
                **payload,
            }
        )
        key = f"{role}.{value_sha256(value)}"
        records.append(
            {
                **scope,
                "store": store,
                "key": key,
                "expected_version": 0,
                "value": value,
                "tags": [
                    f"category:{category}",
                    "project:code-composition",
                    f"role:{role}",
                    "status:quarantined",
                ],
            }
        )
        member_dimensions.append(payload["dimensions"])
        return noun_ref(store, key, value)

    packaged = {node.node_id: node for node in build_seed_nodes()}
    node_refs = {
        node.node_id: noun("noun.code_node", "tool", _tool_payload(node, packaged, commit))
        for node in db.list_nodes()
    }
    compiler = DeterministicCompiler(db)
    authored = load_catalog_recipes() if recipes is None else [(None, recipe) for recipe in recipes]
    compiled = _compile_recipes(compiler, authored)
    runtime_ref = noun("noun.code_node", "tool", _runtime_payload(compiled, commit))
    node_keys = {node_id: ref["key"] for node_id, ref in node_refs.items()}
    for item in compiled:
        payload = _recipe_payload(item, runtime_ref["key"], node_keys, commit)
        recipe_ref = noun("noun.skill_pack", "recipe", payload)
        steps = sorted({str(step["node_id"]) for step in item.document["steps"]})
        brief = _task_brief(recipe_ref, runtime_ref, [node_refs[node_id] for node_id in steps])
        tasks.append(
            {
                **scope,
                "queue": queue,
                "kind": "verb.compile_dag",
                "effect_class": "write-internal",
                "idempotency_key": f"code-composition-seed:{value_sha256({'queue': queue, 'brief': brief})}",
                "tags": [
                    "category:verb.compile_dag",
                    "project:code-composition",
                    "status:quarantined",
                ],
                "brief": brief,
            }
        )

    members = list(records)
    pack_dimensions = _pack_dimensions(member_dimensions, db.catalog_token_stats())
    noun(
        "noun.skill_pack",
        "project",
        {
            "title": "Code composition: verified code and recipe seed pack",
            "definition": "Index of the code-composition tool and recipe nouns and their compile/execute verb seeds. A label for discovery, not a service, queue or permission; Tessera owns coordination.",
            "relations": [
                _requires(
                    record["key"],
                    str(record["value"]["category_id"]),
                    f"Pack member: {record['value']['role']}",
                )
                for record in members
            ],
            "seed_identities": [task["idempotency_key"] for task in tasks],
            "dimensions": pack_dimensions,
            "dimension_basis": PACK_DIMENSION_BASIS,
            "provenance": _provenance(commit, [f"{PACKAGE}/seed_pack.py"]),
            "spdx_license": PACKAGE_SPDX_LICENSE,
        },
    )
    return {
        "format": PACK_FORMAT,
        "status": "offline_candidate",
        "importer": None,
        "activation": "Create permitted records, verify version-1 readback, then explicitly enqueue in an existing queue.",
        "source": {
            "repository": REPOSITORY,
            "path": REPOSITORY_PATH,
            "commit": commit,
            "package": PACKAGE,
            "package_version": __version__,
        },
        "records": records,
        "tasks": tasks,
    }
