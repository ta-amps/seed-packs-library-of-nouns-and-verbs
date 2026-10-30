"""Command-line interface and end-to-end deterministic recipe-to-DAG demo."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from code_composition.compiler import DeterministicCompiler
from code_composition.composer import RecipeComposer, load_example_recipes, sample_inputs_for_recipe
from code_composition.errors import CodeCompositionError
from code_composition.registry import NodeDatabase
from code_composition.runtime import DeterministicRuntime
from code_composition.schemas import RecipeSpec, canonical_json
from code_composition.seed_pack import build_seed_pack, resolve_source_commit


def _default_db_path() -> str:
    return os.environ.get("CODE_COMPOSITION_DB") or ".code-composition/code-composition.db"


def _load_recipe_arg(path_str: str) -> RecipeSpec:
    path = Path(path_str)
    if not path.is_file():
        by_id = {r.recipe_id: r for r in load_example_recipes()}
        if path_str in by_id:
            return by_id[path_str]
        raise FileNotFoundError(f"Recipe file or ID not found: {path_str}")
    return RecipeSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))


def cmd_init(args: argparse.Namespace) -> int:
    db = NodeDatabase(args.db, auto_seed=True)
    report = db.verify_all()
    print(f"code-composition init: {len(report)} verified prewritten nodes ready in {args.db}")
    db.close()
    return 0


def cmd_nodes(args: argparse.Namespace) -> int:
    db = NodeDatabase(args.db, auto_seed=True)
    if args.signatures:
        print(db.catalog_signature_prompt(category=args.category))
    else:
        nodes = db.list_nodes(category=args.category)
        for node in nodes:
            in_ports = ", ".join(f"{p.name}:{p.port_type}" for p in node.inputs)
            out_ports = ", ".join(f"{p.name}:{p.port_type}" for p in node.outputs)
            print(
                f"{node.node_id:30s}  ({in_ports}) -> ({out_ports})  sha256:{node.code_sha256[:12]}"
            )
    db.close()
    return 0


def cmd_verify_nodes(args: argparse.Namespace) -> int:
    db = NodeDatabase(args.db, auto_seed=True)
    report = db.verify_all()
    total_cases = sum(int(item["tests_passed"]) for item in report.values())
    print(
        f"code-composition verify-nodes: {len(report)} nodes verified ({total_cases} self-test cases passed)"
    )
    for node_id, meta in report.items():
        print(
            f"  [ok] {node_id:28s} sha256:{str(meta['code_sha256'])[:16]}  tests={meta['tests_passed']}"
        )
    db.close()
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    db = NodeDatabase(args.db, auto_seed=True)
    compiler = DeterministicCompiler(db)
    recipe = _load_recipe_arg(args.recipe)
    plan = compiler.compile(recipe)
    if args.emit_python:
        py_src = compiler.emit_python_from_plan(plan)
        if args.out:
            Path(args.out).write_text(py_src, encoding="utf-8")
            print(f"code-composition compile: wrote standalone Python pipeline to {args.out}")
        else:
            print(py_src, end="")
    else:
        output = json.dumps(plan.model_dump(mode="json"), indent=2)
        if args.out:
            Path(args.out).write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
    db.close()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    db = NodeDatabase(args.db, auto_seed=True)
    compiler = DeterministicCompiler(db)
    runtime = DeterministicRuntime(db, compiler)
    recipe = _load_recipe_arg(args.recipe)
    if args.inputs:
        inputs: dict[str, Any] = json.loads(Path(args.inputs).read_text(encoding="utf-8"))
    else:
        inputs = sample_inputs_for_recipe(recipe.recipe_id)
    result = runtime.execute(recipe, inputs, verify_emitted_python=args.verify_python)
    rcpt = result.receipt
    print(f"recipe_id:              {rcpt.recipe_id}")
    print(f"plan_sha256:            {rcpt.plan_sha256}")
    print(
        f"executed_steps ({len(rcpt.executed_steps):2d}):   {', '.join(rcpt.executed_steps) or 'none'}"
    )
    print(f"memo_hits ({len(rcpt.memo_hits):2d}):        {', '.join(rcpt.memo_hits) or 'none'}")
    print(f"llm_tokens_at_runtime:  {rcpt.llm_tokens_at_runtime}")
    print(f"python_equiv_verified:  {result.python_equivalence_verified}")
    print(f"receipt_sha256:         {rcpt.receipt_sha256}")
    db.close()
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    db = NodeDatabase(args.db, auto_seed=True)
    compiler = DeterministicCompiler(db)
    composer = RecipeComposer(db, compiler)
    recipe, plan = composer.compose(args.goal, force_offline=args.offline)
    if args.emit_python:
        print(compiler.emit_python_from_plan(plan), end="")
    else:
        print(json.dumps(recipe.model_dump(mode="json"), indent=2))
    db.close()
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    db = NodeDatabase(args.db, auto_seed=True)
    compiler = DeterministicCompiler(db)
    runtime = DeterministicRuntime(db, compiler)
    composer = RecipeComposer(db, compiler)

    print("=== Recipe-to-DAG Deterministic Compiler Demo ===")
    verification = db.verify_all()
    tok = db.catalog_token_stats()
    print(
        f"1. Verified node database: {len(verification)}/18 nodes passed self-tests "
        f"(signature catalog ~{tok['signature_tokens_est']} tok vs ~{tok['raw_code_tokens_est']} tok raw Python)"
    )

    recipes = load_example_recipes()
    print(
        f"2. Compiling & executing {len(recipes)} declarative recipes with Python equivalence proof:"
    )
    for recipe in recipes:
        plan = compiler.compile(recipe)
        py_src = compiler.emit_python_from_plan(plan)
        res = runtime.execute(
            plan,
            sample_inputs_for_recipe(recipe.recipe_id),
            verify_emitted_python=True,
        )
        recipe_tok = max(1, round(len(canonical_json(recipe.model_dump(mode="json"))) / 4))
        py_tok = max(1, round(len(py_src) / 4))
        print(
            f"   - {recipe.recipe_id:26s} | {len(plan.steps):2d} steps | "
            f"recipe ~{recipe_tok:3d} tok -> wired Python ~{py_tok:4d} tok | "
            f"equiv={res.python_equivalence_verified} | receipt={res.receipt.receipt_sha256[:12]}..."
        )

    # Prefix memoization demonstration on a challenger variant of ab-candidate-selection
    ab_base = next(r for r in recipes if r.recipe_id == "ab-candidate-selection")
    variant_raw = ab_base.model_dump(mode="json")
    variant_raw["recipe_id"] = "ab-candidate-selection-v2"
    variant_raw["title"] = "Challenger B2 Weight Sweep (Shared 7-Step Prefix)"
    for step in variant_raw["steps"]:
        if step["step_id"] == "score_arm_b":
            step["params"]["weights_csv"] = "11.5,0.012"
            step["params"]["bias"] = -2.5
    variant_recipe = RecipeSpec.model_validate(variant_raw)
    warm_res = runtime.execute(
        variant_recipe,
        sample_inputs_for_recipe("ab-candidate-selection"),
        verify_emitted_python=True,
    )
    print(
        f"3. Warm sub-DAG prefix reuse ({variant_recipe.recipe_id}): "
        f"memo_hits={len(warm_res.receipt.memo_hits)}/{len(warm_res.plan.steps)} steps "
        f"({', '.join(warm_res.receipt.memo_hits)}), "
        f"executed={len(warm_res.receipt.executed_steps)}, "
        f"llm_tokens_at_runtime={warm_res.receipt.llm_tokens_at_runtime}"
    )

    # Loose-proposal deterministic compiler guard demonstration
    broken_raw = recipes[1].model_dump(mode="json")
    broken_raw["edges"][1]["src_port"] = "rowz"
    verdict = composer.validate_candidate(broken_raw)
    print(
        f"4. Loose candidate compile-time rollback: valid={verdict.valid} "
        f"code={verdict.error_code} -> {verdict.error_detail}"
    )
    db.close()
    return 0


def cmd_seed_pack(args: argparse.Namespace) -> int:
    commit, how = resolve_source_commit(args.source_commit)
    # Never create, migrate or seed a named database just to export from it.
    db = (
        NodeDatabase(":memory:", auto_seed=True)
        if args.db in (None, ":memory:")
        else NodeDatabase.open_existing_read_only(args.db)
    )
    try:
        pack = build_seed_pack(
            db,
            namespace=args.namespace,
            queue=args.queue,
            store=args.store,
            source_commit=commit,
        )
    finally:
        db.close()
    if how == "checkout_head":
        print(
            f"code-composition seed-pack: provenance commit {commit} is this checkout's HEAD; uncommitted "
            "changes are not detected. Export from a clean checkout.",
            file=sys.stderr,
        )
    print(json.dumps(pack, indent=2, sort_keys=True, allow_nan=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code-composition",
        description="Recipe-to-DAG deterministic code compiler over prewritten verified nodes.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize and seed the verified SQLite node database.")
    p_init.add_argument("--db", default=_default_db_path(), help="SQLite database path.")
    p_init.set_defaults(func=cmd_init)

    p_nodes = sub.add_parser("nodes", help="List verified prewritten nodes or signature prompt.")
    p_nodes.add_argument("--db", default=_default_db_path(), help="SQLite database path.")
    p_nodes.add_argument("--category", default=None, help="Filter by node category.")
    p_nodes.add_argument(
        "--signatures",
        action="store_true",
        help="Print the compact typed signature prompt exposed to LLM composers.",
    )
    p_nodes.set_defaults(func=cmd_nodes)

    p_verify = sub.add_parser("verify-nodes", help="Run SHA-256 and self-test checks on all nodes.")
    p_verify.add_argument("--db", default=_default_db_path(), help="SQLite database path.")
    p_verify.set_defaults(func=cmd_verify_nodes)

    p_pack = sub.add_parser(
        "seed-pack", help="Export private candidate nouns and worker seeds offline."
    )
    p_pack.add_argument("--namespace", required=True, help="Already assigned Tessera namespace.")
    p_pack.add_argument("--queue", required=True, help="Existing authorized work queue.")
    p_pack.add_argument(
        "--store", default="code-composition.seeds", help="Authorized candidate store."
    )
    p_pack.add_argument(
        "--db",
        default=None,
        help=(
            "Existing node database, opened read-only; it is never created, migrated or seeded "
            "and its stored code is never executed. Default: the packaged catalog in memory."
        ),
    )
    p_pack.add_argument(
        "--source-commit",
        default=None,
        help="Exact commit this package was built from; required outside a Git checkout.",
    )
    p_pack.set_defaults(func=cmd_seed_pack)

    p_compile = sub.add_parser("compile", help="Compile a RecipeSpec JSON into a verified DAG.")
    p_compile.add_argument("recipe", help="Path to recipe JSON or built-in recipe_id.")
    p_compile.add_argument("--db", default=_default_db_path(), help="SQLite database path.")
    p_compile.add_argument(
        "--emit-python",
        action="store_true",
        help="Emit standalone wired Python module instead of CompiledPlan JSON.",
    )
    p_compile.add_argument("--out", default=None, help="Optional output file path.")
    p_compile.set_defaults(func=cmd_compile)

    p_run = sub.add_parser("run", help="Compile and deterministically execute a RecipeSpec.")
    p_run.add_argument("recipe", help="Path to recipe JSON or built-in recipe_id.")
    p_run.add_argument("--inputs", default=None, help="JSON file of initial_inputs.")
    p_run.add_argument("--db", default=_default_db_path(), help="SQLite database path.")
    p_run.add_argument(
        "--verify-python",
        action="store_true",
        help="Verify byte-identical output equivalence against emitted standalone Python.",
    )
    p_run.set_defaults(func=cmd_run)

    p_compose = sub.add_parser("compose", help="Compose a verified RecipeSpec from a goal prompt.")
    p_compose.add_argument("goal", help="Natural-language pipeline goal.")
    p_compose.add_argument("--db", default=_default_db_path(), help="SQLite database path.")
    p_compose.add_argument(
        "--offline", action="store_true", help="Force offline deterministic composer."
    )
    p_compose.add_argument(
        "--emit-python", action="store_true", help="Emit standalone Python module."
    )
    p_compose.set_defaults(func=cmd_compose)

    p_demo = sub.add_parser(
        "demo", help="Run full verification, compilation, equivalence, and cache demo."
    )
    p_demo.add_argument("--db", default=_default_db_path(), help="SQLite database path.")
    p_demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        handler = args.func
        rc: int = handler(args)
        return rc
    except CodeCompositionError as exc:
        print(f"code-composition error [{exc.code}]: {exc.detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
