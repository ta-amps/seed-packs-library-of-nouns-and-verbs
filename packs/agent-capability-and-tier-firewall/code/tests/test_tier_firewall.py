"""Unit tests for tier_firewall (standard library only)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tier_firewall import (
    check_effect_ceiling,
    check_model_tier_routing,
    evaluate_dispatch,
    scan_and_redact_payload,
)


def _fake_github_token() -> str:
    return "gh" + "p_" + ("A9b8C7d6E5f4G3h2" * 2)


def _fake_high_entropy() -> str:
    return "Zx9_Qm2-Lp8+Vn4/Kr7=Wt3Yk6Hs1B"


class TierFirewallTests(unittest.TestCase):
    def test_effect_ceiling_blocks_public_when_capped_at_write_internal(self) -> None:
        policy = {
            "max_effect_class": "write-internal",
            "allowed_stores": ["workspace.drafts"],
            "allowed_path_prefixes": ["src", "tests"],
        }
        blocked = check_effect_ceiling(
            {"effect_class": "public", "target_store": "workspace.drafts", "target_path": "src/main.py"},
            policy,
        )
        self.assertFalse(blocked["passed"])
        self.assertIn("effect_exceeds_ceiling:public>write-internal", blocked["reasons"])

        allowed = check_effect_ceiling(
            {"effect_class": "write-internal", "target_store": "workspace.drafts", "target_path": "src/main.py"},
            policy,
        )
        self.assertTrue(allowed["passed"])

    def test_path_traversal_and_destructive_commands_blocked(self) -> None:
        policy = {"max_effect_class": "write-repo", "allowed_path_prefixes": ["src"]}
        res = check_effect_ceiling(
            {"effect_class": "write-repo", "target_path": "../etc/passwd", "command": "git push --force origin main"},
            policy,
        )
        self.assertFalse(res["passed"])
        self.assertIn("path_traversal_or_absolute_rejected", res["reasons"])
        self.assertIn("destructive_command_pattern_blocked", res["reasons"])

    def test_secret_scanner_redacts_tokens_and_preserves_sha256_digests(self) -> None:
        sha = "a" * 64
        payload = {
            "prompt": f"Check commit {sha} using {_fake_github_token()} and {_fake_high_entropy()}",
            "ssn_note": "id 123-45-6789",
        }
        res = scan_and_redact_payload(payload)
        self.assertFalse(res["clean"])
        self.assertGreaterEqual(res["finding_count"], 3)
        # SHA-256 hex digest must NOT be falsely flagged as high-entropy secret.
        self.assertIn(sha, res["sanitized_payload"]["prompt"])
        self.assertNotIn(_fake_github_token(), res["sanitized_payload"]["prompt"])
        self.assertNotIn("123-45-6789", res["sanitized_payload"]["ssn_note"])

    def test_model_tier_blocks_internal_or_confidential_data_from_training_or_contributor_tiers(self) -> None:
        blocked_train = check_model_tier_routing(
            data_sensitivity="internal",
            endpoint_tier="trains_on_inputs",
            contains_unredacted_secrets=False,
        )
        self.assertFalse(blocked_train["passed"])

        blocked_contrib = check_model_tier_routing(
            data_sensitivity="confidential",
            endpoint_tier="zero_retention_isolated",
            contains_unredacted_secrets=False,
            contributor_mode_enabled=True,
        )
        self.assertFalse(blocked_contrib["passed"])
        self.assertEqual(blocked_contrib["effective_endpoint_tier"], "contributor_shared")

        allowed_isolated = check_model_tier_routing(
            data_sensitivity="confidential",
            endpoint_tier="zero_retention_isolated",
            contains_unredacted_secrets=False,
            contributor_mode_enabled=False,
        )
        self.assertTrue(allowed_isolated["passed"])

    def test_secret_classification_always_blocked_from_external_dispatch(self) -> None:
        res = check_model_tier_routing(
            data_sensitivity="secret",
            endpoint_tier="zero_retention_isolated",
            contains_unredacted_secrets=False,
        )
        self.assertFalse(res["passed"])
        self.assertIn("secret_tier_payload_forbidden_for_external_model_dispatch", res["reasons"])

    def test_evaluate_dispatch_blocks_leak_and_allows_clean_scoped_call(self) -> None:
        policy = {"max_effect_class": "write-internal", "allowed_stores": ["sandbox.notes"]}
        bad_req = {
            "action": {"effect_class": "write-internal", "target_store": "sandbox.notes"},
            "data_sensitivity": "internal",
            "endpoint_tier": "contributor_shared",
            "payload": {"message": f"Authorization: Bearer {'Z' * 24}"},
        }
        bad_dec = evaluate_dispatch(bad_req, policy)
        self.assertEqual(bad_dec["verdict"], "block")
        self.assertFalse(bad_dec["allowed"])

        good_req = {
            "action": {"effect_class": "read", "target_store": "sandbox.notes"},
            "data_sensitivity": "internal",
            "endpoint_tier": "enterprise_no_train",
            "payload": {"message": "Summarize public RFC 9110 caching semantics."},
        }
        good_dec = evaluate_dispatch(good_req, policy)
        self.assertEqual(good_dec["verdict"], "allow")
        self.assertTrue(good_dec["allowed"])

    def test_cli_exit_codes_zero_on_allow_and_two_on_block(self) -> None:
        policy = {"max_effect_class": "read"}
        allow_req = {
            "action": {"effect_class": "read"},
            "data_sensitivity": "public",
            "endpoint_tier": "trains_on_inputs",
            "payload": {"text": "Public benchmark prompt."},
        }
        block_req = {
            "action": {"effect_class": "public"},
            "data_sensitivity": "confidential",
            "endpoint_tier": "trains_on_inputs",
            "payload": {"text": "Confidential incident report."},
        }
        cwd = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            pol_p = Path(tmp) / "pol.json"
            allow_p = Path(tmp) / "allow.json"
            block_p = Path(tmp) / "block.json"
            pol_p.write_text(json.dumps(policy), encoding="utf-8")
            allow_p.write_text(json.dumps(allow_req), encoding="utf-8")
            block_p.write_text(json.dumps(block_req), encoding="utf-8")

            ok_proc = subprocess.run(
                [sys.executable, "-m", "tier_firewall", "evaluate", str(allow_p), "--policy", str(pol_p)],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok_proc.returncode, 0)
            self.assertTrue(json.loads(ok_proc.stdout)["allowed"])

            blk_proc = subprocess.run(
                [sys.executable, "-m", "tier_firewall", "evaluate", str(block_p), "--policy", str(pol_p)],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(blk_proc.returncode, 2)
            self.assertFalse(json.loads(blk_proc.stdout)["allowed"])


if __name__ == "__main__":
    unittest.main()
