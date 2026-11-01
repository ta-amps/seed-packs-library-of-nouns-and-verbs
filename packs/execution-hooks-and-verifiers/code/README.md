# execution-hooks-and-verifiers (`hooks_verifiers`)

Standard-library implementation of:
- `PortableHookCompiler`: compiles declarative 4-stage hook specifications (`pre_claim`, `pre_tool`, `post_step`, `pre_submit`) for `claude_code`, `muse_code`, `opencode`, and `pi_coding_agent` with `disable_bypass_permissions=True`, and evaluates `pre_tool` calls (`allow | deny | rewrite_hint`).
- `ComposableVerifierDagAndMutationGate`: executes topological `pre_submit` Verifier DAGs, runs a Checks-of-Checks mutation sensitivity gate (`trusted | revise | reject`), and extracts normalized `negative_tombstone` dead-end signatures.

Run checks:
```bash
make check
```
