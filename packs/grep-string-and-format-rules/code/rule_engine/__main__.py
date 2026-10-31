"""CLI entry point for grep-string-and-format-rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .aho_corasick import AhoCorasickAutomaton, load_default_grid_spec
from .formatter import StrictJsonAndCopyFormatter
from .grep_rules import PortableGrepRuleRunner
from .unicode_entropy import UnicodeAndEntropySecurityScanner


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()

    # 1. AhoCorasickAutomaton multi-pattern literal scan
    ac = AhoCorasickAutomaton(case_insensitive=False)
    for pat in bundle["aho_patterns"]:
        ac.add_pattern(str(pat), word_boundary=True)
    ac_hits = ac.scan(str(bundle["aho_text"]))

    # 2. PortableGrepRuleRunner checks
    runner = PortableGrepRuleRunner(spec=cfg)
    good_regex = runner.validate_ecmascript_portable(str(bundle["portable_pattern"]))
    bad_regex = runner.validate_ecmascript_portable(str(bundle["non_portable_pattern"]))
    grep_audit = runner.audit_text(str(bundle["grep_audit_sample"]))

    # 3. UnicodeAndEntropySecurityScanner checks
    scanner = UnicodeAndEntropySecurityScanner(spec=cfg)
    probe_unicode_str = str(bundle["unicode_probe_prefix"]) + "".join(
        chr(int(cp)) for cp in bundle["unicode_probe_codepoints"]
    )
    uni_res = scanner.scan_unicode(probe_unicode_str)
    name_hits = scanner.scan_blocked_name_hashes(str(bundle["name_hash_probe_text"]))
    ent_res = scanner.scan_and_mask_high_entropy_tokens(str(bundle["entropy_probe_text"]))

    # 4. StrictJsonAndCopyFormatter checks
    fmt = StrictJsonAndCopyFormatter(spec=cfg)
    clean_json = fmt.parse_and_canonicalize_json(str(bundle["clean_json_sample"]))
    dup_json = fmt.parse_and_canonicalize_json(str(bundle["duplicate_key_json_sample"]))
    entity_audit = fmt.audit_plain_copy(str(bundle["html_entity_copy_sample"]))
    wrapped = fmt.wrap_balanced_caption(str(bundle["caption_sample"]))

    return {
        "aho_matched_patterns": [str(h["pattern"]) for h in ac_hits],
        "portable_regex_passed": bool(good_regex["portable"]),
        "non_portable_regex_rejected": not bool(bad_regex["portable"]),
        "outbound_violation_count": len(grep_audit["outbound_violations"]),
        "secret_prefix_hit_count": len(grep_audit["secret_prefix_hits"]),
        "scrubbed_home_paths": int(grep_audit["home_path_scrub"]["path_leak_count"]),
        "accusatory_hit_count": len(grep_audit["accusatory_copy_hits"]),
        "visible_stamp_hit_count": len(grep_audit["visible_stamp_hits"]),
        "trojan_bidi_hit_count": len(uni_res["trojan_bidi_hits"]),
        "decoded_tag_payload": str(uni_res["decoded_tag_payload"]),
        "blocked_name_hash_hits": len(name_hits),
        "high_entropy_hit_count": len(ent_res["high_entropy_hits"]),
        "exempted_hex_digest_count": int(ent_res["exempted_hex_digest_count"]),
        "clean_json_canonical": str(clean_json["canonical_json"]),
        "duplicate_json_rejected": not bool(dup_json["valid"]),
        "html_entity_leaks": list(entity_audit["html_entity_leaks"]),
        "wrapped_caption_lines": list(wrapped["lines"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run grep-string-and-format-rules bundle evaluation.")
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    cfg = load_default_grid_spec()
    indent = int(cfg["formatter"]["json_indent"])
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
