# Status and evidence boundaries

This repository is instructions, synthetic examples and a library of proposed seed
packs, dated October 29, 2026. It does not deploy a service and contains no active
pack. The [packs/](../packs/README.md) library holds seventy-nine proposals that are validated
examples only: none is installed, imported, admitted or activated, and no worker has
run their verbs. Read the target's live schemas before sending work.

| Item | Status here |
| --- | --- |
| HTTP/MCP request examples | Authored from existing Tessera contracts; placeholders require actual lease and record values |
| Local validation | `make check` parses and checks these files offline; its output supplies the test result |
| Live or native harness evaluation | Not performed by this repository's checks |
| Generic pack manifest/importer | Manifest is proposed review transport; no importer exists here |
| Category/profile composition | Guidance only; no automatic resolver, inheritance or merge engine |
| Shim-rule nouns | Versioned rule data is an architectural direction; a CAS write alone does not activate a rule |
| Capability negotiation | Use live discovery, principal grants and the owning brief; no new negotiation protocol |
| Reusable code admission | Existing owning policy must check bytes, licenses, provenance and required review |
| Provider usage | No model is called by this repository; example measurements are unknown unless explicitly measured |
| Automatic ongoing work | None; no scheduler, daemon or server inference is installed |
| Capability research | Proposed source-to-decision seed workflow; no feed/inbox connector, automated comparison or adoption service is active |
| Research seed authoring | Tessera owns a bounded task builder with synthetic requests for discovery, collector preparation, schedule proposals and one scan; this repository remains a guide |
| Seed pack library | Seventy-nine proposed packs, 1510 nouns and 487 verb templates, rebuilt byte for byte and validated offline by `make check`; not installed, imported, admitted or activated |
| Pack code | The video and motion pack ships its tested code in `packs/video-motion/code`. Its own CI job runs every test with real renders and the pinned Tessera; the root `make check` pins the code by digest, never runs it, and stays install-free |
| Pack scope probe | On a throwaway local Store, a key on the importing team's surface read every pack noun, claimed and submitted every instantiated template and updated a success record by compare-and-set; keys on other surfaces or none saw nothing. HTTP grants were not exercised |
| Pack inventory | [Plain-English map](pack-inventory.md) of packs for making a video, building nonprofit kits and keeping knowledge fresh, with what is still missing |
| Tessera model validation | Every pack noun and verb passed Tessera's own `RecordWrite`, `TaskSpec`, category, relation, `NounRef` and execution-report checks at the commit in [VALIDATION.json](../packs/VALIDATION.json); shape evidence only |
| Pack worked examples | Forty-five deterministic examples (repository and security finding checks, finding record checks, direction record checks, status report checks, release receipt checks, old-name sweep checks, narration release checks, explainer video release checks, promotion decision checks, company brief checks, research report checks, options review checks, data findings checks, design finding checks, step packet checks, unattended run report checks, stored solution checks, move plan checks, technical note checks, sign-off checks, accessibility finding checks, heuristic finding checks, readiness report checks, session note checks, video QA report checks, edit summary checks, video review checks, cut-down checks, title checks, audience acceptance checks, dossier checks, conformance report checks, panel synthesis checks, review run checks, annoyance finding checks, edge case result checks, baseline comparison checks, health finding checks, thumbnail text contrast, check validation, evaluation arithmetic, benchmark staleness, text contrast, theme contrast) are recomputed by `make check`; they are synthetic, except that the finding record checks also recheck eight real public findings |
| Prior-art surveys | The prior-art pack's two worked examples are real surveys, checked against their template's shape only: this library at `54c58c9` with Tessera's docs at `7e7433c`, and a hackathon directory of about 740 repositories for a PII redaction tool, which lists seven candidates unranked and runs none. Each records the sources it did not search |
| Pack code | The code composition pack keeps its tested code as nouns in `packs/code-composition/code/`. A path-filtered CI job runs that code's checks and the pinned Tessera integration; the root `make check` only hashes it. No worker has run it |
| Pack code, standard library only | The narrated explainer video, continuous tuning, options chain review, checked data analysis, video QA, wiring and conformance checks, edge and corner cases and codebase health review packs ship small standard-library code in `packs/<pack>/code/` whose tests recompute each pack's worked example; path-filtered CI jobs run them on Python 3.10 and 3.12, and the root `make check` only hashes them. The tuning code's draws, bootstrap and decisions match values recorded from Tessera's own continuous tuning example. The voice narration, public company research and deep research report packs' worked-example arithmetic, quotes and citations are rechecked by `make check`'s tests, and so are the screenshot design review's seven measured checks, from its layout facts, and the video editing, review, cut-down, thumbnail and audience acceptance packs' pacing, counts, lengths, sizes and decisions, and the living research dossier and persona panel packs' refresh dates, counts, view digests, reading order and quotes, and the continuous self-review, annoyance hunt, edge and corner cases, regression watch and codebase health review packs' picks, diffs, coverage, ranks, outcomes and statuses. The video QA code's contrast is checked against the accessibility audit pack's recorded ratios; the edge case generator's daylight saving cases are checked against the time zone database, and the health checks' ages against throwaway git repositories with fixed author dates. No worker has run any of it |
| Pack code, accessibility audit | The accessibility audit pack ships standard-library contrast and structure lint code in `packs/accessibility-audit/code/`, whose tests check published reference ratios and every lint rule and recompute the pack's contrast and lint worked examples; a path-filtered CI job runs them on Python 3.10 and 3.12, and the root `make check` only hashes it. No worker has run it in a claimed verb |
| Pack execution | None. No verb from the library has been claimed, run, measured or reviewed |
| Recurring refresh | Daily schedule proposal nouns for tool discovery, benchmark scores, freshness checks and agent harness feeds only; they need Tessera's flag-gated schedule support, which is being designed, and no scheduler is activated. The continuous self-review pack's review rotation is a template and a worked example that wait for a person's approval, not a schedule proposal noun |

Tessera remains the single authority for nouns, verbs, permissions, execution
observations and receipts. A repository of examples is not another canonical
artifact index. A review manifest can reference accepted Tessera records once
their actual versions and permissions exist.

New submissions can carry optional `execution_report` data on deployments exposing
the history APIs. Check for `recall_execution`, `list_executions` and
`get_execution` in tools/list. Telemetry is immutable on accepted replay and
worker reported; old submissions are not automatically backfilled. Anonymous
history retains session privacy and expiry. No report or matching score grants
automatic reuse, verification or public publication.

Reference implementation and contracts:

- [Tessera repository](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine)
- [Tessera access contract](https://tessera.ta-amps.workers.dev/connect.json)
- [Tessera OpenAPI](https://tessera.ta-amps.workers.dev/v1/openapi.json)
- [Tessera agent instructions](https://tessera.ta-amps.workers.dev/llms.txt)

These links identify sources to inspect. The local checker does not fetch them or
assert that a specific public deployment currently matches every example.
