"""The finder lists handlers that swallow errors, by class, and leaves alone the ones that raise or do work."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from health_checks import classify, find_swallowed, scan_source


def one(body: str, head: str = "except Exception:") -> str | None:
    """Classify the handler of a try statement whose except clause is head and whose body is the given lines."""
    lines = ["try:", "    work()", head, *("    " + line for line in body.splitlines())]
    return classify(ast.parse("\n".join(lines) + "\n").body[0].handlers[0])


class Classes(unittest.TestCase):
    def test_broad_handlers_that_do_nothing_are_swallowed(self) -> None:
        for head in ("except:", "except Exception:", "except BaseException as exc:", "except (ValueError, Exception):",
                     "except builtins.Exception:"):
            for body in ("pass", "...", "return None", "return"):
                self.assertEqual(one(body, head), "swallowed", (head, body))

    def test_loop_control_is_doing_nothing_too(self) -> None:
        found = scan_source("for x in xs:\n    try:\n        work()\n    except Exception:\n        continue\n")
        self.assertEqual([f["class"] for f in found], ["swallowed"])

    def test_logged_fallback_and_narrow(self) -> None:
        self.assertEqual(one("log.warning('failed: %s', exc)", "except Exception as exc:"), "logged_only")
        self.assertEqual(one("print('failed')\npass"), "logged_only")
        self.assertEqual(one("return []"), "fallback")
        self.assertEqual(one("log.error('x')\nreturn {}"), "fallback")
        self.assertEqual(one("pass", "except KeyError:"), "narrow_ignored")
        self.assertIsNone(one("log.warning('x')", "except KeyError:"), "a narrow handler that logs is fine")

    def test_handlers_that_raise_or_work_are_not_listed(self) -> None:
        self.assertIsNone(one("raise"))
        self.assertIsNone(one("raise RuntimeError('wrapped') from exc", "except Exception as exc:"))
        self.assertIsNone(one("log.exception('x')\nraise"))
        self.assertIsNone(one("errors.append(exc)", "except Exception as exc:"))
        self.assertIsNone(one("def later():\n    raise ValueError()\npass"), "defining a function is work")

    def test_a_raise_only_in_a_nested_function_does_not_count_as_raising(self) -> None:
        source = "try:\n    work()\nexcept Exception:\n    class Later:\n        def go(self):\n            raise ValueError()\n    pass\n"
        self.assertEqual(scan_source(source), [], "defining a class is work, but its raise is not the handler's")
        self.assertEqual(one("pass"), "swallowed")

    def test_suppress_broad_only(self) -> None:
        source = ("from contextlib import suppress\nimport contextlib\n"
                  "with suppress(Exception):\n    work()\n"
                  "with contextlib.suppress(OSError, BaseException):\n    work()\n"
                  "with suppress(KeyError):\n    work()\n")
        self.assertEqual([(f["line"], f["class"]) for f in scan_source(source)], [(3, "suppress_broad"), (5, "suppress_broad")])

    def test_locations_and_enclosing_names(self) -> None:
        source = "class Roster:\n    def sync(self):\n        try:\n            work()\n        except Exception:\n            pass\n"
        found = scan_source(source)
        self.assertEqual((found[0]["line"], found[0]["end_line"], found[0]["in"], found[0]["handler"], found[0]["body"]),
                         (5, 6, "Roster.sync", "except Exception:", "pass"))


class Files(unittest.TestCase):
    def test_folders_counts_and_unparsed_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "a.py").write_text("try:\n    x()\nexcept:\n    pass\n", encoding="utf-8")
            (root / "pkg" / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "lib.py").write_text("try:\n    x()\nexcept:\n    pass\n", encoding="utf-8")
            result = find_swallowed(root)
            self.assertEqual((result["files"], result["count"], result["act"]), (2, 1, 1))
            self.assertEqual(result["unparsed"], [{"path": "pkg/broken.py", "line": 1, "error": "SyntaxError"}])
            self.assertEqual(result["items"][0]["path"], "pkg/a.py")
            self.assertEqual(find_swallowed(root, exclude=["pkg/a.py"])["count"], 0)


if __name__ == "__main__":
    unittest.main()
