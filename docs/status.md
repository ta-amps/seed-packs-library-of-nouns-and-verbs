# Status and evidence boundaries

This repository is instructions, synthetic examples and a library of proposed seed
packs, dated October 29, 2026. It does not deploy a service and contains no active
pack. The [packs/](../packs/README.md) library holds twenty proposals that are validated
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
| Seed pack library | Twenty proposed packs, 411 nouns and 128 verb templates, rebuilt byte for byte and validated offline by `make check`; not installed, imported, admitted or activated |
| Pack code | The video and motion pack ships its tested code in `packs/video-motion/code`. Its own CI job runs every test with real renders and the pinned Tessera; the root `make check` pins the code by digest, never runs it, and stays install-free |
| Pack scope probe | On a throwaway local Store, a key on the importing team's surface read every pack noun, claimed and submitted every instantiated template and updated a success record by compare-and-set; keys on other surfaces or none saw nothing. HTTP grants were not exercised |
| Pack inventory | [Plain-English map](pack-inventory.md) of packs for making a video, building nonprofit kits and keeping knowledge fresh, with what is still missing |
| Tessera model validation | Every pack noun and verb passed Tessera's own `RecordWrite`, `TaskSpec`, category, relation, `NounRef` and execution-report checks at the commit in [VALIDATION.json](../packs/VALIDATION.json); shape evidence only |
| Pack worked examples | Seven deterministic examples (repository and security finding checks, finding record checks, check validation, evaluation arithmetic, benchmark staleness, text contrast) are recomputed by `make check`; they are synthetic, except that the finding record checks also recheck eight real public findings |
| Prior-art surveys | The prior-art pack's two worked examples are real surveys, checked against their template's shape only: this library at `54c58c9` with Tessera's docs at `7e7433c`, and a hackathon directory of about 740 repositories for a PII redaction tool, which lists seven candidates unranked and runs none. Each records the sources it did not search |
| Pack code | The code composition pack keeps its tested code as nouns in `packs/code-composition/code/`. A path-filtered CI job runs that code's checks and the pinned Tessera integration; the root `make check` only hashes it. No worker has run it |
| Pack execution | None. No verb from the library has been claimed, run, measured or reviewed |
| Recurring refresh | Daily schedule proposal nouns for tool discovery, benchmark scores and freshness checks only; they need Tessera's flag-gated schedule support, which is being designed, and no scheduler is activated |

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
