# Grep, string and format rules

## What this pack lets workers do

A collection of nouns and verbs for Aho-Corasick literal scanning, portable grep rules, Unicode and entropy security checks and strict JSON and copy formatting. Workers use grid-governed rule engines to scan multi-pattern literals in single-pass `O(|text| + matches)` time with `AhoCorasickAutomaton`, check ECMA-262 regex portability, secret prefixes, local paths, sentence-level negation and placeholder stamps with `PortableGrepRuleRunner`, catch Trojan Source bidi overrides, Unicode Tag ASCII smuggling, SHA-256 hashed private names and high-entropy secrets with `UnicodeAndEntropySecurityScanner` and enforce canonical duplicate-free JSON and balanced captions with `StrictJsonAndCopyFormatter`.

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Mask matched secrets and hashed names in diagnostics, exempt 32..64-char lowercase hex SHA-256/MD5 pins from entropy blocks and enforce `ZeroHardcodedValuesAstGate` |
| `spec.portable-grep-unicode-and-format-grid` | Declarative Unicode Tag/bidi ranges, hex-digest exemption bounds and 53-bit IEEE-754 safe-integer limits |
| `rules.negation-entropy-and-caption-wrapping` | Zero-model rules for sentence-level outbound negation exemptions and orphan-free clause-balanced caption wrapping |
| `tool.rule-engine` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.rule-engine-receipt` | JSON Schema for Aho-Corasick hits, regex portability, Tag smuggling decodes, entropy counts and canonical JSON/captions |
| Worked example | Made-up text, Unicode, JSON and caption bundle (`example.rule-engine-bundle`) and recomputed receipt (`example.rule-engine-receipt`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `scan-literals-and-portable-grep-rules` | agent, no model | Run single-pass Aho-Corasick scans, check ECMA-262 regex portability, scrub `/home/` and `/Users/` paths and block placeholder UI stamps |
| `audit-unicode-smuggling-and-entropy` | agent, no model | Check NFC normalization, decode Unicode Tag smuggling, flag Trojan bidi/invisible chars, match SHA-256 name hashes and mask high-entropy tokens |
| `verify-strict-json-copy-and-ast-gate` | agent, no model | Reject duplicate JSON keys, `NaN`/`Infinity` and unsafe integers, check HTML entities/em-dashes, wrap captions and run `ZeroHardcodedValuesAstGate` |

## How to use it

Run `make check` in [code/](code/README.md) to run unit tests covering `AhoCorasickAutomaton` failure/output links, ECMA-262 regex portability, sentence-level outbound negation, secret prefix masking, Trojan Source bidi and Unicode Tag ASCII smuggling decoding, SHA-256 name-hash matching, Shannon-entropy hex exemptions, strict JSON canonicalization, balanced caption wrapping, `ZeroHardcodedValuesAstGate` self-scanning and worked-example receipt recomputation.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or activated, and no worker has claimed or run these tasks through the work-engine.
- Deterministic lexical, Unicode and entropy scanners catch structural leaks and formatting defects offline; they do not replace human or `distinct_reviewer` judgment on domain claims.
- Shannon-entropy scanning intentionally exempts 32..64-character lowercase hexadecimal digests so pinned content hashes pass without false positives; hex-encoded raw keys still require prefix or context rules.
