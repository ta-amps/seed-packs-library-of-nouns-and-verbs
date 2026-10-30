"""The ager finds markers only in comments, ages them by git blame's author time, and says unknown otherwise."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import gitrepo
from health_checks import age_todos, bucket, markers, parse_porcelain

PORCELAIN = """\
1111111111111111111111111111111111111111 1 1 2
author Synthetic Author
author-mail <synthetic@example.invalid>
author-time 1717408800
author-tz +0000
committer Synthetic Author
committer-time 1717408800
summary first
filename roster/sync.py
\timport os
1111111111111111111111111111111111111111 2 2
\t# TODO: retry
2222222222222222222222222222222222222222 3 3 1
author Synthetic Author
author-time 1777000000
summary second
filename roster/sync.py
\tx = 1
0000000000000000000000000000000000000000 4 4 1
author Not Committed Yet
author-time 1800000000
filename roster/sync.py
\t# FIXME: new
"""


class Markers(unittest.TestCase):
    def test_only_comments_count_in_python(self) -> None:
        found = markers(Path("a.py"), 's = "TODO: in a string"  # TODO(ops): real #12\n# todo lowercase\nTODOS = 1\n# FIXME\n')
        self.assertEqual([(m["line"], m["marker"], m["owner"], m["has_ref"]) for m in found],
                         [(1, "TODO", "ops", True), (4, "FIXME", None, False)])

    def test_python_that_does_not_tokenize_falls_back_to_lines(self) -> None:
        found = markers(Path("a.py"), 'x = (\n# TODO: unclosed\n')
        self.assertEqual([m["line"] for m in found], [2])

    def test_slash_block_hash_dash_and_markup_comments(self) -> None:
        js = 'const u = "https://x//TODO"; // TODO: debounce\n/* FIXME: block\n still XXX */ go();\nlet t = `// HACK no`;\n'
        self.assertEqual([(m["line"], m["marker"]) for m in markers(Path("a.js"), js)], [(1, "TODO"), (2, "FIXME"), (3, "XXX")])
        yml = 'key: "#TODO not" # HACK: pinned see https://example.invalid/1\nurl: a#TODO\n'
        found = markers(Path("a.yml"), yml)
        self.assertEqual([(m["marker"], m["has_ref"]) for m in found], [("HACK", True)])
        self.assertEqual([m["marker"] for m in markers(Path("q.sql"), "select '--TODO' -- XXX remove\n")], ["XXX"])
        self.assertEqual([m["line"] for m in markers(Path("README.md"), "TODO in prose\n<!-- TODO: comment -->\n")], [2])
        self.assertEqual([m["marker"] for m in markers(Path("Makefile"), "all: # TODO split\n")], ["TODO"])
        self.assertEqual(markers(Path("photo.png"), "# TODO"), [])

    def test_line_numbers_count_newlines_only(self) -> None:
        text = "x = 1\n\f\n# TODO: after a form feed\n"
        self.assertEqual([m["line"] for m in markers(Path("a.py"), text)], [3])
        self.assertEqual([m["line"] for m in markers(Path("a.js"), "a();\f b();\n// TODO: next\n")], [2])

    def test_references_and_owners(self) -> None:
        refs = [m["has_ref"] for m in markers(Path("a.py"), "# TODO: see ABC-123\n# TODO: see #7\n# TODO: someday\n")]
        self.assertEqual(refs, [True, True, False])


class Blame(unittest.TestCase):
    def test_porcelain_maps_lines_to_author_times(self) -> None:
        lines = parse_porcelain(PORCELAIN)
        self.assertEqual({n: e["author_time"] for n, e in lines.items()}, {1: 1717408800, 2: 1717408800, 3: 1777000000, 4: 1800000000})
        self.assertEqual(lines[4]["commit"], "0" * 40)

    def test_buckets(self) -> None:
        self.assertEqual([bucket(d) for d in (0, 29, 30, 89, 90, 364, 365, 4000, None, -1)],
                         ["fresh", "fresh", "aging", "aging", "stale", "stale", "ancient", "ancient", "unknown", "unknown"])


@unittest.skipIf(not gitrepo.HAVE_GIT and not gitrepo.REQUIRE_GIT, "git is not installed")
class WithGit(unittest.TestCase):
    def setUp(self) -> None:
        if not gitrepo.HAVE_GIT:
            self.fail("HEALTH_CHECKS_REQUIRE_GIT=1 but git is not installed")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        patcher = mock.patch.dict(os.environ, gitrepo.ISOLATED)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_ages_come_from_the_line_that_holds_the_marker(self) -> None:
        gitrepo.build(self.root, [
            {"date": "2024-06-03T10:00:00Z", "files": {"app.py": "import os\n# TODO: old one\n"}},
            {"date": "2026-10-20T10:00:00Z", "files": {"app.py": "import os\n# TODO: old one\nx = 1  # FIXME: new one\n"}},
        ])
        result = age_todos(self.root, date(2026, 10, 30))
        self.assertTrue(result["git"])
        got = {(i["line"], i["authored_on"], i["age_days"], i["bucket"], i["age_source"]) for i in result["items"]}
        self.assertEqual(got, {(2, "2024-06-03", 879, "ancient", "git_blame"), (3, "2026-10-20", 10, "fresh", "git_blame")})
        self.assertEqual(result["items"][0]["line"], 2, "oldest first")
        self.assertEqual(result["counts"], {"fresh": 1, "aging": 0, "stale": 0, "ancient": 1, "unknown": 0})

    def test_uncommitted_and_untracked_lines_have_no_age(self) -> None:
        gitrepo.build(self.root, [{"date": "2025-01-01T00:00:00Z", "files": {"app.py": "# TODO: kept\n"}}])
        (self.root / "app.py").write_text("# TODO: kept\n# TODO: edited now\n", encoding="utf-8")
        (self.root / "new.py").write_text("# HACK: never committed\n", encoding="utf-8")
        items = {(i["path"], i["line"]): i for i in age_todos(self.root, date(2026, 10, 30))["items"]}
        self.assertEqual(items[("app.py", 1)]["bucket"], "ancient")
        self.assertEqual((items[("app.py", 2)]["age_days"], items[("app.py", 2)]["age_reason"]), (None, "the line is not committed yet"))
        self.assertIsNone(items[("new.py", 1)]["age_days"])
        self.assertIn("may not be committed", items[("new.py", 1)]["age_reason"])

    def test_a_shallow_clone_never_dates_a_line_by_its_cut_off_commit(self) -> None:
        full = gitrepo.build(self.root, [
            {"date": "2024-01-01T00:00:00Z", "files": {"a.py": "# TODO: old\n"}},
            {"date": "2026-10-01T00:00:00Z", "files": {"a.py": "# TODO: old\nx = 1  # TODO: new\n"}},
        ])
        whole = {i["line"]: i for i in age_todos(full, date(2026, 10, 30))["items"]}
        self.assertEqual((whole[1]["authored_on"], whole[2]["authored_on"]), ("2024-01-01", "2026-10-01"), "a true root commit dates its lines")
        shallow = Path(self.tmp.name) / "shallow"
        gitrepo.git(Path(self.tmp.name), "clone", "-q", "--depth", "1", full.resolve().as_uri(), str(shallow))
        result = age_todos(shallow, date(2026, 10, 30))
        self.assertTrue(result["shallow"])
        items = {i["line"]: i for i in result["items"]}
        self.assertEqual((items[1]["age_days"], items[1]["bucket"]), (None, "unknown"))
        self.assertIn("shallow", items[1]["age_reason"])
        self.assertEqual((items[2]["age_days"], items[2]["bucket"]), (None, "unknown"), "every line of the cut-off commit is unknown")

    def test_an_as_of_date_before_the_commit_is_not_an_age(self) -> None:
        gitrepo.build(self.root, [{"date": "2026-10-20T10:00:00Z", "files": {"app.py": "# TODO: later\n"}}])
        item = age_todos(self.root, date(2026, 1, 1))["items"][0]
        self.assertEqual((item["age_days"], item["bucket"]), (None, "unknown"))
        self.assertIn("after the as-of date", item["age_reason"])


class WithoutGit(unittest.TestCase):
    def test_no_git_means_unknown_and_modification_times_are_never_used(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "old.py"
            path.write_text("# TODO: looks old\n", encoding="utf-8")
            os.utime(path, (0, 0))
            result = age_todos(root, date(2026, 10, 30), use_git=False)
            item = result["items"][0]
            self.assertEqual((item["age_days"], item["bucket"], item["age_source"]), (None, "unknown", "none"))
            self.assertEqual(result["git_reason"], "git was not used")

    def test_files_that_are_not_utf8_are_listed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "latin.py").write_bytes(b"# TODO: caf\xe9\n")
            result = age_todos(root, date(2026, 10, 30), use_git=False)
            self.assertEqual(result["unreadable"], [{"path": "latin.py", "error": "UnicodeDecodeError"}])
            self.assertEqual(result["count"], 0)

    def test_tool_folders_and_excluded_globs_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in ("src/a.py", "node_modules/x/b.js", ".venv/c.py", "vendor/d.py", "gen/e.py"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("# TODO: here\n" if rel.endswith(".py") else "// TODO: here\n", encoding="utf-8")
            paths = [i["path"] for i in age_todos(root, date(2026, 10, 30), use_git=False, exclude=["gen/*"])["items"]]
            self.assertEqual(paths, ["src/a.py"])


if __name__ == "__main__":
    unittest.main()
