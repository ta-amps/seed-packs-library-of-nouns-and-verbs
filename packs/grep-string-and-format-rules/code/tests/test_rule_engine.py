"""Unit tests for grep-string-and-format-rules (including ZeroHardcodedValuesAstGate self-scan)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rule_engine import (
    AhoCorasickAutomaton,
    PortableGrepRuleRunner,
    StrictJsonAndCopyFormatter,
    UnicodeAndEntropySecurityScanner,
    ZeroHardcodedValuesAstGate,
)
from rule_engine.__main__ import run_bundle

PACK_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = CODE_DIR / "rule_engine"


class RuleEngineTests(unittest.TestCase):
    def test_package_itself_passes_zero_hardcoded_values_ast_gate(self) -> None:
        report = ZeroHardcodedValuesAstGate.scan_paths([PKG_DIR])
        self.assertTrue(report["passed"], f"Unexpected magic literals in rule_engine: {report}")
        self.assertGreaterEqual(report["files_scanned"], 7)

        bad_scan = ZeroHardcodedValuesAstGate.scan_source("def bad_limit(s: str) -> bool:\n    return len(s) > 42\n")
        self.assertFalse(bad_scan["passed"])
        self.assertEqual(bad_scan["violation_count"], 1)

    def test_aho_corasick_overlapping_suffix_links_and_word_boundaries(self) -> None:
        ac = AhoCorasickAutomaton(case_insensitive=False)
        for pat in ("he", "she", "his", "hers"):
            ac.add_pattern(pat)
        hits = [h["pattern"] for h in ac.scan("ushers")]
        self.assertEqual(hits, ["she", "he", "hers"])

        wb_ac = AhoCorasickAutomaton(case_insensitive=True)
        wb_ac.add_pattern("coming soon", word_boundary=True)
        wb_ac.add_pattern("local run", word_boundary=True)
        self.assertEqual(len(wb_ac.scan("Status: COMING SOON in this local run card")), 2)
        self.assertEqual(len(wb_ac.scan("local_runner coming_sooner")), 0)

    def test_portable_grep_rules_negation_secrets_paths_accusatory_and_stamps(self) -> None:
        runner = PortableGrepRuleRunner()
        self.assertTrue(runner.validate_ecmascript_portable(r"^[a-z0-9_-]{1,32}$")["portable"])
        self.assertFalse(runner.validate_ecmascript_portable(r"(?<=foo)bar")["portable"])
        self.assertFalse(runner.validate_ecmascript_portable(r"(?P<name>[a-z]+)")["portable"])
        self.assertFalse(runner.validate_ecmascript_portable(r"([a-z]+)\1")["portable"])

        negated = "Workers never send external messages and do not deploy unreviewed code."
        self.assertEqual(len(runner.scan_outbound_effects(negated)), 0)

        unnegated = "Worker " + "sends" + " external report to https://example.invalid/hook."
        self.assertEqual(len(runner.scan_outbound_effects(unnegated)), 1)

        # Construct made-up test credentials dynamically so source files hold zero literal keys
        dyn_secrets = " ".join([
            "ghp_" + ("A" * 32),
            "github_pat_" + ("B" * 42),
            "tsk_" + ("c" * 30),
            "tan_" + ("d" * 30),
            "hmk_" + ("e" * 24),
            "AKIA" + ("9" * 16),
            "sk-" + ("Z" * 28),
        ])
        sec_hits = runner.scan_secret_prefixes(dyn_secrets)
        self.assertEqual(len(sec_hits), 7)
        self.assertTrue(all("..." in h["masked_match"] for h in sec_hits))

        scrub = runner.scrub_home_paths("Loaded /home/ci_bot/data.json and /Users/dev_box/cfg.toml")
        self.assertEqual(scrub["path_leak_count"], 2)
        self.assertEqual(scrub["scrubbed_text"], "Loaded <HOME>/data.json and <HOME>/cfg.toml")

        self.assertEqual(len(runner.scan_public_good_accusatory_copy("A corrupt and fraudulent report")), 2)
        stamps = runner.scan_visible_stamps(
            "MADE-UP EXAMPLE | AI-generated voice | local run | planned | not running | coming soon"
        )
        self.assertEqual(len(stamps), 6)

    def test_unicode_nfc_trojan_bidi_zero_width_variation_tag_smuggling_and_entropy(self) -> None:
        custom_hash = hashlib.sha256(b"internal-codename-omega").hexdigest()
        scanner = UnicodeAndEntropySecurityScanner(blocked_name_hashes={custom_hash})

        # Non-NFC decomposed e + combining acute (U+0301 = 769)
        decomposed = "cafe" + chr(769)
        uni_nfc = scanner.scan_unicode(decomposed)
        self.assertFalse(uni_nfc["is_nfc"])

        # Trojan bidi (U+202E=8238, U+2066=8294, U+061C=1564), zero-width (U+200B=8203, mid-text BOM=65279),
        # variation selector (U+FE0F=65039, U+E0100=917760) and Tag ASCII smuggling ("prompt" -> 0xE0000 + ord)
        smuggled_word = "prompt"
        tag_seq = "".join(chr(917504 + ord(c)) for c in smuggled_word)
        payload = "safe" + chr(8238) + chr(8294) + chr(1564) + chr(8203) + chr(65279) + chr(65039) + chr(917760) + tag_seq
        uni = scanner.scan_unicode(payload)
        self.assertEqual(len(uni["trojan_bidi_hits"]), 3)
        self.assertEqual(len(uni["zero_width_hits"]), 2)
        self.assertEqual(len(uni["variation_selector_hits"]), 2)
        self.assertEqual(uni["decoded_tag_payload"], "prompt")

        # SHA-256 normalized name-hash blocklist check (case + underscore separator normalization)
        name_hits = scanner.scan_blocked_name_hashes("Check INTERNAL_CODENAME_OMEGA reference")
        self.assertEqual(len(name_hits), 1)
        self.assertNotIn("omega", name_hits[0]["masked_token"].lower())

        # Shannon entropy: exempts 32-char MD5 and 64-char SHA-256 lowercase hex pins, flags mixed-class secret
        md5_hex = hashlib.md5(b"pin-a").hexdigest()
        sha256_hex = hashlib.sha256(b"pin-b").hexdigest()
        high_ent = "Qp8!zW3#mK9$vR2@xL7^nB4&tY6*"
        ent = scanner.scan_and_mask_high_entropy_tokens(f"Pins {md5_hex} and {sha256_hex} vs {high_ent}")
        self.assertEqual(ent["exempted_hex_digest_count"], 2)
        self.assertEqual(len(ent["high_entropy_hits"]), 1)
        self.assertIn("<REDACTED_HIGH_ENTROPY>", ent["masked_text"])
        self.assertIn(sha256_hex, ent["masked_text"])

    def test_strict_json_em_dash_html_entities_and_balanced_caption_wrapper(self) -> None:
        fmt = StrictJsonAndCopyFormatter()

        dup = fmt.parse_and_canonicalize_json('{"a": 1, "b": 2, "a": 3}')
        self.assertFalse(dup["valid"])
        self.assertEqual(dup["duplicate_keys"], ["a"])

        nan_res = fmt.parse_and_canonicalize_json('{"score": NaN}')
        self.assertFalse(nan_res["valid"])
        self.assertEqual(nan_res["non_finite_constants"], ["NaN"])

        unsafe_int = (1 << 53) + 7
        big_res = fmt.parse_and_canonicalize_json(f'{{"id": {unsafe_int}}}')
        self.assertFalse(big_res["valid"])
        self.assertEqual(len(big_res["unsafe_integers"]), 1)

        copy_check = fmt.audit_plain_copy("Alpha" + chr(8212) + "Beta &nbsp; &mdash; &rarr;")
        self.assertFalse(copy_check["passed"])
        self.assertEqual(copy_check["em_dash_count"], 1)
        self.assertGreaterEqual(len(copy_check["html_entity_leaks"]), 3)

        # Rejects 1-word orphan captions and captions overflowing max_lines * max_chars_per_line
        orphan = fmt.wrap_balanced_caption("Summary")
        self.assertFalse(orphan["valid"])
        overflow = fmt.wrap_balanced_caption(
            "Verified static filters protect every distributed storage pool from redundant high latency upstream database reads"
        )
        self.assertFalse(overflow["valid"])

        # Balanced two-line caption: avoids 1-word orphans and avoids ending line 1 with 'the'/'of'/'from'
        good_wrap = fmt.wrap_balanced_caption(
            "Verified static filters protect the storage pool from redundant reads"
        )
        self.assertTrue(good_wrap["valid"])
        self.assertEqual(len(good_wrap["lines"]), 2)
        for line in good_wrap["lines"]:
            self.assertLessEqual(len(line), 42)
            self.assertGreaterEqual(len(line.split()), 2)
        first_line_last_word = good_wrap["lines"][0].split()[-1].lower()
        self.assertNotIn(first_line_last_word, {"a", "an", "the", "of", "in", "to", "for", "from", "and", "or"})

    def test_worked_example_recomputes_exact_receipt_and_cli_runs(self) -> None:
        src = json.loads((PACK_DIR / "source.json").read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in src["nouns"]}
        bundle = nouns["example.rule-engine-bundle"]
        expected = nouns["example.rule-engine-receipt"]["instance"]
        recomputed = run_bundle(bundle)
        self.assertEqual(recomputed, expected)

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
            json.dump(bundle, tmp)
            tmp.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "rule_engine", "--bundle", tmp.name],
                cwd=CODE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            cli_out = json.loads(proc.stdout)
            self.assertEqual(cli_out, expected)


if __name__ == "__main__":
    unittest.main()
