"""Apply a pre-registered promotion rule to candidate, champion and base evaluations.

Keeping the champion is a valid outcome. A promotion moves only a private champion pointer that the next
round compares against; this code moves nothing and only returns the decision.

An evaluation is {split: {"aggregate": {metric: value}, "exact": [0 or 1 per frozen row], "ids_sha256": ...}}.
"""

from __future__ import annotations

from typing import Any

from .bootstrap import paired_bootstrap
from .draw import digest

RULE_FORMAT = "tessera.continuous-tuning.promotion-rule.v1"
SPLITS = {"test", "fresh", "sanity", "dev"}


def check_rule(rule: dict[str, Any]) -> list[str]:
    """Problems that make a rule unusable; an empty list means it can decide."""
    problems: list[str] = []
    if rule.get("format") != RULE_FORMAT or rule.get("version") != 1:
        return [f"unsupported promotion rule: format {rule.get('format')!r}, version {rule.get('version')!r}"]
    promotion = rule.get("promotion", {})
    for name in ("primary_metric", "min_delta", "paired_bootstrap", "no_regression", "integrity", "effects"):
        if name not in promotion:
            problems.append(f"promotion.{name} is missing")
    boot = promotion.get("paired_bootstrap", {})
    if not (isinstance(boot.get("resamples"), int) and boot["resamples"] >= 100):
        problems.append("paired_bootstrap.resamples is an integer of at least 100")
    if not (isinstance(boot.get("confidence"), (int, float)) and 0.5 < boot["confidence"] < 1):
        problems.append("paired_bootstrap.confidence is between 0.5 and 1")
    if not (isinstance(boot.get("seed"), str) and boot["seed"]):
        problems.append("paired_bootstrap.seed is a fixed string")
    for guard in promotion.get("no_regression", []):
        if guard.get("split") not in SPLITS or not isinstance(guard.get("max_drop"), (int, float)):
            problems.append(f"guard {guard.get('name')!r} needs a known split and a numeric max_drop")
    return problems


def metric(evaluation: dict[str, Any], split: str, name: str) -> float | None:
    part = evaluation.get(split)
    return None if part is None else part["aggregate"].get(name)


def same_rows(a: dict[str, Any], b: dict[str, Any]) -> bool:
    for key in ("ids", "ids_sha256"):
        if key in a or key in b:
            return a.get(key) == b.get(key)
    return False


def decide(rule: dict[str, Any], candidate: dict[str, Any], champion: dict[str, Any], base: dict[str, Any],
           integrity: dict[str, bool]) -> dict[str, Any]:
    """The decision record: every check with what was observed, and promote_candidate or keep_champion."""
    problems = check_rule(rule)
    if problems:
        raise ValueError("; ".join(problems))
    promotion = rule["promotion"]
    primary = promotion["primary_metric"]
    boot = promotion["paired_bootstrap"]
    if not same_rows(candidate["test"], champion["test"]):
        raise ValueError("candidate and champion were not scored on the same frozen rows")
    paired = paired_bootstrap(candidate["test"]["exact"], champion["test"]["exact"], boot["resamples"], boot["seed"],
                              boot["confidence"])
    checks: list[dict[str, Any]] = [
        {"check": f"test {primary} improves by at least {promotion['min_delta']}",
         "passed": paired["delta"] >= promotion["min_delta"], "observed": paired["delta"]},
        {"check": "paired bootstrap lower bound above zero",
         "passed": paired["lower"] > boot["require_lower_bound_above"], "observed": paired["lower"]},
    ]
    for guard in promotion["no_regression"]:
        reference = base if guard.get("against") == "base" else champion
        if guard["split"] not in candidate or guard["split"] not in reference:
            passed = None if guard.get("optional") else False
            checks.append({"check": guard["name"], "passed": passed, "observed": "not evaluated"})
            continue
        new = metric(candidate, guard["split"], guard["metric"])
        old = metric(reference, guard["split"], guard["metric"])
        passed = new is not None and old is not None and new >= old - guard["max_drop"]
        checks.append({"check": guard["name"], "passed": passed, "observed": [old, new]})
    for name in promotion["integrity"]:
        checks.append({"check": f"integrity: {name}", "passed": bool(integrity.get(name))})
    required = [check for check in checks if check["passed"] is not None]
    promote = all(check["passed"] for check in required)
    return {
        "rule_id": rule["rule_id"],
        "rule_sha256": digest(rule),
        "outcome": "promote_candidate" if promote else "keep_champion",
        "paired_test": paired,
        "checks": checks,
        "effects": promotion["effects"],
    }
