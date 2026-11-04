"""Build a throwaway git repository with commits at fixed author dates, for the ager's tests.

Git runs isolated from the machine's own settings. Without git, tests that need it skip, unless
HEALTH_CHECKS_REQUIRE_GIT=1, as in CI, which makes a missing git a failure.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

REQUIRE_GIT = os.environ.get("HEALTH_CHECKS_REQUIRE_GIT") == "1"
HAVE_GIT = shutil.which("git") is not None
ISOLATED = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}


def git(cwd: Path, *args: str, when: str | None = None) -> None:
    env = {**os.environ, **ISOLATED}
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "-c", "user.name=Made-up Author", "-c", "user.email=made-up@example.invalid",
                    "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
                   cwd=cwd, env=env, check=True, capture_output=True, text=True)


def build(root: Path, commits: Iterable[dict]) -> Path:
    """commits: [{"date": "2025-08-20T10:00:00Z", "files": {"path": "text"}}], applied in order."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    for commit in commits:
        for rel, text in commit["files"].items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", commit.get("message", "made-up commit"), when=commit["date"])
    return root
