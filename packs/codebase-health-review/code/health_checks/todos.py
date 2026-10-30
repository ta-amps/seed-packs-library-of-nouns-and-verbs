"""Find TODO, FIXME, XXX and HACK markers in comments and age each one by the date git blame gives its line.

Only comments count: Python is read with the tokenize module, so a marker inside a string is never a
finding, and other languages are read line by line with quote-aware comment detection. An age comes
from the author time git blame reports for the marker's line, or it is unknown with the reason: not
committed, not in git, or cut off at a shallow clone's boundary. A file's modification time is never
used as an age, and files that cannot be read as UTF-8 are listed, never skipped silently.
"""

from __future__ import annotations

import fnmatch
import io
import os
import re
import shutil
import subprocess
import tokenize
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MARKER = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b(?:\(([^)\n]{1,40})\))?:?[ \t]*(.*)")
REFERENCE = re.compile(r"(?:#[0-9]+\b|\b[A-Z][A-Z0-9]+-[0-9]+\b|https?://\S+)")
BUCKETS = (("fresh", 0, 29), ("aging", 30, 89), ("stale", 90, 364), ("ancient", 365, None))
SKIP_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "__pycache__", ".tox", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", "build", "dist", "vendor", "third_party"}
HASH = {".py", ".pyi", ".sh", ".bash", ".zsh", ".rb", ".pl", ".r", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".tf",
        ".mk", ".dockerfile"}
HASH_NAMES = {"Makefile", "Dockerfile", "Gemfile", "Rakefile"}
SLASH = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".kts", ".swift", ".c", ".h",
         ".cc", ".cpp", ".hpp", ".cs", ".scala", ".php", ".css", ".scss", ".less", ".dart"}
DASH = {".sql", ".lua", ".hs"}
MARKUP = {".html", ".htm", ".xml", ".svg", ".md", ".vue"}
UNCOMMITTED = "0" * 40
BLAME_HEADER = re.compile(r"^([0-9a-f]{40}) [0-9]+ ([0-9]+)(?: [0-9]+)?$")
GIT_ENV = {"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}


def style(path: Path) -> str | None:
    """The comment style for a file, or None when this scanner does not read it."""
    if path.name in HASH_NAMES:
        return "hash"
    suffix = path.suffix.lower()
    for name, suffixes in (("hash", HASH), ("slash", SLASH), ("dash", DASH), ("markup", MARKUP)):
        if suffix in suffixes:
            return name
    return None


def python_comments(text: str) -> list[tuple[int, str]] | None:
    """Comment tokens with their line numbers, or None when the file does not tokenize."""
    try:
        return [(tok.start[0], tok.string[1:]) for tok in tokenize.generate_tokens(io.StringIO(text).readline)
                if tok.type == tokenize.COMMENT]
    except (tokenize.TokenError, SyntaxError):
        return None


def line_comments(text: str, kind: str) -> list[tuple[int, str]]:
    """Comments found line by line, outside single, double and back quotes; block comments may span lines."""
    opener = {"hash": "#", "slash": "//", "dash": "--"}.get(kind)
    block = {"slash": ("/*", "*/"), "markup": ("<!--", "-->")}.get(kind)
    quotes = "" if kind == "markup" else "\"'`"
    out: list[tuple[int, str]] = []
    in_block = False
    for number, line in enumerate(text.split("\n"), start=1):
        line = line[:-1] if line.endswith("\r") else line
        i, quote = 0, None
        while i < len(line):
            if in_block:
                end = line.find(block[1], i)
                out.append((number, line[i:] if end < 0 else line[i:end]))
                if end < 0:
                    break
                in_block, i = False, end + len(block[1])
                continue
            ch = line[i]
            if quote:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in quotes:
                quote = ch
            elif block and line.startswith(block[0], i):
                in_block, i = True, i + len(block[0])
                continue
            elif opener and line.startswith(opener, i) and (kind != "hash" or i == 0 or line[i - 1] in " \t"):
                out.append((number, line[i + len(opener):]))
                break
            i += 1
    return out


def comments(path: Path, text: str) -> list[tuple[int, str]]:
    kind = style(path)
    if kind is None:
        return []
    if path.suffix.lower() in (".py", ".pyi"):
        found = python_comments(text)
        if found is not None:
            return found
    return line_comments(text, kind)


def markers(path: Path, text: str) -> list[dict[str, Any]]:
    """Every marker in the file's comments: line, marker word, owner in parentheses, text and a reference flag."""
    out = []
    for number, comment in comments(path, text):
        match = MARKER.search(comment)
        if match:
            rest = match.group(3).strip()
            owner = match.group(2).strip() if match.group(2) else None
            out.append({"line": number, "marker": match.group(1), "owner": owner, "text": rest[:160],
                        "has_ref": bool(owner or REFERENCE.search(rest))})
    return out


def parse_porcelain(text: str) -> dict[int, dict[str, Any]]:
    """Final line number to {commit, author_time, boundary} from `git blame --porcelain` output.

    git marks a root commit as boundary. In a full clone that is the true first commit; in a shallow clone
    it is where the history was cut off, and the lines blamed on it may be older.
    """
    commits: dict[str, dict[str, Any]] = {}
    lines: dict[int, dict[str, Any]] = {}
    current: str | None = None
    for raw in text.splitlines():
        header = BLAME_HEADER.match(raw)
        if header:
            current = header.group(1)
            commits.setdefault(current, {})
            lines[int(header.group(2))] = {"commit": current}
        elif current is not None and raw.startswith("author-time "):
            commits[current]["author_time"] = int(raw.split(" ", 1)[1])
        elif current is not None and raw == "boundary":
            commits[current]["boundary"] = True
    return {n: {**entry, "author_time": commits[entry["commit"]].get("author_time"),
                "boundary": commits[entry["commit"]].get("boundary", False)} for n, entry in lines.items()}


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a read-only git command: no optional locks, no prompts, no network."""
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False, timeout=120,
                          env={**os.environ, **GIT_ENV})


def is_shallow(top: Path) -> bool:
    done = git(["rev-parse", "--is-shallow-repository"], top)
    return done.returncode == 0 and done.stdout.strip() == "true"


def git_top(root: Path) -> tuple[Path | None, str | None]:
    """The work tree's top folder, or None with the reason no age can come from git."""
    if shutil.which("git") is None:
        return None, "git is not installed"
    done = git(["rev-parse", "--show-toplevel"], root if root.is_dir() else root.parent)
    if done.returncode != 0:
        return None, "not inside a git work tree"
    return Path(done.stdout.strip()).resolve(), None


def blame(top: Path, path: Path) -> tuple[dict[int, dict[str, Any]] | None, str | None]:
    done = git(["blame", "--porcelain", "--", path.resolve().relative_to(top).as_posix()], top)
    if done.returncode != 0:
        return None, "git blame could not read the file; it may not be committed"
    return parse_porcelain(done.stdout), None


def bucket(days: int | None) -> str:
    if days is None or days < 0:
        return "unknown"
    return next(name for name, low, high in BUCKETS if days >= low and (high is None or days <= high))


def files_under(root: Path, exclude: Iterable[str] = ()) -> list[Path]:
    """Files this scanner reads, skipping tool and dependency folders, symbolic links and excluded globs."""
    patterns = list(exclude)
    if root.is_file():
        return [root] if style(root) else []
    found = []
    for item in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = item.relative_to(root)
        if set(rel.parts[:-1]) & SKIP_DIRS or item.is_symlink() or style(item) is None:
            continue
        if any(fnmatch.fnmatch(rel.as_posix(), p) for p in patterns):
            continue
        found.append(item)
    return found


def age_todos(root: Path, as_of: date, use_git: bool = True, exclude: Iterable[str] = ()) -> dict[str, Any]:
    """Every marker under one root, with its age in days as of a date, its bucket and how the age is known."""
    root = Path(root)
    top, no_git = git_top(root) if use_git else (None, "git was not used")
    base = top or (root if root.is_dir() else root.parent).resolve()
    shallow = bool(top) and is_shallow(top)
    items: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []
    for path in files_under(root, exclude):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            unreadable.append({"path": path.resolve().relative_to(base).as_posix(), "error": type(exc).__name__})
            continue
        found = markers(path, text)
        if not found:
            continue
        lines, reason = blame(top, path) if top else (None, no_git)
        shown = path.resolve().relative_to(base).as_posix()
        for item in found:
            entry = (lines or {}).get(item["line"])
            authored, why = None, reason
            if entry is not None and entry["commit"] == UNCOMMITTED:
                why = "the line is not committed yet"
            elif entry is not None and entry["boundary"] and shallow:
                why = "the clone is shallow and the line is blamed on the commit where its history is cut off, so it may be older"
            elif entry is not None and entry["author_time"] is not None:
                authored = datetime.fromtimestamp(entry["author_time"], tz=timezone.utc).date()
            elif lines is not None:
                why = "git blame gave no author time for the line"
            days = (as_of - authored).days if authored else None
            if days is not None and days < 0:
                why = "the line was authored after the as-of date"
            known = days is not None and days >= 0
            items.append({"path": shown, **item, "authored_on": authored.isoformat() if authored else None,
                          "age_days": days if known else None, "bucket": bucket(days),
                          "age_source": "git_blame" if known else "none", "age_reason": None if known else why})
    items.sort(key=lambda i: (i["age_days"] is None, -(i["age_days"] or 0), i["path"], i["line"]))
    counts = {name: sum(1 for i in items if i["bucket"] == name) for name, _, _ in BUCKETS}
    counts["unknown"] = sum(1 for i in items if i["bucket"] == "unknown")
    return {"as_of": as_of.isoformat(), "git": top is not None, "git_reason": None if top else no_git,
            "shallow": shallow, "unreadable": unreadable,
            "buckets": {name: [low, high] for name, low, high in BUCKETS}, "count": len(items), "counts": counts,
            "without_ref": sum(1 for i in items if not i["has_ref"]), "items": items}
