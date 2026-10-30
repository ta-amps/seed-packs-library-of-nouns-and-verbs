"""Find exception handlers in Python code that swallow errors, by reading the syntax tree with ast.

Classes, from most to least serious:
  swallowed       a broad handler (bare except, Exception or BaseException) whose body does nothing:
                  pass, ..., continue, break or return None
  suppress_broad  contextlib.suppress(Exception) or suppress(BaseException)
  logged_only     a broad handler that only logs or prints, then carries on
  fallback        a broad handler that returns a value instead of the error
  narrow_ignored  a specific exception whose body does nothing; often fine, listed for review
A handler that raises anywhere in its own body, or does other work, is not listed. A file that does not
parse is reported as unparsed, never skipped. The code is read, never imported or run.
"""

from __future__ import annotations

import ast
import fnmatch
from pathlib import Path
from typing import Any, Iterable

BROAD = {"Exception", "BaseException"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
CLASSES = ("swallowed", "suppress_broad", "logged_only", "fallback", "narrow_ignored")
ACT = {"swallowed", "suppress_broad"}
SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
             ".ruff_cache", "build", "dist"}


def names(node: ast.AST | None) -> list[str]:
    """The exception names a handler type mentions: Name, dotted Attribute or a tuple of them."""
    if node is None:
        return []
    if isinstance(node, ast.Tuple):
        return [n for item in node.elts for n in names(item)]
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    return [ast.unparse(node)]


def raises(body: list[ast.stmt]) -> bool:
    """Whether the handler raises in its own body; a raise inside a nested function or class does not count."""
    stack: list[ast.AST] = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(node))
    return False


def no_op(stmt: ast.stmt) -> bool:
    if isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return True
    return isinstance(stmt, ast.Return) and (stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None))


def logs(stmt: ast.stmt) -> bool:
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return False
    func = stmt.value.func
    return (isinstance(func, ast.Attribute) and func.attr in LOG_METHODS) or (isinstance(func, ast.Name) and func.id == "print")


def classify(handler: ast.ExceptHandler) -> str | None:
    if raises(handler.body):
        return None
    broad = handler.type is None or bool(BROAD & set(names(handler.type)))
    body = handler.body
    if all(no_op(s) for s in body):
        return "swallowed" if broad else "narrow_ignored"
    if not broad:
        return None
    if all(logs(s) or no_op(s) for s in body):
        return "logged_only"
    if isinstance(body[-1], ast.Return) and all(logs(s) or no_op(s) for s in body[:-1]):
        return "fallback"
    return None


def describe(handler: ast.ExceptHandler) -> str:
    if handler.type is None:
        return "except:"
    return f"except {ast.unparse(handler.type)}" + (f" as {handler.name}:" if handler.name else ":")


def body_kind(handler: ast.ExceptHandler) -> str:
    parts = []
    for stmt in handler.body:
        if logs(stmt):
            parts.append("log")
        elif isinstance(stmt, ast.Return):
            parts.append("return None" if no_op(stmt) else "return value")
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            parts.append("ellipsis" if stmt.value.value is Ellipsis else "constant")
        else:
            parts.append(type(stmt).__name__.lower())
    return ", ".join(parts)


class Finder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.found: list[dict[str, Any]] = []

    def visit_scoped(self, node: ast.AST) -> None:
        self.scope.append(getattr(node, "name", "?"))
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = visit_scoped

    def where(self) -> str:
        return ".".join(self.scope) or "<module>"

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        kind = classify(node)
        if kind:
            self.found.append({"line": node.lineno, "end_line": node.end_lineno, "class": kind, "handler": describe(node),
                               "body": body_kind(node), "in": self.where()})
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            call = item.context_expr
            if isinstance(call, ast.Call):
                target = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", None)
                caught = [n for arg in call.args for n in names(arg)]
                if target == "suppress" and BROAD & set(caught):
                    self.found.append({"line": node.lineno, "end_line": node.end_lineno, "class": "suppress_broad",
                                       "handler": f"with {ast.unparse(call)}:", "body": "suppressed block", "in": self.where()})
        self.generic_visit(node)

    visit_AsyncWith = visit_With


def scan_source(text: str) -> list[dict[str, Any]]:
    finder = Finder()
    finder.visit(ast.parse(text))
    return sorted(finder.found, key=lambda f: (f["line"], f["class"]))


def python_files(root: Path, exclude: Iterable[str] = ()) -> list[Path]:
    if root.is_file():
        return [root]
    patterns = list(exclude)
    out = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if set(rel.parts[:-1]) & SKIP_DIRS or path.is_symlink():
            continue
        if any(fnmatch.fnmatch(rel.as_posix(), p) for p in patterns):
            continue
        out.append(path)
    return out


def find_swallowed(root: Path, exclude: Iterable[str] = ()) -> dict[str, Any]:
    """Every listed handler under a root, by file and line, with counts by class and the files that did not parse."""
    root = Path(root)
    base = root if root.is_dir() else root.parent
    items: list[dict[str, Any]] = []
    unparsed: list[dict[str, Any]] = []
    files = python_files(root, exclude)
    for path in files:
        shown = path.relative_to(base).as_posix()
        try:
            found = scan_source(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
            unparsed.append({"path": shown, "line": getattr(exc, "lineno", None), "error": type(exc).__name__})
            continue
        items += [{"path": shown, **item} for item in found]
    counts = {name: sum(1 for i in items if i["class"] == name) for name in CLASSES}
    return {"files": len(files), "count": len(items), "counts": counts, "act": sum(counts[c] for c in ACT),
            "unparsed": unparsed, "items": items}
