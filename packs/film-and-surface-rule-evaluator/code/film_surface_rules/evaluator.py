"""Declarative film rule-noun evaluator, stamp scanner, cognitive-load scorer, mirror rewriter & MCP parity gate."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_WORD_RE = re.compile(r"[a-z0-9]+")
_WHITESPACE_RE = re.compile(r"\s+")
_STATED_TOOLS_RE = re.compile(r"\b(\d+)\s+tools\b", re.IGNORECASE)
_TOOL_SECTION_RE = re.compile(r"tools(?:\s+total)?\)?\s*:", re.IGNORECASE)
_TOOL_BULLET_RE = re.compile(r"^\s*[-*]\s*`?([a-z][a-z0-9_-]*)`?(?:\s*\([^()]*\))?")


def load_default_grid_cell(spec_path: Path | None = None) -> dict[str, Any]:
    """Load the externalized default configuration grid cell."""
    target = spec_path or Path(__file__).with_name("default_grid_spec.json")
    spec = json.loads(target.read_text(encoding="utf-8"))
    return dict(spec["default_cell"])


def _resolve_metric_path(measurements: dict[str, Any], metric_path: str | None) -> tuple[bool, Any]:
    """Resolve dotted metric keys (`audio.true_peak_dbtp`) without fabricating missing values."""
    if not metric_path:
        return False, None
    if metric_path in measurements:
        val = measurements[metric_path]
        return val is not None, val
    cur: Any = measurements
    for part in metric_path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return cur is not None, cur


def evaluate_declarative_rule_nouns(
    rules: list[dict[str, Any]],
    measurements: dict[str, Any],
    *,
    hook_stage: str | None = None,
) -> dict[str, Any]:
    """Evaluate declarative rule nouns (`<`, `<=`, `>=`, `abs<=`, `in_range`, `empty`, `is_true`, `is_false`)."""
    results: list[dict[str, Any]] = []
    block_failures = 0
    warn_failures = 0
    unknown_count = 0
    advisory_count = 0
    passed_count = 0

    for rule in rules:
        rule_hooks = rule.get("hook") or []
        if hook_stage is not None and rule_hooks and hook_stage not in rule_hooks:
            continue
        rule_id = str(rule.get("id", ""))
        op = rule.get("op")
        severity = str(rule.get("severity") or "info")
        threshold = rule.get("threshold")
        metric_key = rule.get("metric")

        if op is None:
            advisory_count += 1
            results.append(
                {
                    "id": rule_id,
                    "severity": severity,
                    "outcome": "advisory",
                    "observed": None,
                    "threshold": threshold,
                }
            )
            continue

        found, observed = _resolve_metric_path(measurements, metric_key)
        if not found:
            unknown_count += 1
            results.append(
                {
                    "id": rule_id,
                    "severity": severity,
                    "outcome": "unknown",
                    "observed": None,
                    "threshold": threshold,
                }
            )
            continue

        ok = False
        if op == "<":
            ok = float(observed) < float(threshold)
        elif op == "<=":
            ok = float(observed) <= float(threshold)
        elif op == ">=":
            ok = float(observed) >= float(threshold)
        elif op == "abs<=":
            ok = abs(float(observed)) <= float(threshold)
        elif op == "in_range":
            ok = isinstance(threshold, list) and float(threshold[0]) <= float(observed) <= float(threshold[-1])
        elif op == "empty":
            ok = isinstance(observed, (list, dict, str)) and len(observed) == 0
        elif op == "is_true":
            ok = observed is True
        elif op == "is_false":
            ok = observed is False
        else:
            raise ValueError(f"Unsupported rule operator: {op}")

        if ok:
            passed_count += 1
            outcome = "pass"
        else:
            outcome = "fail"
            if severity == "block":
                block_failures += 1
            elif severity == "warn":
                warn_failures += 1

        results.append(
            {
                "id": rule_id,
                "severity": severity,
                "outcome": outcome,
                "observed": observed,
                "threshold": threshold,
            }
        )

    if block_failures > 0:
        verdict = "blocked"
    elif unknown_count > 0:
        verdict = "unknown"
    elif warn_failures > 0:
        verdict = "warn"
    else:
        verdict = "pass"

    return {
        "verdict": verdict,
        "evaluated_count": len(results),
        "passed_count": passed_count,
        "block_failures": block_failures,
        "warn_failures": warn_failures,
        "unknown_count": unknown_count,
        "advisory_count": advisory_count,
        "results": results,
    }


def _char_ngrams(text: str, width: int) -> set[str]:
    norm = _WHITESPACE_RE.sub(" ", text.strip().lower())
    if len(norm) <= width:
        return {norm} if norm else set()
    return {norm[idx : idx + width] for idx in range(len(norm) - width + 1)}


def scan_forbidden_stamps_and_chips(
    ocr_spans: list[dict[str, Any]],
    status_chips: list[str],
    grid_cell: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect forbidden made-up/non-functional stamps at native frame resolution and non-functional chips."""
    cell = grid_cell or load_default_grid_cell()
    min_sim = float(cell["forbidden_stamp_min_similarity"])
    ngram_w = int(cell["ngram_width"])
    digits = int(cell["round_digits"])
    forbidden_stamps = [str(s).lower() for s in cell["forbidden_stamps"]]
    forbidden_chips = {str(s).strip().lower() for s in cell["forbidden_status_chips"]}

    stamp_hits: list[dict[str, Any]] = []
    for item in ocr_spans:
        raw_text = str(item.get("text", ""))
        lowered = _WHITESPACE_RE.sub(" ", raw_text.strip().lower())
        if not lowered:
            continue
        obs_grams = _char_ngrams(lowered, ngram_w)
        for target in forbidden_stamps:
            if target in lowered:
                stamp_hits.append(
                    {
                        "frame_t_s": item.get("t_s"),
                        "matched_stamp": target,
                        "similarity": 1.0,
                        "observed_text": raw_text,
                    }
                )
                break
            tgt_grams = _char_ngrams(target, ngram_w)
            union_len = len(obs_grams | tgt_grams)
            sim = (len(obs_grams & tgt_grams) / union_len) if union_len > 0 else 0.0
            if sim >= min_sim:
                stamp_hits.append(
                    {
                        "frame_t_s": item.get("t_s"),
                        "matched_stamp": target,
                        "similarity": round(sim, digits),
                        "observed_text": raw_text,
                    }
                )
                break

    chip_hits = sorted({chip.strip() for chip in status_chips if chip.strip().lower() in forbidden_chips})
    return {
        "clean": len(stamp_hits) == 0 and len(chip_hits) == 0,
        "stamp_hits": stamp_hits,
        "chip_hits": chip_hits,
    }


def score_caption_plate_and_cognitive_load(
    cues: list[dict[str, Any]],
    ost_events: list[dict[str, Any]],
    grid_cell: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute frosted-pill centering offsets, CPS, gap flicker, on-screen text dwell & dual-channel load."""
    cell = grid_cell or load_default_grid_cell()
    stage_center_x = float(cell["stage_width_px"]) / float(cell["half_divisor"])
    center_tol = float(cell["caption_center_tol_px"])
    max_lines = int(cell["caption_max_lines"])
    max_line_chars = int(cell["caption_max_chars_per_line"])
    max_cps = float(cell["caption_max_cps"])
    min_gap = float(cell["caption_min_gap_no_blink_s"])
    base_dwell = float(cell["ost_base_dwell_s"])
    wps_quiet = float(cell["ost_wps_quiet"])
    wps_captioned = float(cell["ost_wps_captioned"])
    max_dual_wps = float(cell["max_dual_load_wps"])
    min_overlap = float(cell["min_competing_word_overlap"])
    min_word_len = int(cell["min_content_word_len"])
    digits = int(cell["round_digits"])

    max_center_offset_px = 0.0
    max_observed_cps = 0.0
    line_violations = 0
    gap_flickers = 0

    sorted_cues = sorted(cues, key=lambda c: float(c["start_s"]))
    for idx, cue in enumerate(sorted_cues):
        text = str(cue.get("text", ""))
        lines = text.splitlines() or [text]
        if len(lines) > max_lines or any(len(line) > max_line_chars for line in lines):
            line_violations += 1
        dur = max(float(cue["end_s"]) - float(cue["start_s"]), 0.0)
        cps = (len(text.replace("\n", " ")) / dur) if dur > 0.0 else 0.0
        if cps > max_observed_cps:
            max_observed_cps = cps
        plate_cx = float(cue.get("plate_center_x_px", stage_center_x))
        offset = abs(plate_cx - stage_center_x)
        if offset > max_center_offset_px:
            max_center_offset_px = offset
        if idx > 0:
            gap = float(cue["start_s"]) - float(sorted_cues[idx - 1]["end_s"])
            if 0.0 < gap < min_gap and not bool(cue.get("plate_held_across_gap", False)):
                gap_flickers += 1

    ost_short_dwell = 0
    competing_Attention_Collisions = 0
    for ost in ost_events:
        ost_text = str(ost.get("text", ""))
        ost_words = [w for w in _WORD_RE.findall(ost_text.lower()) if len(w) >= min_word_len]
        word_count = len(_WORD_RE.findall(ost_text.lower()))
        ost_start = float(ost["start_s"])
        ost_end = float(ost["end_s"])
        ost_dur = max(ost_end - ost_start, 0.0)

        overlapping_cues = [
            c for c in sorted_cues if min(ost_end, float(c["end_s"])) > max(ost_start, float(c["start_s"]))
        ]
        rate = wps_captioned if overlapping_cues else wps_quiet
        required_dwell = base_dwell + (word_count / rate)
        if ost_dur < required_dwell:
            ost_short_dwell += 1

        for cue in overlapping_cues:
            cue_words = [w for w in _WORD_RE.findall(str(cue.get("text", "")).lower()) if len(w) >= min_word_len]
            cue_dur = max(float(cue["end_s"]) - float(cue["start_s"]), 0.0)
            cue_wps = (len(_WORD_RE.findall(str(cue.get("text", "")).lower())) / cue_dur) if cue_dur > 0.0 else 0.0
            ost_wps = (word_count / ost_dur) if ost_dur > 0.0 else 0.0
            overlap_ratio = (len(set(ost_words) & set(cue_words)) / len(set(ost_words))) if ost_words else 1.0
            if (cue_wps + ost_wps) > max_dual_wps and overlap_ratio < min_overlap:
                competing_Attention_Collisions += 1

    passed = (
        max_center_offset_px <= center_tol
        and max_observed_cps <= max_cps
        and line_violations == 0
        and gap_flickers == 0
        and ost_short_dwell == 0
        and competing_Attention_Collisions == 0
    )
    return {
        "passed": passed,
        "max_center_offset_px": round(max_center_offset_px, digits),
        "max_observed_cps": round(max_observed_cps, digits),
        "line_violations": line_violations,
        "gap_flickers": gap_flickers,
        "ost_short_dwell": ost_short_dwell,
        "competing_attention_collisions": competing_Attention_Collisions,
    }


def rewrite_dead_repo_links_to_source_mirror(
    urls: list[str],
    mirror_manifest: dict[str, Any],
    *,
    mirror_base_path: str = "/source",
    intake_fallback_path: str = "/nonprofits",
    downloads_base_path: str = "/downloads",
    grid_cell: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically repoint dead external repository links to self-hosted `/source/` mirror bundles."""
    cell = grid_cell or load_default_grid_cell()
    short_len = int(cell["short_sha_chars"])
    repos_by_name: dict[str, dict[str, Any]] = {}
    for raw_entry in mirror_manifest.get("repositories", []):
        entry = dict(raw_entry)
        repo_name = str(entry.get("repo_name") or entry.get("repository") or "").strip()
        slug = str(entry.get("slug") or repo_name).strip()
        entry["slug"] = slug
        entry["commit"] = str(entry.get("commit") or entry.get("git_commit") or "")
        entry["tar_sha256"] = str(entry.get("tar_sha256") or entry.get("sha256") or "")
        entry["archive"] = str(entry.get("archive") or "").lstrip("./")
        entry["readme"] = str(entry.get("readme") or "").lstrip("./")
        if repo_name:
            repos_by_name[repo_name] = entry
        if slug:
            repos_by_name[slug] = entry

    rewritten: list[dict[str, Any]] = []
    unresolved: list[str] = []

    for raw_url in urls:
        parsed = urlparse(raw_url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) == 1:
            rewritten.append(
                {
                    "original_url": raw_url,
                    "mirror_url": f"{mirror_base_path}/",
                    "commit": None,
                    "bundle_sha256_prefix": None,
                    "route_kind": "mirror_index",
                }
            )
            continue
        if len(parts) >= 1 + 1:
            repo_key = parts[1]
            entry = repos_by_name.get(repo_key)
            if entry is None:
                unresolved.append(raw_url)
                continue
            slug = str(entry["slug"])
            commit = str(entry.get("commit", ""))[:short_len]
            bundle_sha = str(entry.get("tar_sha256", ""))[:short_len]
            rest = parts[1 + 1 :]
            if rest and rest[0] == "issues":
                target_url = intake_fallback_path
                route_kind = "live_intake_door"
            elif rest and rest[0] == "releases" and rest[-1]:
                target_url = f"{downloads_base_path}/{rest[-1]}"
                route_kind = "self_hosted_download"
            elif rest and rest[-1].lower() == "readme.md" and len(rest) <= 1 + 1 + 1:
                target_url = f"{mirror_base_path}/{entry['readme']}"
                route_kind = "mirror_readme"
            elif len(rest) >= 1 + 1 + 1 and rest[0] in ("tree", "blob"):
                subpath = "/".join(rest[1 + 1 :])
                target_url = f"{mirror_base_path}/#{slug}:{subpath}@{commit}"
                route_kind = "mirror_subpath_anchor"
            elif len(rest) >= 1 + 1 and rest[0] == "pull":
                target_url = f"{mirror_base_path}/#{slug}:pr-{rest[1]}@{commit}"
                route_kind = "mirror_pr_anchor"
            else:
                target_url = f"{mirror_base_path}/#{slug}@{commit}"
                route_kind = "mirror_repo_anchor"
            rewritten.append(
                {
                    "original_url": raw_url,
                    "mirror_url": target_url,
                    "archive": f"{mirror_base_path}/{entry['archive']}",
                    "commit": commit,
                    "bundle_sha256_prefix": bundle_sha,
                    "route_kind": route_kind,
                }
            )
        else:
            unresolved.append(raw_url)

    return {
        "all_resolved": len(unresolved) == 0,
        "rewritten_count": len(rewritten),
        "unresolved_count": len(unresolved),
        "rewritten": rewritten,
        "unresolved": unresolved,
    }


def verify_llms_txt_and_mcp_parity(
    llms_txt: str,
    mcp_tool_names: list[str],
    *,
    has_simulated_fallback: bool = False,
) -> dict[str, Any]:
    """Verify exact 1:1 parity between `/llms.txt` tool documentation and live MCP `tools/list`."""
    stated_counts = [int(m.group(1)) for m in _STATED_TOOLS_RE.finditer(llms_txt)]
    listed_tools: list[str] = []
    in_tools_block = False
    for raw_line in llms_txt.splitlines():
        stripped = raw_line.strip()
        if _TOOL_SECTION_RE.search(stripped):
            in_tools_block = True
            continue
        if in_tools_block:
            if stripped.startswith("#"):
                in_tools_block = False
                continue
            bullet = _TOOL_BULLET_RE.match(raw_line)
            if bullet:
                listed_tools.append(bullet.group(1))

    doc_set = set(listed_tools)
    live_set = {t.strip() for t in mcp_tool_names if t.strip()}
    missing_in_mcp = sorted(doc_set - live_set)
    undocumented_in_llms = sorted(live_set - doc_set)
    count_mismatch = any(cnt != len(live_set) for cnt in stated_counts)

    passed = (
        len(missing_in_mcp) == 0
        and len(undocumented_in_llms) == 0
        and not count_mismatch
        and not has_simulated_fallback
    )
    return {
        "passed": passed,
        "documented_tool_count": len(doc_set),
        "live_mcp_tool_count": len(live_set),
        "stated_counts": stated_counts,
        "count_mismatch": count_mismatch,
        "missing_in_mcp": missing_in_mcp,
        "undocumented_in_llms": undocumented_in_llms,
        "simulated_fallback_detected": has_simulated_fallback,
    }


def run_worked_example(bundle: dict[str, Any], grid_cell: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute the deterministic end-to-end film and surface rule evaluation bundle."""
    cell = grid_cell or load_default_grid_cell()
    rule_eval = evaluate_declarative_rule_nouns(
        bundle["rules"],
        bundle["measurements"],
        hook_stage=bundle.get("hook_stage"),
    )
    stamp_clean = scan_forbidden_stamps_and_chips(
        bundle["clean_cut_ocr"],
        bundle["clean_status_chips"],
        cell,
    )
    stamp_dirty = scan_forbidden_stamps_and_chips(
        bundle["dirty_cut_ocr"],
        bundle["dirty_status_chips"],
        cell,
    )
    caption_load = score_caption_plate_and_cognitive_load(
        bundle["cues"],
        bundle["ost_events"],
        cell,
    )
    mirror_rewrite = rewrite_dead_repo_links_to_source_mirror(
        bundle["dead_urls"],
        bundle["mirror_manifest"],
        grid_cell=cell,
    )
    mcp_parity = verify_llms_txt_and_mcp_parity(
        bundle["llms_txt"],
        bundle["mcp_tools"],
        has_simulated_fallback=bool(bundle.get("has_simulated_fallback", False)),
    )
    return {
        "rule_verdict": rule_eval["verdict"],
        "evaluated_rules": rule_eval["evaluated_count"],
        "passed_rules": rule_eval["passed_count"],
        "advisory_rules": rule_eval["advisory_count"],
        "clean_cut_passed": stamp_clean["clean"],
        "dirty_cut_blocked": not stamp_dirty["clean"],
        "dirty_stamp_hit_count": len(stamp_dirty["stamp_hits"]),
        "dirty_chip_hit_count": len(stamp_dirty["chip_hits"]),
        "caption_and_load_passed": caption_load["passed"],
        "max_center_offset_px": caption_load["max_center_offset_px"],
        "max_observed_cps": caption_load["max_observed_cps"],
        "mirror_all_resolved": mirror_rewrite["all_resolved"],
        "mirror_rewritten_count": mirror_rewrite["rewritten_count"],
        "mcp_parity_passed": mcp_parity["passed"],
        "live_mcp_tool_count": mcp_parity["live_mcp_tool_count"],
    }
