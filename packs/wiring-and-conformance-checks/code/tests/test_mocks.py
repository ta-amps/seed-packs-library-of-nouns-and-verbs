"""The patch-target scan and behavior coverage: every patch form, names resolved through imports."""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from wiring_checks import check_behaviors, hits_path, scan_tests

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pantry"


def scan_text(text: str) -> dict[str, list[str]]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "test_sample.py"
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return {row["id"].split("::", 1)[1]: row["patched"] for row in scan_tests([path], Path(directory))}


class PatchForms(unittest.TestCase):
    def test_decorators_with_statements_and_started_patchers(self) -> None:
        got = scan_text("""
            from unittest import mock
            from unittest.mock import patch
            import unittest.mock as um

            @mock.patch("app.a.one")
            def test_decorated(one):
                pass

            def test_with():
                with patch("app.b.two") as two, um.patch("app.b.three"):
                    pass

            def test_started():
                patcher = mock.patch("app.c.four")
                patcher.start()
        """)
        self.assertEqual(got, {"test_decorated": ["app.a.one"], "test_with": ["app.b.three", "app.b.two"],
                               "test_started": ["app.c.four"]})

    def test_object_dict_and_multiple_resolve_through_imports(self) -> None:
        got = scan_text("""
            from unittest import mock
            from app import store as storage
            from app.store import Store
            import app.config

            def test_object():
                with mock.patch.object(Store, "save"), mock.patch.object(storage.Store, attribute="load"):
                    pass

            def test_dict():
                with mock.patch.dict("app.config.SETTINGS", {"x": 1}), mock.patch.dict(app.config.ENV, {}):
                    pass

            @mock.patch.multiple("app.mail", send=mock.DEFAULT, queue=mock.DEFAULT)
            def test_multiple(send, queue):
                pass
        """)
        self.assertEqual(got["test_object"], ["app.store.Store.load", "app.store.Store.save"])
        self.assertEqual(got["test_dict"], ["app.config.ENV", "app.config.SETTINGS"])
        self.assertEqual(got["test_multiple"], ["app.mail.queue", "app.mail.send"])

    def test_class_decorators_and_set_up_apply_to_every_test(self) -> None:
        got = scan_text("""
            import unittest
            from unittest import mock

            @mock.patch("app.clock.now")
            class TimedTests(unittest.TestCase):
                def setUp(self):
                    self.addCleanup(mock.patch.stopall)
                    mock.patch("app.net.fetch").start()

                def test_one(self, now):
                    pass

                def test_two(self, now):
                    with mock.patch("app.disk.read"):
                        pass

                def helper(self):
                    mock.patch("app.never.counted").start()

            class NotATest:
                def test_ignored(self):
                    mock.patch("app.ignored").start()
        """)
        self.assertEqual(got, {"TimedTests::test_one": ["app.clock.now", "app.net.fetch"],
                               "TimedTests::test_two": ["app.clock.now", "app.disk.read", "app.net.fetch"]})

    def test_monkeypatch_and_fixtures_that_patch(self) -> None:
        got = scan_text("""
            import pytest
            from app import mailer

            @pytest.fixture
            def no_mail(monkeypatch):
                monkeypatch.setattr(mailer, "send", lambda *args: None)

            @pytest.fixture()
            def quiet(no_mail, monkeypatch):
                monkeypatch.setattr("app.log.write", print)

            def test_signup(quiet):
                pass

            def test_env(monkeypatch):
                monkeypatch.delattr("app.config.CACHE")

            def test_plain():
                pass
        """)
        self.assertEqual(got, {"test_signup": ["app.log.write", "app.mailer.send"], "test_env": ["app.config.CACHE"],
                               "test_plain": []})

    def test_aliases_and_star_imports(self) -> None:
        self.assertEqual(scan_text("""
            from unittest.mock import patch as replace

            def test_alias():
                with replace("app.x"):
                    pass
        """), {"test_alias": ["app.x"]})
        self.assertEqual(scan_text("""
            from unittest.mock import *

            def test_star():
                with patch.object(Thing, "y"):
                    pass
        """), {"test_star": ["Thing.y"]})

    def test_an_http_patch_request_is_not_a_mock(self) -> None:
        self.assertEqual(scan_text("""
            import requests

            def test_client(client):
                client.patch("/slots/1", json={})
                requests.patch("https://example.invalid/x")
        """), {"test_client": []})


class Coverage(unittest.TestCase):
    def test_hits_path(self) -> None:
        self.assertTrue(hits_path("a.b.C.save", "a.b.C.save"))
        self.assertTrue(hits_path("a.b.C", "a.b.C.save"), "patching the class replaces its methods")
        self.assertTrue(hits_path("a.b.C.save.cache", "a.b.C.save"))
        self.assertFalse(hits_path("a.b.C.saved", "a.b.C.save"))
        self.assertFalse(hits_path("a.b.D", "a.b.C.save"))

    def test_statuses(self) -> None:
        tests = [{"id": "t::a", "patched": ["app.store.save"]}, {"id": "t::b", "patched": ["app.clock.now"]},
                 {"id": "t::c", "patched": []}]
        behaviors = [
            {"id": "mocked", "real_path": ["app.api.save", "app.store.save"], "tests": ["t::a"]},
            {"id": "boundary-only", "real_path": ["app.api.save"], "tests": ["t::b"]},
            {"id": "one-clean-is-enough", "real_path": ["app.store.save"], "tests": ["t::a", "t::c"]},
            {"id": "missing", "real_path": ["app.x"], "tests": ["t::gone"]},
            {"id": "none-listed", "real_path": ["app.x"], "tests": []},
        ]
        got = {row["id"]: row for row in check_behaviors(behaviors, tests)}
        self.assertEqual({k: v["status"] for k, v in got.items()},
                         {"mocked": "mock_only", "boundary-only": "real_path", "one-clean-is-enough": "real_path",
                          "missing": "untested", "none-listed": "untested"})
        self.assertEqual(got["missing"]["missing_tests"], ["t::gone"])
        self.assertEqual(got["one-clean-is-enough"]["real_path_tests"], ["t::c"])
        self.assertEqual(got["mocked"]["tests"], [{"test": "t::a", "patched_on_path": ["app.store.save"]}])

    def test_pantry_behaviors(self) -> None:
        tests = scan_tests([FIXTURE / "tests"], FIXTURE)
        self.assertEqual(len(tests), 6)
        behaviors = json.loads((FIXTURE / "behaviors.json").read_text(encoding="utf-8"))
        got = {row["id"]: row["status"] for row in check_behaviors(behaviors, tests)}
        self.assertEqual(got, {"B1": "mock_only", "B2": "mock_only", "B3": "real_path", "B4": "untested"})
        patched = {row["id"]: row["patched"] for row in tests}
        self.assertEqual(patched["tests/test_slots.py::CancelTests::test_cancel_removes_the_slot"],
                         ["pantry_app.store.Store.delete"], "a setUp patch.object applies to the class's tests")


if __name__ == "__main__":
    unittest.main()
