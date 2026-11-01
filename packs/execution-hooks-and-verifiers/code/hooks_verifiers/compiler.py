"""Harness-portable 4-stage hook compiler and deterministic pre_tool guard."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .grid import resolve_grid_cell


class PortableHookCompiler:
    """Compiles 4-stage hook specs across 4 coding harnesses and evaluates pre_tool calls."""

    def __init__(
        self,
        grid_overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.cell, self.constants = resolve_grid_cell(grid_overrides, regime=regime, spec=spec)

    def compile_for_harness(self, hook_spec: dict[str, Any], target_harness: str) -> dict[str, Any]:
        """Compile declarative (pre_claim, pre_tool, post_step, pre_submit) spec for target_harness."""
        supported = list(self.constants["supported_harnesses"])
        if target_harness not in supported:
            raise ValueError(f"unsupported target_harness: {target_harness}")

        stages_raw = hook_spec.get("stages", {})
        stage_cmds = {
            stage_name: list(stages_raw.get(stage_name, []))
            for stage_name in self.constants["hook_stages"]
        }
        deny_regexes = dict(self.constants["bash_deny_regexes"])
        for custom_id, custom_pat in hook_spec.get("extra_deny_regexes", {}).items():
            deny_regexes[str(custom_id)] = str(custom_pat)

        spend_cap = float(hook_spec.get("approved_spend_cap_usd", self.cell["approved_spend_cap_usd"]))

        if target_harness == "claude_code":
            return {
                "harness": "claude_code",
                "disable_bypass_permissions": True,
                "disableBypassPermissionsMode": "disable",
                "approved_spend_cap_usd": spend_cap,
                "pre_claim_checks": stage_cmds["pre_claim"],
                "hooks": {
                    "PreToolUse": stage_cmds["pre_tool"],
                    "PostToolUse": stage_cmds["post_step"],
                    "Stop": stage_cmds["pre_submit"],
                },
                "permissions": {
                    "deny_bash_regexes": deny_regexes,
                    "deny_paths": [".env", ".env.*"],
                },
            }

        if target_harness == "muse_code":
            return {
                "harness": "muse_code",
                "disable_bypass_permissions": True,
                "approved_spend_cap_usd": spend_cap,
                "lifecycle_hooks": stage_cmds,
                "guard_patterns": deny_regexes,
            }

        if target_harness == "opencode":
            return {
                "harness": "opencode",
                "disable_bypass_permissions": True,
                "approved_spend_cap_usd": spend_cap,
                "events": {
                    "session.before_claim": stage_cmds["pre_claim"],
                    "tool.execute.before": stage_cmds["pre_tool"],
                    "tool.execute.after": stage_cmds["post_step"],
                    "session.before_submit": stage_cmds["pre_submit"],
                },
                "deny_regexes": deny_regexes,
            }

        return {
            "harness": "pi_coding_agent",
            "disable_bypass_permissions": True,
            "approved_spend_cap_usd": spend_cap,
            "handlers": {
                "on_pre_claim": stage_cmds["pre_claim"],
                "on_pre_tool": stage_cmds["pre_tool"],
                "on_post_step": stage_cmds["post_step"],
                "on_pre_submit": stage_cmds["pre_submit"],
            },
            "deny_regexes": deny_regexes,
        }

    def compile_all_harnesses(self, hook_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Compile portable configurations for claude_code, muse_code, opencode, and pi_coding_agent."""
        return {
            str(harness): self.compile_for_harness(hook_spec, str(harness))
            for harness in self.constants["supported_harnesses"]
        }

    @staticmethod
    def _is_dotenv_path(file_path: str) -> bool:
        if not file_path:
            return False
        name = Path(file_path).name
        return name == ".env" or name.startswith(".env.")

    def evaluate_pre_tool(
        self,
        tool_call: dict[str, Any],
        *,
        approved_spend_cap_override: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate a pre_tool call and return allow | deny | rewrite_hint."""
        command = str(tool_call.get("command", ""))
        file_path = str(tool_call.get("file_path", ""))
        content_patch = str(tool_call.get("content_patch", ""))
        config_delta = tool_call.get("config_delta") or {}

        spend_cap = (
            float(approved_spend_cap_override)
            if approved_spend_cap_override is not None
            else float(self.cell["approved_spend_cap_usd"])
        )
        est_spend = float(tool_call.get("estimated_spend_usd", 0.0))
        if est_spend > spend_cap:
            return {
                "decision": "deny",
                "blocked": True,
                "rule_id": "unapproved_spend",
                "reason": f"Estimated spend {est_spend} exceeds approved cap {spend_cap}.",
                "rewrite_hint": None,
            }

        if (
            bool(config_delta.get("contributor_mode", False))
            or bool(config_delta.get("allow_training_collection", False))
            or bool(config_delta.get("disable_bypass_permissions") is False)
            or "--enable-contributor-mode" in command
        ):
            return {
                "decision": "deny",
                "blocked": True,
                "rule_id": "contributor_mode_downgrade",
                "reason": "Contributor-mode data collection or permission-bypass downgrade is forbidden.",
                "rewrite_hint": None,
            }

        if self._is_dotenv_path(file_path):
            return {
                "decision": "deny",
                "blocked": True,
                "rule_id": "dotenv_secret_read",
                "reason": "Reading .env secret files is denied.",
                "rewrite_hint": None,
            }

        for rule_id, pattern in self.constants["bash_deny_regexes"].items():
            if command and re.search(str(pattern), command):
                return {
                    "decision": "deny",
                    "blocked": True,
                    "rule_id": str(rule_id),
                    "reason": f"Command matched deny rule {rule_id}.",
                    "rewrite_hint": None,
                }

        hygiene_decision = str(self.cell["hygiene_violation_decision"])
        combined_source = f"{content_patch}\n{command}"
        for rule_id, rule_cfg in self.constants["rewrite_rules"].items():
            if re.search(str(rule_cfg["pattern"]), combined_source):
                return {
                    "decision": hygiene_decision,
                    "blocked": True,
                    "rule_id": str(rule_id),
                    "reason": f"Source patch matched hygiene policy {rule_id}.",
                    "rewrite_hint": str(rule_cfg["hint"]),
                }

        return {
            "decision": "allow",
            "blocked": False,
            "rule_id": None,
            "reason": "Tool call passed pre_tool policy checks.",
            "rewrite_hint": None,
        }
