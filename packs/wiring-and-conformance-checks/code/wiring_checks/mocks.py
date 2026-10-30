"""List what each test patches, and whether a documented behavior's tests replace part of its real path.

The scan reads test files with ast and never runs them. It finds unittest.mock patches (patch,
patch.object, patch.dict and patch.multiple, as decorators, in with statements or as plain calls),
class decorators and setUp patches that apply to every test in a class, pytest's monkeypatch.setattr
and delattr, and fixtures in the same file that patch on a test's behalf. Names are resolved through
the test file's own imports, so patch.object(Store, "save") after `from app.store import Store` reads
as app.store.Store.save.

A behavior map lists, for each documented behavior, the dotted names on its real path and the tests
said to cover it. A behavior is real_path when at least one of those tests patches nothing on the path,
mock_only when every one does, and untested when none of them exists.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .modules import dotted, python_files

PATCH_KINDS = ("patch", "patch.object", "patch.dict", "patch.multiple")
MOCK_MODULES = ("unittest.mock", "mock")
MONKEYPATCH = ("monkeypatch.setattr", "monkeypatch.delattr")
SETUP = ("setUp", "setUpClass", "asyncSetUp", "setup_method", "setup_class")
BEHAVIOR_STATUSES = ("real_path", "mock_only", "untested")


def import_aliases(tree: ast.Module) -> dict[str, str]:
    """Local names a test file binds by import, mapped to the dotted names they stand for."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    head = alias.name.split(".", 1)[0]
                    aliases.setdefault(head, head)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                if alias.name != "*":
                    aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
                elif node.module in MOCK_MODULES:
                    aliases.setdefault("patch", f"{node.module}.patch")
    return aliases


def resolve(name: str, aliases: dict[str, str]) -> str:
    """Replace a dotted name's first part by what the file's imports bind it to."""
    head, _, rest = name.partition(".")
    if head in aliases:
        return aliases[head] + (f".{rest}" if rest else "")
    return name


def _patch_kind(func: ast.AST, aliases: dict[str, str]) -> str | None:
    name = dotted(func)
    if name is None:
        return None
    if name in MONKEYPATCH:
        return name
    full = resolve(name, aliases)
    for kind in PATCH_KINDS:
        if any(full == f"{module}.{kind}" for module in MOCK_MODULES):
            return kind
    return None


def _text(node: ast.AST, aliases: dict[str, str]) -> str:
    name = dotted(node)
    return resolve(name, aliases) if name else ast.unparse(node)


def _string(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def patch_targets(call: ast.Call, aliases: dict[str, str]) -> list[str]:
    """The dotted targets one patch call replaces; [] when the call is not a patch."""
    kind = _patch_kind(call.func, aliases)
    if kind is None:
        return []
    args = list(call.args)
    keyword = {k.arg: k.value for k in call.keywords if k.arg}
    first = args[0] if args else keyword.get("target")
    if kind in ("patch", "patch.dict"):
        text = _string(first)
        return [text if text is not None else _text(first, aliases)] if first is not None else []
    if kind == "patch.object":
        attribute = _string(args[1]) if len(args) > 1 else _string(keyword.get("attribute"))
        return [f"{_text(first, aliases)}.{attribute}"] if first is not None and attribute else []
    if kind == "patch.multiple":
        owner = _string(first) or (_text(first, aliases) if first is not None else "")
        return [f"{owner}.{name}" for name in sorted(keyword) if name not in ("target", "spec", "create",
                                                                              "spec_set", "autospec", "new_callable")]
    # monkeypatch.setattr and delattr take a dotted string, or an object and an attribute name.
    text = _string(first)
    if text is not None:
        return [text]
    attribute = _string(args[1]) if len(args) > 1 else _string(keyword.get("name"))
    return [f"{_text(first, aliases)}.{attribute}"] if first is not None and attribute else []


def _calls(nodes: list[ast.AST]) -> list[ast.Call]:
    found = []
    for node in nodes:
        found += [item for item in ast.walk(node) if isinstance(item, ast.Call)]
    return found


def _targets_in(nodes: list[ast.AST], aliases: dict[str, str]) -> set[str]:
    out: set[str] = set()
    for call in _calls(nodes):
        out.update(patch_targets(call, aliases))
    return out


def _is_fixture(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in func.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = dotted(target) or ""
        if name == "fixture" or name.endswith(".fixture"):
            return True
    return False


def _params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    return [a.arg for a in [*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs]]


def _fixture_patches(functions: list[ast.FunctionDef | ast.AsyncFunctionDef], aliases: dict[str, str]) -> dict[str, set[str]]:
    """What each fixture in the file patches, including fixtures it asks for in turn."""
    fixtures = {f.name: f for f in functions if _is_fixture(f)}
    own = {name: _targets_in(f.body, aliases) for name, f in fixtures.items()}
    resolved: dict[str, set[str]] = {}

    def total(name: str, seen: frozenset[str] = frozenset()) -> set[str]:
        if name in resolved:
            return resolved[name]
        out = set(own[name])
        for param in _params(fixtures[name]):
            if param in fixtures and param not in seen:
                out |= total(param, seen | {name})
        resolved[name] = out
        return out

    for name in fixtures:
        total(name)
    return resolved


def _is_test_class(node: ast.ClassDef) -> bool:
    return node.name.startswith("Test") or any((dotted(b) or "").endswith("TestCase") for b in node.bases)


def scan_file(path: Path, shown_as: str) -> list[dict]:
    """Every test in one file with the sorted targets it patches."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = import_aliases(tree)
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    fixtures = _fixture_patches(functions, aliases)

    def own(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
        out = _targets_in(func.body, aliases) | _targets_in(func.decorator_list, aliases)
        for param in _params(func):
            out |= fixtures.get(param, set())
        return out

    rows = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            rows.append({"id": f"{shown_as}::{node.name}", "patched": sorted(own(node))})
        elif isinstance(node, ast.ClassDef) and _is_test_class(node):
            shared = _targets_in(node.decorator_list, aliases)
            methods = [m for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
            for method in methods:
                if method.name in SETUP:
                    shared |= own(method)
            for method in methods:
                if method.name.startswith("test"):
                    rows.append({"id": f"{shown_as}::{node.name}::{method.name}", "patched": sorted(own(method) | shared)})
    return rows


def scan_tests(paths: list[Path], base: Path) -> list[dict]:
    """Tests in the given files, or in test_*.py and *_test.py files under the given folders, by id."""
    base = base.resolve()
    files = []
    for path in paths:
        path = path.resolve()
        if path.is_dir():
            files += [p for p in python_files(path) if p.name.startswith("test_") or p.name.endswith("_test.py")]
        else:
            files.append(path)
    rows = []
    for path in sorted(set(files)):
        shown = path.relative_to(base).as_posix() if path.is_relative_to(base) else path.as_posix()
        rows += scan_file(path, shown)
    return sorted(rows, key=lambda row: row["id"])


def hits_path(target: str, element: str) -> bool:
    """A patch replaces part of a path element when the names are equal or one contains the other."""
    return target == element or element.startswith(target + ".") or target.startswith(element + ".")


def check_behaviors(behaviors: list[dict], tests: list[dict]) -> list[dict]:
    """Classify each documented behavior by whether a listed test runs its real path unpatched."""
    by_id = {row["id"]: row for row in tests}
    out = []
    for behavior in behaviors:
        listed = list(behavior.get("tests", []))
        rows = []
        for test_id in (t for t in listed if t in by_id):
            hits = sorted({p for p in by_id[test_id]["patched"] for e in behavior["real_path"] if hits_path(p, e)})
            rows.append({"test": test_id, "patched_on_path": hits})
        clean = [row["test"] for row in rows if not row["patched_on_path"]]
        status = "untested" if not rows else ("real_path" if clean else "mock_only")
        out.append({"id": behavior["id"], "status": status, "real_path_tests": clean, "tests": rows,
                    "missing_tests": [t for t in listed if t not in by_id]})
    return out
