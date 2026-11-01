"""Unit tests for session_distiller (standard library only)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from session_distiller import (
    detect_tool_error_loops,
    distill_session_events,
    extract_failure_tombstones,
    extract_verified_fix_recipes,
    propose_prompt_shims,
    redact_session,
    redact_text,
)


def _synthetic_openai_token() -> str:
    return "sk" + "-" + ("x" * 28)


def _synthetic_aws_key() -> str:
    return "AK" + "IA" + ("7" * 16)


def _synthetic_pem_header() -> str:
    return "-----BEGIN " + "RSA PRIVATE KEY-----"


class SessionDistillerTests(unittest.TestCase):
    def test_redactor_strips_secrets_emails_and_home_paths(self) -> None:
        raw = (
            f"Authorization: Bearer {'b' * 24}; key={_synthetic_openai_token()}; "
            f"aws={_synthetic_aws_key()}; hdr={_synthetic_pem_header()}; "
            "author=alice.dev@corp-domain.org; file=/home/alice/repo/app.py"
        )
        stats: dict[str, int] = {}
        cleaned = redact_text(raw, stats)
        self.assertNotIn(_synthetic_openai_token(), cleaned)
        self.assertNotIn(_synthetic_aws_key(), cleaned)
        self.assertNotIn("alice.dev@corp-domain.org", cleaned)
        self.assertNotIn("/home/alice", cleaned)
        self.assertIn("<HOME>/repo/app.py", cleaned)
        self.assertGreaterEqual(stats["secrets_redacted"], 4)
        self.assertEqual(stats["emails_redacted"], 1)
        self.assertEqual(stats["paths_normalized"], 1)

    def test_example_org_emails_stay_untouched(self) -> None:
        stats: dict[str, int] = {}
        cleaned = redact_text("Contact maintainer@example.org for fixture docs.", stats)
        self.assertIn("maintainer@example.org", cleaned)
        self.assertEqual(stats.get("emails_redacted", 0), 0)

    def test_tool_error_loop_and_recovery_detected(self) -> None:
        events = [
            {"step": 1, "tool": "edit_file", "path": "src/parser.py", "status": "error", "error": "Target string not found at line 42"},
            {"step": 2, "tool": "edit_file", "path": "src/parser.py", "status": "error", "error": "Target string not found at line 88"},
            {"step": 3, "tool": "edit_file", "path": "src/parser.py", "status": "error", "error": "Target string not found at line 91"},
            {"step": 4, "tool": "read_file", "path": "src/parser.py", "status": "ok"},
        ]
        loops = detect_tool_error_loops(events, min_repeats=2)
        self.assertEqual(len(loops), 1)
        self.assertEqual(loops[0]["repeat_count"], 3)
        self.assertEqual(loops[0]["wasted_steps"], 2)
        self.assertEqual(loops[0]["resolution"], "recovered_via_read_file")
        self.assertEqual(loops[0]["recovery_step"], 4)

    def test_verified_fix_requires_failing_check_then_edit_then_passing_check(self) -> None:
        events = [
            {"step": 1, "tool": "run_command", "command": "python3 -m unittest", "exit_code": 1, "error": "AssertionError: off by one"},
            {"step": 2, "tool": "edit_file", "path": "src/calc.py", "status": "ok", "summary": "Clamp upper index bound"},
            {"step": 3, "tool": "run_command", "command": "python3 -m unittest", "exit_code": 0, "status": "ok"},
            {"step": 4, "tool": "write_file", "path": "src/untested_helper.py", "status": "ok", "summary": "Add helper without running tests"},
        ]
        verified, unverified = extract_verified_fix_recipes(events)
        self.assertEqual(len(verified), 1)
        self.assertEqual(verified[0]["files_modified"], ["src/calc.py"])
        self.assertEqual(verified[0]["failure_step"], 1)
        self.assertEqual(verified[0]["verification_step"], 3)
        self.assertEqual(len(unverified), 1)
        self.assertEqual(unverified[0]["file"], "src/untested_helper.py")
        self.assertEqual(unverified[0]["reason"], "no_subsequent_passing_verification_check")

    def test_abandoned_branch_becomes_tombstone_and_prompt_shim(self) -> None:
        events = [
            {
                "step": 10,
                "tool": "apply_patch",
                "target": "src/cache.py",
                "abandoned": True,
                "reason": "Global mutable cache broke worker isolation under concurrency",
            }
        ]
        tombstones = extract_failure_tombstones(events, loops=[])
        self.assertEqual(len(tombstones), 1)
        self.assertEqual(tombstones[0]["source_kind"], "abandoned_branch")
        shims = propose_prompt_shims([], tombstones)
        self.assertEqual(len(shims), 1)
        self.assertEqual(shims[0]["status"], "candidate_proposal")

    def test_full_distillation_and_cli_determinism(self) -> None:
        events = [
            {"step": 1, "tool": "run_command", "command": "pytest -q", "exit_code": 1, "error": "KeyError: 'timeout' in /home/bob/work/cfg.py"},
            {"step": 2, "tool": "edit_file", "path": "/home/bob/work/cfg.py", "status": "error", "error": "Target mismatch"},
            {"step": 3, "tool": "edit_file", "path": "/home/bob/work/cfg.py", "status": "error", "error": "Target mismatch"},
            {"step": 4, "tool": "read_file", "path": "/home/bob/work/cfg.py", "status": "ok"},
            {"step": 5, "tool": "edit_file", "path": "/home/bob/work/cfg.py", "status": "ok", "summary": "Default timeout to 30"},
            {"step": 6, "tool": "run_command", "command": "pytest -q", "exit_code": 0, "status": "ok"},
        ]
        first = distill_session_events(events, session_id="demo-01")
        second = distill_session_events(events, session_id="demo-01")
        self.assertEqual(first, second)
        self.assertEqual(first["counts"]["tool_error_loops"], 1)
        self.assertEqual(first["counts"]["verified_fix_recipes"], 1)
        self.assertGreaterEqual(first["redaction_counts"]["paths_normalized"], 1)

        with tempfile.TemporaryDirectory() as tmp:
            jsonl_file = Path(tmp) / "trace.jsonl"
            jsonl_file.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "session_distiller", "distill", str(jsonl_file), "--session-id", "demo-01"],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out["sanitized_events_sha256"], first["sanitized_events_sha256"])
            self.assertEqual(cli_out["counts"], first["counts"])

    def test_secret_dict_fields_redacted(self) -> None:
        sanitized, stats = redact_session([{"step": 1, "api_key": "plain_text_token_value_12345"}])
        self.assertEqual(sanitized[0]["api_key"], "[REDACTED:SECRET_FIELD]")
        self.assertEqual(stats["secrets_redacted"], 1)


if __name__ == "__main__":
    unittest.main()
