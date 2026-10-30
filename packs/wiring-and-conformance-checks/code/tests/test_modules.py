"""The unused-module finder: names, relative imports, computed names, statuses and entry points."""

from __future__ import annotations

import ast
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from wiring_checks import discover, find_unused, read_entry_points, resolve_relative, static_prefix

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pantry"


def write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")


def statuses(result: dict) -> dict[str, str]:
    return {row["module"]: row["status"] for row in result["modules"]}


def run_tree(files: dict[str, str], **kwargs) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_tree(root, files)
        return find_unused(root, **kwargs)


class Names(unittest.TestCase):
    def test_relative_imports_resolve_like_python(self) -> None:
        self.assertEqual(resolve_relative("a.b.c", False, 1, "d"), "a.b.d")
        self.assertEqual(resolve_relative("a.b.c", False, 2, None), "a")
        self.assertIsNone(resolve_relative("a.b.c", False, 3, None), "climbs above the top package")
        self.assertEqual(resolve_relative("a.b", True, 1, "c"), "a.b.c")
        self.assertEqual(resolve_relative("a.b", True, 2, "c"), "a.c")
        self.assertEqual(resolve_relative("a", True, 1, None), "a")
        self.assertIsNone(resolve_relative("a", False, 1, None), "a top-level module has no package")
        self.assertEqual(resolve_relative("x", False, 0, "y.z"), "y.z")

    def test_static_prefix_of_computed_names(self) -> None:
        def prefix(expression: str):
            return static_prefix(ast.parse(expression, mode="eval").body)

        self.assertIsNone(prefix("'a.b'"))
        self.assertEqual(prefix("f'a.plugins.{name}'"), "a.plugins.")
        self.assertEqual(prefix("'a.plugins.' + name"), "a.plugins.")
        self.assertEqual(prefix("'a.' + kind + '.x'"), "a.")
        self.assertEqual(prefix("'a.%s' % name"), "a.")
        self.assertEqual(prefix("'a.{}'.format(name)"), "a.")
        self.assertEqual(prefix("name"), "")
        self.assertEqual(prefix("f'{name}.plugins'"), "")

    def test_discover_keeps_tests_apart_and_skips_caches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_tree(root, {
                "app/__init__.py": "", "app/core.py": "", "app/tests/test_core.py": "", "app/conftest.py": "",
                "app/core_test.py": "", "app/__pycache__/core.py": "", "app/.hidden/x.py": "",
                "app/ns/thing.py": "", "loose.py": "", "plain/x.py": "",
            })
            modules, tests = discover(root)
            self.assertEqual(sorted(modules), ["app", "app.core", "app.ns.thing"])
            self.assertEqual([t.relative_to(root.resolve()).as_posix() for t in tests],
                             ["app/conftest.py", "app/core_test.py", "app/tests/test_core.py"])
            modules, _ = discover(root, ["loose", "plain"])
            self.assertEqual(sorted(modules), ["loose", "plain.x"], "a single module and a namespace folder")
            with self.assertRaises(FileNotFoundError):
                discover(root, ["missing"])


class PantryApp(unittest.TestCase):
    def test_every_status_is_found(self) -> None:
        result = find_unused(FIXTURE / "src", test_paths=[FIXTURE / "tests"], base=FIXTURE)
        got = statuses(result)
        self.assertEqual(result["entries"], ["pantry_app.__main__"])
        self.assertEqual({m for m, s in got.items() if s == "dark"}, {"pantry_app.legacy_export", "pantry_app.plugins.fax"})
        self.assertEqual(got["pantry_app.reports"], "test_only")
        self.assertEqual(got["pantry_app._types"], "type_only")
        self.assertEqual({m for m, s in got.items() if s == "dynamic_candidate"},
                         {"pantry_app.exporters", "pantry_app.exporters.csv_out"})
        self.assertEqual(got["pantry_app.plugins.sms"], "live", "a string-literal importlib call is an import")
        self.assertEqual(got["pantry_app.plugins"], "live", "importing a submodule loads its package")
        self.assertEqual(result["counts"], {"live": 11, "dynamic_candidate": 2, "type_only": 1, "test_only": 1, "dark": 2})
        self.assertEqual(result["open_dynamic_imports"],
                         [{"module": "pantry_app.cli", "line": 11, "prefix": "pantry_app.exporters."}])
        self.assertEqual(result["graph"], "open", "a computed import name leaves the graph open")
        rows = {row["module"]: row for row in result["modules"]}
        self.assertEqual(rows["pantry_app.__main__"]["reached_from"], "entry point")
        self.assertEqual(rows["pantry_app.reports"]["reached_from"], "tests/test_reports.py")
        self.assertEqual(rows["pantry_app.cli"]["path"], "src/pantry_app/cli.py")

    def test_without_its_tests_the_test_only_module_is_dark(self) -> None:
        self.assertEqual(statuses(find_unused(FIXTURE / "src", base=FIXTURE))["pantry_app.reports"], "dark")

    def test_a_named_entry_replaces_the_defaults(self) -> None:
        result = find_unused(FIXTURE / "src", entries=["pantry_app.routes:book"], base=FIXTURE)
        got = statuses(result)
        self.assertEqual(result["entries"], ["pantry_app.routes"])
        self.assertEqual((got["pantry_app.routes"], got["pantry_app.cli"], got["pantry_app.__main__"]), ("live", "dark", "dark"))
        self.assertEqual(got["pantry_app.exporters"], "dark", "the computed import is in cli, which is not live here")
        self.assertEqual(result["graph"], "closed")

    def test_a_missing_entry_is_reported(self) -> None:
        result = find_unused(FIXTURE / "src", entries=["pantry_app.server"], base=FIXTURE)
        self.assertEqual(result["missing_entries"], ["pantry_app.server"])


class Imports(unittest.TestCase):
    def test_from_imports_of_submodules_and_star(self) -> None:
        got = statuses(run_tree({
            "app/__init__.py": "from . import a\nfrom .b import *\n",
            "app/a.py": "from .sub import thing\n",
            "app/b.py": "",
            "app/sub/__init__.py": "from .thing import value\n",
            "app/sub/thing.py": "value = 1\n",
            "app/sub/other.py": "",
        }, entries=["app"]))
        self.assertEqual(got, {"app": "live", "app.a": "live", "app.b": "live", "app.sub": "live",
                               "app.sub.thing": "live", "app.sub.other": "dark"})

    def test_importlib_with_a_package_and_dunder_import(self) -> None:
        result = run_tree({
            "app/__init__.py": ("import importlib\nPLUGIN = importlib.import_module('.plug', package='app')\n"
                                "ONE = __import__('app.one')\nLATER = __import__(name)\n"),
            "app/plug.py": "", "app/one.py": "", "app/never.py": "",
        }, entries=["app"])
        got = statuses(result)
        self.assertEqual((got["app.plug"], got["app.one"], got["app.never"]), ("live", "live", "dark"))
        self.assertEqual(result["open_dynamic_imports"], [{"module": "app", "line": 4, "prefix": ""}])
        self.assertEqual(result["graph"], "open")

    def test_type_checking_imports_do_not_make_modules_live(self) -> None:
        got = statuses(run_tree({
            "app/__init__.py": ("import typing\nif typing.TYPE_CHECKING:\n    from .types import T\n"
                                "else:\n    from .runtime import R\n"),
            "app/types.py": "from .helpers import h\n",
            "app/helpers.py": "",
            "app/runtime.py": "",
        }, entries=["app"]))
        self.assertEqual(got, {"app": "live", "app.runtime": "live", "app.types": "type_only", "app.helpers": "type_only"})

    def test_imports_inside_functions_count(self) -> None:
        got = statuses(run_tree({"app/__init__.py": "def load():\n    from . import lazy\n    return lazy\n",
                                 "app/lazy.py": ""}, entries=["app"]))
        self.assertEqual(got["app.lazy"], "live")

    def test_an_unparsable_file_is_reported_not_guessed(self) -> None:
        result = run_tree({"app/__init__.py": "from . import ok\n", "app/ok.py": "", "app/broken.py": "def (:\n"},
                          entries=["app"])
        self.assertEqual([row["path"] for row in result["unparsed"]], ["app/broken.py"])
        self.assertEqual(statuses(result)["app.broken"], "dark")
        self.assertEqual(result["graph"], "open")

    def test_default_entries_are_main_modules_or_top_packages(self) -> None:
        result = run_tree({"lib/__init__.py": "from . import core\n", "lib/core.py": "", "lib/extra.py": ""})
        self.assertEqual(result["entries"], ["lib"])
        self.assertEqual(statuses(result), {"lib": "live", "lib.core": "live", "lib.extra": "dark"})
        self.assertEqual(result["graph"], "closed")

    def test_tests_inside_a_package_reach_modules(self) -> None:
        got = statuses(run_tree({"app/__init__.py": "", "app/util.py": "",
                                 "app/tests/test_util.py": "from app import util\n"}, entries=["app"]))
        self.assertEqual(got, {"app": "live", "app.util": "test_only"})

    def test_the_finder_never_imports_what_it_reads(self) -> None:
        before = set(sys.modules)
        result = run_tree({"boom/__init__.py": "raise SystemExit('this module must never run')\n",
                           "boom/inner.py": "import os\nos.remove('anything')\n"})
        self.assertEqual(statuses(result), {"boom": "live", "boom.inner": "dark"})
        self.assertFalse({"boom", "boom.inner"} & (set(sys.modules) - before))


class EntryPoints(unittest.TestCase):
    TEXT = textwrap.dedent("""\
        [project]
        name = "app"
        [project.scripts]
        app = "app.cli:main"   # the command
        app-admin = 'app.admin:run'
        [project.gui-scripts]
        app-gui = "app.gui"
        [project.entry-points."app.plugins"]
        sms = "app.plugins.sms:Plugin"
        [tool.other]
        x = "not.an.entry:point"
        """)
    EXPECTED = ["app.admin", "app.cli", "app.gui", "app.plugins.sms"]

    def read(self) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pyproject.toml"
            path.write_text(self.TEXT, encoding="utf-8")
            return read_entry_points(path)

    def test_scripts_and_entry_point_tables(self) -> None:
        self.assertEqual(self.read(), self.EXPECTED)

    def test_the_reader_without_tomllib_agrees(self) -> None:
        with mock.patch.dict(sys.modules, {"tomllib": None}):
            self.assertEqual(self.read(), self.EXPECTED)

    def test_pyproject_entries_join_named_ones(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_tree(root, {"src/app/__init__.py": "", "src/app/cli.py": "from . import core\n", "src/app/core.py": "",
                              "src/app/admin.py": "", "src/app/gui.py": "", "src/app/plugins/__init__.py": "",
                              "src/app/plugins/sms.py": "", "src/app/old.py": ""})
            (root / "pyproject.toml").write_text(self.TEXT, encoding="utf-8")
            result = find_unused(root / "src", pyproject=root / "pyproject.toml")
            self.assertEqual(result["entries"], self.EXPECTED)
            self.assertEqual([row["module"] for row in result["modules"] if row["status"] == "dark"], ["app.old"])


if __name__ == "__main__":
    unittest.main()
