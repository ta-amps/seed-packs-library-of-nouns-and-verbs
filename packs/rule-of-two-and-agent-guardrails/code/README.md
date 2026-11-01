# rule-of-two-and-agent-guardrails (`rule_of_two_guardrails`)

Standard-library implementation of grid-governed agent capability lattices, bidirectional privacy placeholder vaults, and model license-tier routing firewalls:
- `RuleOfTwoCapabilityLattice`: monotone taint and capability join-semilattice over multi-step tool DAGs tracking `untrusted_input` (`A`), `sensitive_access` (`B`), and `external_mutation_or_egress` (`C`), permitting at most two unapproved legs and returning a deterministic `403` verdict plus minimal witness path whenever a step or transitive dataflow combines all three without a scoped `human_steward_approval` token.
- `BidirectionalPrivacyPlaceholderGateway`: outbound deterministic typed placeholder vault (`<ENTITY_TYPE_001>`) preserving coreference and SHA-256 hex digests, paired with lossless inbound re-hydration and a bidirectional zero-leak / round-trip evaluation harness.
- `ModelLicenseTierFirewall`: deterministic payload router across `contributor_training_allowed`, `standard_zero_retention`, and `local_open_weights` tiers based on sensitivity, synthetic provenance, vault state, and license tags.
- `ZeroHardcodedValuesAstGate` and `scan_directory_for_hardcoded_values`: mechanical Python AST scanner verifying zero non-identity inline numeric literals across operational modules.

Run checks:
```bash
make check
```
