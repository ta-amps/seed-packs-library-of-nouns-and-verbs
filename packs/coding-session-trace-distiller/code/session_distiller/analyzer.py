"""Mine sanitized coding session JSONL transcripts into reusable operational artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .redactor import redact_session

EDIT_TOOLS = {"edit_file", "write_file", "apply_patch", "patch_file", "replace_in_file", "create_file"}
CHECK_TOOLS = {"run_command", "bash", "shell", "exec_command", "run_tests", "pytest", "unittest"}
LINE_NUM_RE = re.compile(r"\bline\s+\d+\b", re.IGNORECASE)
HEX_ADDR_RE = re.compile(r"0x[0-9a-fA-F]{6,16}")


def load_jsonl_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError(f"line {lineno}: JSONL event must be an object")
        if "step" not in parsed:
            parsed = {"step": lineno, **parsed}
        events.append(parsed)
    return events


def _normalize_error_signature(error_text: str) -> str:
    head = (error_text or "").strip().splitlines()[0] if (error_text or "").strip() else "unspecified_error"
    head = LINE_NUM_RE.sub("line N", head)
    head = HEX_ADDR_RE.sub("0xADDR", head)
    return re.sub(r"\s+", " ", head)[:160]


def _step_of(ev: dict[str, Any], fallback: int) -> int:
    raw = ev.get("step", ev.get("step_index", fallback))
    return int(raw) if isinstance(raw, int) and not isinstance(raw, bool) else fallback


def _tool_of(ev: dict[str, Any]) -> str:
    return str(ev.get("tool") or ev.get("tool_name") or ev.get("kind") or "message").strip()


def _target_of(ev: dict[str, Any]) -> str:
    for field in ("target", "path", "command", "file"):
        val = ev.get(field)
        if isinstance(val, str) and val.strip():
            return val.strip()[:200]
    args = ev.get("args")
    if isinstance(args, dict):
        for field in ("path", "Path", "command", "CommandLine", "target"):
            val = args.get(field)
            if isinstance(val, str) and val.strip():
                return val.strip()[:200]
    return ""


def _is_failure(ev: dict[str, Any]) -> bool:
    status = str(ev.get("status") or "").lower()
    exit_code = ev.get("exit_code")
    if status in {"error", "failed", "failure", "timeout"}:
        return True
    if isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0:
        return True
    return bool(ev.get("error"))


def _is_passing_check(ev: dict[str, Any]) -> bool:
    tool = _tool_of(ev)
    if tool not in CHECK_TOOLS and not ev.get("is_verification"):
        return False
    if _is_failure(ev):
        return False
    exit_code = ev.get("exit_code")
    status = str(ev.get("status") or "").lower()
    return (isinstance(exit_code, int) and exit_code == 0) or status in {"ok", "pass", "passed", "done", "success"}


def _is_failing_check(ev: dict[str, Any]) -> bool:
    tool = _tool_of(ev)
    return (tool in CHECK_TOOLS or bool(ev.get("is_verification"))) and _is_failure(ev)


def _is_edit(ev: dict[str, Any]) -> bool:
    tool = _tool_of(ev)
    return (tool in EDIT_TOOLS or ev.get("action") == "edit") and not _is_failure(ev)


def _short_id(prefix: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def detect_tool_error_loops(events: list[dict[str, Any]], min_repeats: int = 2) -> list[dict[str, Any]]:
    """Find consecutive or unbroken tool-failure streaks with identical tool and error signature."""
    if min_repeats < 2:
        raise ValueError("min_repeats must be at least 2")
    loops: list[dict[str, Any]] = []
    streak: list[tuple[int, dict[str, Any], str, str]] = []

    def _flush(next_event: dict[str, Any] | None) -> None:
        if len(streak) < min_repeats:
            return
        tool = streak[0][2]
        err_sig = streak[0][3]
        targets = sorted({item[1].get("_norm_target", "") for item in streak if item[1].get("_norm_target")})
        start_step = streak[0][0]
        end_step = streak[-1][0]
        resolution = "unrecovered"
        recovery_step: int | None = None
        if next_event is not None and not _is_failure(next_event):
            resolution = f"recovered_via_{_tool_of(next_event)}"
            recovery_step = _step_of(next_event, end_step + 1)
        loop_id = _short_id("LOOP", f"{tool}|{err_sig}|{start_step}|{end_step}")
        loops.append(
            {
                "loop_id": loop_id,
                "tool": tool,
                "targets": targets,
                "error_signature": err_sig,
                "repeat_count": len(streak),
                "wasted_steps": len(streak) - 1,
                "start_step": start_step,
                "end_step": end_step,
                "resolution": resolution,
                "recovery_step": recovery_step,
            }
        )

    for idx, raw_ev in enumerate(events, start=1):
        step = _step_of(raw_ev, idx)
        tool = _tool_of(raw_ev)
        target = _target_of(raw_ev)
        ev = {**raw_ev, "_norm_target": target}
        if _is_failure(ev):
            err_sig = _normalize_error_signature(str(ev.get("error") or ev.get("output") or ev.get("status") or "error"))
            if streak and streak[-1][2] == tool and streak[-1][3] == err_sig:
                streak.append((step, ev, tool, err_sig))
            else:
                _flush(ev)
                streak = [(step, ev, tool, err_sig)]
        else:
            if streak:
                _flush(ev)
                streak = []
    if streak:
        _flush(None)
    return loops


def extract_failure_tombstones(
    events: list[dict[str, Any]],
    loops: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Extract dead-end approaches from repeated failure loops and explicitly reverted/abandoned steps."""
    computed_loops = loops if loops is not None else detect_tool_error_loops(events)
    tombstones: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()

    for loop in computed_loops:
        fp = f"{loop['tool']}:{loop['error_signature']}"
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)
        target_desc = loop["targets"][0] if loop["targets"] else "unspecified_target"
        tombstones.append(
            {
                "tombstone_id": _short_id("TOMB", fp),
                "source_kind": "tool_error_loop",
                "tool": loop["tool"],
                "target": target_desc,
                "symptom": loop["error_signature"],
                "step_span": [loop["start_step"], loop["end_step"]],
                "wasted_attempts": loop["repeat_count"],
                "avoid_rule": (
                    f"Stop repeating {loop['tool']} on {target_desc} after the first "
                    f"'{loop['error_signature']}' failure; inspect preconditions before retrying."
                ),
            }
        )

    for idx, ev in enumerate(events, start=1):
        step = _step_of(ev, idx)
        if ev.get("abandoned") is True or str(ev.get("disposition") or "").lower() in {"reverted", "dead_end", "abandoned"}:
            tool = _tool_of(ev)
            target = _target_of(ev) or "session_branch"
            reason = _normalize_error_signature(str(ev.get("reason") or ev.get("error") or ev.get("summary") or "abandoned_approach"))
            fp = f"abandoned:{tool}:{target}:{reason}"
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)
            tombstones.append(
                {
                    "tombstone_id": _short_id("TOMB", fp),
                    "source_kind": "abandoned_branch",
                    "tool": tool,
                    "target": target,
                    "symptom": reason,
                    "step_span": [step, step],
                    "wasted_attempts": 1,
                    "avoid_rule": f"Avoid {target} approach that was reverted or abandoned due to: {reason}.",
                }
            )
    return tombstones


def extract_verified_fix_recipes(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract verified fix recipes (failing_check -> edit -> passing_check) and separate unverified edits."""
    verified: list[dict[str, Any]] = []
    unverified: list[dict[str, Any]] = []

    active_failure: dict[str, Any] | None = None
    pending_edits: list[dict[str, Any]] = []

    for idx, ev in enumerate(events, start=1):
        step = _step_of(ev, idx)
        if _is_failing_check(ev):
            err_sig = _normalize_error_signature(str(ev.get("error") or ev.get("output") or "check_failed"))
            cmd = _target_of(ev) or _tool_of(ev)
            if active_failure is None:
                active_failure = {"step": step, "command": cmd, "error_signature": err_sig}
            elif not pending_edits:
                active_failure = {"step": step, "command": cmd, "error_signature": err_sig}
        elif _is_edit(ev):
            target = _target_of(ev) or "unknown_file"
            summary = str(ev.get("summary") or ev.get("change_summary") or f"Modified {target}").strip()[:240]
            pending_edits.append({"step": step, "file": target, "summary": summary, "reverted": bool(ev.get("abandoned"))})
        elif _is_passing_check(ev):
            cmd = _target_of(ev) or _tool_of(ev)
            live_edits = [e for e in pending_edits if not e["reverted"]]
            if active_failure is not None and live_edits:
                files = sorted({e["file"] for e in live_edits})
                edit_steps = [e["step"] for e in live_edits]
                recipe_key = f"{active_failure['error_signature']}|{'|'.join(files)}|{cmd}"
                verified.append(
                    {
                        "recipe_id": _short_id("FIX", recipe_key),
                        "verification_status": "verified_by_passing_check",
                        "failure_step": active_failure["step"],
                        "failing_command": active_failure["command"],
                        "failure_signature": active_failure["error_signature"],
                        "edit_steps": edit_steps,
                        "files_modified": files,
                        "fix_summaries": [e["summary"] for e in live_edits],
                        "verification_step": step,
                        "verification_command": cmd,
                    }
                )
                active_failure = None
                pending_edits = []
            elif live_edits and active_failure is None:
                for e in live_edits:
                    unverified.append(
                        {
                            "step": e["step"],
                            "file": e["file"],
                            "reason": "passing_check_had_no_prior_failing_reproduction",
                        }
                    )
                pending_edits = []

    for leftover in pending_edits:
        unverified.append(
            {
                "step": leftover["step"],
                "file": leftover["file"],
                "reason": "no_subsequent_passing_verification_check",
            }
        )
    return verified, unverified


def propose_prompt_shims(
    loops: list[dict[str, Any]],
    tombstones: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compile recurring tool-error loops and tombstones into bounded prompt-shim candidates."""
    shims: list[dict[str, Any]] = []
    by_tool_sig: dict[tuple[str, str], dict[str, Any]] = {}

    for loop in loops:
        key = (loop["tool"], loop["error_signature"])
        slot = by_tool_sig.setdefault(
            key,
            {
                "tool": loop["tool"],
                "error_signature": loop["error_signature"],
                "supporting_loops": [],
                "total_wasted_steps": 0,
            },
        )
        slot["supporting_loops"].append(loop["loop_id"])
        slot["total_wasted_steps"] += int(loop["wasted_steps"])

    for (tool, err_sig), agg in sorted(by_tool_sig.items()):
        shim_id = _short_id("SHIM", f"{tool}|{err_sig}")
        shims.append(
            {
                "shim_id": shim_id,
                "status": "candidate_proposal",
                "target_tool": tool,
                "when_trigger": f"Before invoking {tool} or immediately after encountering '{err_sig}'",
                "guard_instruction": (
                    f"If {tool} fails with '{err_sig}', read the target state or schema once before "
                    f"issuing another {tool} call; never repeat identical arguments."
                ),
                "supporting_loop_ids": sorted(agg["supporting_loops"]),
                "wasted_steps_preventable": agg["total_wasted_steps"],
            }
        )

    existing_triggers = {s["target_tool"] + ":" + s["when_trigger"] for s in shims}
    for tomb in tombstones:
        if tomb["source_kind"] != "abandoned_branch":
            continue
        trig = f"Before modifying {tomb['target']}"
        if f"{tomb['tool']}:{trig}" in existing_triggers:
            continue
        shims.append(
            {
                "shim_id": _short_id("SHIM", f"abandoned|{tomb['tombstone_id']}"),
                "status": "candidate_proposal",
                "target_tool": tomb["tool"],
                "when_trigger": trig,
                "guard_instruction": tomb["avoid_rule"],
                "supporting_loop_ids": [tomb["tombstone_id"]],
                "wasted_steps_preventable": tomb["wasted_attempts"],
            }
        )
    return shims


def distill_session_events(
    raw_events: list[dict[str, Any]],
    *,
    session_id: str = "session",
    min_loop_repeats: int = 2,
) -> dict[str, Any]:
    """Run full redaction + deterministic distillation over a list of coding session events."""
    sanitized_events, redaction_stats = redact_session(raw_events)
    loops = detect_tool_error_loops(sanitized_events, min_repeats=min_loop_repeats)
    tombstones = extract_failure_tombstones(sanitized_events, loops=loops)
    verified_fixes, unverified_edits = extract_verified_fix_recipes(sanitized_events)
    prompt_shims = propose_prompt_shims(loops, tombstones)
    canonical_bytes = json.dumps(sanitized_events, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "session_id": session_id,
        "event_count": len(sanitized_events),
        "sanitized_events_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "redaction_counts": redaction_stats,
        "counts": {
            "tool_error_loops": len(loops),
            "failure_tombstones": len(tombstones),
            "verified_fix_recipes": len(verified_fixes),
            "unverified_edits_rejected": len(unverified_edits),
            "prompt_shim_candidates": len(prompt_shims),
        },
        "tool_error_loops": loops,
        "failure_tombstones": tombstones,
        "verified_fix_recipes": verified_fixes,
        "unverified_edits": unverified_edits,
        "prompt_shim_candidates": prompt_shims,
    }
