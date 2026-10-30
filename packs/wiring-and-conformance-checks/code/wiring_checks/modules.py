"""Find modules that no live path imports, from Python source alone.

The finder parses every module of the selected packages with ast, resolves absolute and relative
imports, string-literal importlib calls and imports made only for type checking, and walks the import
graph from the entry points. It never imports, runs or writes the code it reads.

Each module ends with one status:

  live               reached from an entry point through imports that run
  dynamic_candidate  not live, but its name fits the static start of a dynamic import whose full name
                     is computed at run time, so only running the code can settle it
  type_only          reached only through an import under `if TYPE_CHECKING:`
  test_only          reached only from test files
  dark               reached from nothing
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

STATUSES = ("live", "dynamic_candidate", "type_only", "test_only", "dark")
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "build", "dist", "node_modules", ".tox", ".mypy_cache",
             ".pytest_cache", ".ruff_cache"}
RUNTIME = ("import", "dynamic")


@dataclass(frozen=True)
class Edge:
    """One import as written: its target, its line, how it is made and, for `from x import n`, x.n."""

    target: str
    line: int
    kind: str  # "import", "type_only" or "dynamic"
    member: str | None = None


@dataclass(frozen=True)
class OpenImport:
    """A dynamic import whose full name is computed at run time; prefix is its static start, or ''."""

    line: int
    prefix: str


@dataclass
class Parsed:
    edges: list[Edge] = field(default_factory=list)
    open_imports: list[OpenImport] = field(default_factory=list)
    error: str | None = None


def is_test_path(rel: Path) -> bool:
    """Test files by the usual conventions: test_*.py, *_test.py, conftest.py, or anything under tests/ or test/."""
    name = rel.name
    return (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
            or any(part in ("tests", "test") for part in rel.parts[:-1]))


def _skipped(part: str) -> bool:
    return part in SKIP_DIRS or part.startswith(".") or part.endswith(".egg-info")


def python_files(directory: Path) -> list[Path]:
    """Every .py file under a directory, leaving out caches, virtual environments and hidden folders."""
    return sorted(p for p in directory.rglob("*.py")
                  if not any(_skipped(part) for part in p.relative_to(directory).parts[:-1]))


def module_name(rel: Path) -> str:
    """pkg/sub/mod.py is pkg.sub.mod; pkg/sub/__init__.py is pkg.sub."""
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def discover(root: Path, packages: list[str] | None = None) -> tuple[dict[str, Path], list[Path]]:
    """Modules of the selected top-level packages under root, and the test files among them.

    Without packages, every directory under root that holds an __init__.py is a top-level package.
    A named package may also be a namespace directory or a single module file.
    """
    root = root.resolve()
    if packages is None:
        packages = sorted(p.name for p in root.iterdir()
                          if p.is_dir() and not _skipped(p.name) and (p / "__init__.py").is_file())
    modules: dict[str, Path] = {}
    tests: list[Path] = []
    for package in packages:
        if (root / package).is_dir():
            files = python_files(root / package)
        elif (root / f"{package}.py").is_file():
            files = [root / f"{package}.py"]
        else:
            raise FileNotFoundError(f"no package or module named {package!r} under {root}")
        for path in files:
            rel = path.relative_to(root)
            if is_test_path(rel):
                tests.append(path)
            else:
                modules[module_name(rel)] = path
    return modules, sorted(tests)


def resolve_relative(module: str, is_package: bool, level: int, name: str | None) -> str | None:
    """The absolute name a relative import refers to, or None when it climbs above the top package."""
    if level == 0:
        return name
    base = module.split(".") if is_package else module.split(".")[:-1]
    if level - 1 >= len(base):
        return None
    base = base[:len(base) - (level - 1)]
    return ".".join(base + ([name] if name else []))


def dotted(node: ast.AST) -> str | None:
    """a.b.c for a chain of names and attributes, else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = dotted(node.value)
        return f"{inner}.{node.attr}" if inner else None
    return None


def _is_type_checking(test: ast.AST) -> bool:
    name = dotted(test)
    return name is not None and (name == "TYPE_CHECKING" or name.endswith(".TYPE_CHECKING"))


def static_prefix(node: ast.AST) -> str | None:
    """None for a constant module name; otherwise the constant start of the computed name, possibly ''."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return None
    if isinstance(node, ast.JoinedStr):
        out = ""
        for part in node.values:
            if not (isinstance(part, ast.Constant) and isinstance(part.value, str)):
                break
            out += part.value
        return out
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        left = node.left
        if isinstance(left, ast.Constant) and isinstance(left.value, str):
            return left.value.split("%", 1)[0] if isinstance(node.op, ast.Mod) else left.value
        inner = static_prefix(left)
        return inner or ""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format"
            and isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str)):
        return node.func.value.value.split("{", 1)[0]
    return ""


class _Collector(ast.NodeVisitor):
    def __init__(self, module: str, is_package: bool) -> None:
        self.module, self.is_package = module, is_package
        self.parsed = Parsed()
        self.type_only = 0

    def _kind(self) -> str:
        return "type_only" if self.type_only else "import"

    def visit_If(self, node: ast.If) -> None:
        if not _is_type_checking(node.test):
            self.generic_visit(node)
            return
        self.type_only += 1
        for item in node.body:
            self.visit(item)
        self.type_only -= 1
        for item in node.orelse:
            self.visit(item)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.parsed.edges.append(Edge(alias.name, node.lineno, self._kind()))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = resolve_relative(self.module, self.is_package, node.level, node.module)
        if base is None:
            return
        for alias in node.names:
            member = None if alias.name == "*" else f"{base}.{alias.name}"
            self.parsed.edges.append(Edge(base, node.lineno, self._kind(), member))

    def visit_Call(self, node: ast.Call) -> None:
        name = dotted(node.func) or ""
        if node.args and (name in ("__import__", "import_module") or name.endswith(".import_module")):
            self._dynamic(node)
        self.generic_visit(node)

    def _dynamic(self, node: ast.Call) -> None:
        first = node.args[0]
        prefix = static_prefix(first)
        if prefix is not None:
            self.parsed.open_imports.append(OpenImport(node.lineno, prefix))
            return
        target = first.value
        if not target.startswith("."):
            self.parsed.edges.append(Edge(target, node.lineno, "dynamic"))
            return
        package = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "package"), None)
        if isinstance(package, ast.Constant) and isinstance(package.value, str):
            level = len(target) - len(target.lstrip("."))
            resolved = resolve_relative(package.value, True, level, target.lstrip(".") or None)
            if resolved:
                self.parsed.edges.append(Edge(resolved, node.lineno, "dynamic"))
                return
        self.parsed.open_imports.append(OpenImport(node.lineno, ""))


def parse_imports(path: Path, module: str) -> Parsed:
    """The imports one file makes, read with ast; a file that does not parse records the error instead."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
        return Parsed(error=f"{type(exc).__name__}: {exc}")
    collector = _Collector(module, path.name == "__init__.py")
    collector.visit(tree)
    return collector.parsed


def _with_parents(name: str, known: dict[str, Path]) -> list[str]:
    parts = name.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts) + 1) if ".".join(parts[:i]) in known]


def loaded_by(edge: Edge, known: dict[str, Path]) -> list[str]:
    """Known modules an import loads: the target and its parent packages, and x.n for `from x import n`."""
    found = _with_parents(edge.target, known)
    if edge.member and edge.member in known:
        found.append(edge.member)
    return found


def read_entry_points(pyproject: Path) -> list[str]:
    """Modules named by the [project.scripts], [project.gui-scripts] and [project.entry-points.*] tables."""
    text = pyproject.read_text(encoding="utf-8")
    values: list[str] = []
    try:
        import tomllib  # Python 3.11 or later
    except ModuleNotFoundError:  # Python 3.10: read just these tables line by line
        section = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if line.startswith("["):
                header = line.strip("[]").strip()
                section = header in ("project.scripts", "project.gui-scripts") or header.startswith("project.entry-points.")
            elif section:
                match = re.match(r"^[\"']?[A-Za-z0-9_.-]+[\"']?\s*=\s*[\"']([^\"']+)[\"']", line)
                if match:
                    values.append(match.group(1))
    else:
        project = tomllib.loads(text).get("project", {})
        for table in (project.get("scripts", {}), project.get("gui-scripts", {}), *project.get("entry-points", {}).values()):
            values += [str(value) for value in table.values()]
    return sorted({value.split(":", 1)[0].strip() for value in values if value.strip()})


def find_unused(root: Path, packages: list[str] | None = None, entries: list[str] | None = None,
                test_paths: list[Path] | None = None, pyproject: Path | None = None,
                base: Path | None = None) -> dict:
    """Classify every module of the packages under root.

    Entry points are the ones named, plus any a pyproject.toml declares; with none, every __main__
    module, or else each top-level package. Paths in the result are relative to base (root by default).
    """
    root = root.resolve()
    base = (base or root).resolve()
    modules, inner_tests = discover(root, packages)
    named = [entry.split(":", 1)[0] for entry in (entries or [])]
    if pyproject is not None:
        named += read_entry_points(pyproject)
    if not named:
        named = [m for m in sorted(modules) if m.rsplit(".", 1)[-1] == "__main__"] or [
            m for m in sorted(modules) if "." not in m]
    named = sorted(set(named))

    parsed = {name: parse_imports(path, name) for name, path in modules.items()}
    status: dict[str, str] = {}
    reached_from: dict[str, str] = {}

    def walk(starts: list[tuple[str, str]], label: str) -> None:
        queue = []
        for name, source in starts:
            if name in modules and name not in status:
                status[name], reached_from[name] = label, source
                queue.append(name)
        while queue:
            current = queue.pop(0)
            for edge in sorted(parsed[current].edges, key=lambda e: (e.line, e.target, e.member or "")):
                if edge.kind not in RUNTIME:
                    continue
                for target in loaded_by(edge, modules):
                    if target not in status:
                        status[target], reached_from[target] = label, current
                        queue.append(target)

    starts = []
    for entry in named:
        parents = _with_parents(entry, modules)
        starts += [(name, "entry point" if name == entry else entry) for name in parents]
    walk(starts, "live")

    open_rows = [{"module": name, "line": item.line, "prefix": item.prefix}
                 for name in sorted(n for n, s in status.items() if s == "live") for item in parsed[name].open_imports]
    starts = []
    for row in open_rows:
        if row["prefix"]:
            stem = row["prefix"].rstrip(".")
            for name in sorted(modules):
                if name == stem or name.startswith(row["prefix"]):
                    starts += [(parent, row["module"]) for parent in _with_parents(name, modules)]
    walk(starts, "dynamic_candidate")

    walk([(target, name) for name in sorted(status) for edge in parsed[name].edges if edge.kind == "type_only"
          for target in loaded_by(edge, modules)], "type_only")

    files = []
    for path in sorted({*(p.resolve() for p in (test_paths or [])), *(p.resolve() for p in inner_tests)}):
        files += python_files(path) if path.is_dir() else [path]
    starts, errors = [], []
    for path in files:
        name = module_name(path.relative_to(root)) if path.is_relative_to(root) else path.stem
        result = parse_imports(path, name)
        if result.error:
            errors.append({"path": _show(path, base), "error": result.error})
        for edge in sorted(result.edges, key=lambda e: (e.line, e.target, e.member or "")):
            if edge.kind in RUNTIME:
                starts += [(target, _show(path, base)) for target in loaded_by(edge, modules)]
    walk(starts, "test_only")

    rows = [{"module": name, "path": _show(modules[name], base), "status": status.get(name, "dark"),
             "reached_from": reached_from.get(name)} for name in sorted(modules)]
    unparsed = [{"path": _show(modules[name], base), "error": p.error} for name, p in sorted(parsed.items()) if p.error]
    unparsed += errors
    return {
        "entries": named,
        "missing_entries": [entry for entry in named if entry not in modules],
        "modules": rows,
        "counts": {s: sum(1 for row in rows if row["status"] == s) for s in STATUSES},
        "open_dynamic_imports": open_rows,
        "unparsed": unparsed,
        "graph": "open" if open_rows or unparsed else "closed",
    }


def _show(path: Path, base: Path) -> str:
    path = path.resolve()
    return path.relative_to(base).as_posix() if path.is_relative_to(base) else path.as_posix()
