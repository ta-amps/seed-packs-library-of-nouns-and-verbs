"""Find health probes that probe nothing, from Python source alone.

A probe is a function whose name looks like one (health, healthz, ready, readyz, live, livez and the
like) or whose route decorator names such a path. The scan reads each probe's body with ast and never
runs it:

  constant   it returns only literals and calls nothing but response builders: it cannot fail
  flag_only  it calls nothing but reads a name or attribute, such as a flag set at start-up: it
             reports a remembered state, not a dependency
  calls      it calls or awaits something else, so it may probe a dependency; only stopping that
             dependency and watching the probe fail shows that it does

constant and flag_only probes are hollow. A probe that calls something is a lead to test, not a pass.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .modules import dotted, module_name, python_files

PROBE_NAMES = r"^(health|healthz|healthcheck|health_check|ready|readyz|readiness|live|livez|liveness)$"
PROBE_ROUTE = re.compile(r"/(health|healthz|healthcheck|health_check|ready|readyz|readiness|live|livez|liveness|ping)(/|$|\?)")
RESPONSE_BUILDERS = {"dict", "list", "tuple", "str", "int", "float", "bool", "jsonify", "JSONResponse",
                     "PlainTextResponse", "Response", "HTTPResponse", "make_response", "json_response"}
KINDS = ("constant", "flag_only", "calls")


def _route(decorator: ast.AST) -> str | None:
    if isinstance(decorator, ast.Call):
        for arg in decorator.args[:1]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and PROBE_ROUTE.search(arg.value):
                return arg.value
    return None


def is_probe(func: ast.FunctionDef | ast.AsyncFunctionDef, names: re.Pattern[str]) -> str | None:
    """Why a function counts as a probe: its name or its route; None when it is not one."""
    if names.search(func.name):
        return f"name {func.name}"
    for decorator in func.decorator_list:
        route = _route(decorator)
        if route:
            return f"route {route}"
    return None


def _nested(func: ast.AST) -> set[int]:
    """Ids of nodes inside functions or classes nested in func, which do not run when func runs."""
    inner: set[int] = set()
    for node in ast.walk(func):
        if node is not func and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            inner.update(id(child) for child in ast.walk(node))
    return inner


def classify(func: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    """constant, flag_only or calls, with the calls made and the names read."""
    skip = _nested(func)
    nodes = [n for stmt in func.body for n in ast.walk(stmt) if id(n) not in skip]
    calls, reads, awaits = set(), set(), False
    callees = set()
    for node in nodes:
        if isinstance(node, ast.Await):
            awaits = True
        elif isinstance(node, ast.Call):
            callees.update(id(child) for child in ast.walk(node.func))
            name = dotted(node.func) or ast.unparse(node.func)
            if name.rsplit(".", 1)[-1] not in RESPONSE_BUILDERS:
                calls.add(name)
    for node in nodes:
        if id(node) in callees:
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            reads.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            name = dotted(node)
            if name:
                reads.add(name)
    if calls or awaits:
        kind = "calls"
    elif reads:
        kind = "flag_only"
    else:
        kind = "constant"
    reads = {r for r in reads if not any(other.startswith(r + ".") for other in reads)}
    return {"kind": kind, "calls": sorted(calls), "reads": sorted(reads), "awaits": awaits}


def scan_probes(root: Path, paths: list[Path] | None = None, names: str = PROBE_NAMES,
                base: Path | None = None) -> dict:
    """Every probe in the files under root (or in the given files and folders), and the hollow ones.

    Module names start from root; paths in the result are relative to base (root by default).
    """
    root = root.resolve()
    base = (base or root).resolve()
    pattern = re.compile(names)
    files = []
    for path in [p.resolve() for p in (paths or [root])]:
        files += python_files(path) if path.is_dir() else [path]
    probes = []
    for path in sorted(set(files)):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module = module_name(path.relative_to(root)) if path.is_relative_to(root) else path.stem
        shown = path.relative_to(base).as_posix() if path.is_relative_to(base) else path.as_posix()
        for owner, func in _functions(tree):
            why = is_probe(func, pattern)
            if why:
                qualified = ".".join(part for part in (module, owner, func.name) if part)
                probes.append({"probe": qualified, "path": shown, "line": func.lineno, "why": why, **classify(func)})
    probes.sort(key=lambda row: row["probe"])
    return {"probes": probes, "hollow": [row["probe"] for row in probes if row["kind"] in ("constant", "flag_only")]}


def _functions(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield "", node
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield node.name, item
