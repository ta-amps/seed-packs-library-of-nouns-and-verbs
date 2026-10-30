"""Negative authoring boundaries; no network, runtime or external dependencies."""

import copy
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("examples", ROOT / "scripts/validate_examples.py")
validate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate)


class ExampleChecks(unittest.TestCase):
    def fixture(self, name):
        return validate.load(ROOT / "examples" / name)

    def test_repository_examples(self):
        self.assertTrue(validate.validate_repository(ROOT)["offline_only"])

    def test_tool_caches_are_not_repository_text(self):
        """Running a pack's code checks leaves binary caches; the text checks skip them, never real files."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(*validate.SKIP_PARTS, "*.egg-info"))
            cache = root / "packs" / "code-composition" / "code" / ".pytest_cache" / "v" / "lastfailed"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"\x8a\x00 binary cache")
            self.assertTrue(validate.validate_repository(root)["offline_only"])
            (root / "docs" / "stray.md").write_text("A forbidden \u2014 dash.\n")
            with self.assertRaises(ValueError):
                validate.validate_repository(root)

    def test_json_duplicate_keys_and_nonfinite_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.json"
            for text in ('{"a":1,"a":2}', '{"count":NaN}', '[]'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    validate.load(path)

    def test_cas_requires_object_and_integer(self):
        for change in ({"expected_version": True}, {"value": "{}"}):
            value = {**self.fixture("http/noun-put.json"), **change}
            with self.assertRaises(ValueError):
                validate.noun(value)

    def test_candidate_cannot_widen_or_claim_verification(self):
        value = self.fixture("http/noun-put.json")
        for change in ({"visibility_scope": "public_commons"}, {"tags": value["tags"] + ["status:verified"]}):
            with self.assertRaises(ValueError):
                validate.noun({**value, **change})

    def test_category_and_facets_are_distinct(self):
        value = self.fixture("http/noun-put.json")
        value["tags"].append("domain:education")
        validate.noun(value)
        value["tags"].append("category:noun.code_node")
        with self.assertRaises(ValueError):
            validate.noun(value)

    def test_submit_types_and_unknown_usage(self):
        value = self.fixture("http/submit.json")
        for change in ({"ok": "true"}, {"fencing_token": False}, {"execution_report": "{}"}):
            with self.assertRaises(ValueError):
                validate.submission({**value, **change})
        invalid = copy.deepcopy(value)
        invalid["execution_report"]["usage"].pop("reason")
        with self.assertRaises(ValueError):
            validate.submission(invalid)

    def test_manifest_digest_and_path_boundaries(self):
        value = self.fixture("pack-manifest.proposed.json")
        for change in ({"path": "../README.md"}, {"sha256": "0" * 64}):
            invalid = copy.deepcopy(value)
            invalid["files"][0].update(change)
            with self.assertRaises(ValueError):
                validate.manifest(invalid, ROOT / "examples")

    def test_mcp_requires_object_arguments(self):
        value = self.fixture("mcp/put-record.json")
        value["params"]["arguments"] = "{}"
        with self.assertRaises(ValueError):
            validate.mcp(value)

    def test_meta_candidate_cannot_approve_or_change_evaluator(self):
        value = self.fixture("meta/self-improvement.reference.json")
        for change in ({"active": True}, {"controls_mutable_by_candidate": True}, {"promotion": {"automatic": True}}):
            with self.assertRaises(ValueError):
                validate.meta_contract({**value, **change})

    def test_public_scan_covers_anonymous_tokens(self):
        spec = importlib.util.spec_from_file_location("public_scan", ROOT / "scripts/check_public.py")
        scan = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scan)
        self.assertIsNotNone(scan.SECRET_PATTERNS["anonymous session"].search("tan_" + "z" * 32))


if __name__ == "__main__":
    unittest.main()
