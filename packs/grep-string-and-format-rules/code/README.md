# grep-string-and-format-rules (`rule_engine`)

Standard-library implementation of grid-governed multi-pattern literal matching, portable grep rules, Unicode/entropy security scanning, and strict JSON/caption formatting:
- `AhoCorasickAutomaton`: trie + failure-link + output-link multi-pattern scanner running in single-pass `O(|text| + matches)` with optional word-boundary checks.
- `PortableGrepRuleRunner`: ECMA-262 portable regex syntax validator, sentence-level negation-exempt outbound effect scanner, secret prefix scanner (`ghp_`, `github_pat_`, `tsk_`, `tan_`, `hmk_`, `AKIA`, `sk-`), local home path scrubber, non-accusatory public-good copy check, and non-functional visible stamp blocker.
- `UnicodeAndEntropySecurityScanner`: NFC normalization verifier, Trojan Source bidi detector, zero-width/variation-selector detector, Unicode Tag block ASCII smuggling decoder (`U+E0000..U+E007F`), zero-leak SHA-256 name-hash blocklist checker, and Shannon-entropy secret detector exempting 32..64-char lowercase hex digests.
- `StrictJsonAndCopyFormatter`: strict JSON canonicalizer rejecting duplicate keys, `NaN`/`Infinity`, and integers exceeding IEEE-754 `MAX_SAFE_INTEGER`, plus HTML entity leak detection, zero-em-dash check, and clause-balanced caption wrapping.
- `ZeroHardcodedValuesAstGate`: mechanical Python AST scanner verifying zero non-identity inline numeric literals across `rule_engine/`.

Run checks:
```bash
make check
```
