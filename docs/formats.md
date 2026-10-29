# Payloads and proposed pack format

Files under `examples/http/` are JSON request bodies for current Tessera operations.
Files under `examples/mcp/` are JSON-RPC requests. They are examples, not live ids,
credentials, measured work or a queue initializer. The validator checks the narrow
profile used here; the owning API remains authoritative.

| File | Actual operation |
| --- | --- |
| [session](../examples/http/session.json) | `POST /v1/session/anonymous` |
| [claim](../examples/http/claim.json) | `POST /v1/tasks/claim` |
| [demo noun](../examples/http/demo-put.json) | `POST /v1/stores/demo.artifacts/records/SYNTHETIC-addition-v1` |
| [keyed candidate](../examples/http/noun-put.json) | `POST /ns/<namespace>/v1/stores/pack.candidates/records/SYNTHETIC-addition-v1` |
| [verb seed](../examples/http/verb-enqueue.json) | `POST /ns/<namespace>/v1/tasks` in an already defined queue |
| [submit](../examples/http/submit.json) | `POST /v1/tasks/submit` with `Idempotency-Key` |
| [MCP put](../examples/mcp/put-record.json) | `tools/call` with name `put_record` |
| [MCP submit](../examples/mcp/submit.json) | `tools/call` with name `submit` |

Use `Content-Type: application/json`. MCP also uses
`Accept: application/json, text/event-stream`. Except discovery and session mint,
these requests need a bearer credential with the corresponding grants. The keyed
namespace belongs in the path; anonymous requests use the namespace assigned by
their bearer. Never substitute a guessed shared namespace.

## Core fields, categories and descriptive facets

The governance envelope uses `namespace`, `producer_surface`, `visibility_scope`,
`allowed_surfaces`, `target_cohorts` and `tags`; identity determines ownership.
Not every endpoint accepts every field in its body: the URL and bearer can supply
namespace/owner. Follow that endpoint's descriptor. Never forge owner ids or
surface identity. The keyed example explicitly uses `private`, empty surface
allowlists and quarantine metadata. None of these tags grants access.

The noun's `value.category_id` is `noun.reflex_procedure`; its category tag agrees.
The verb's `brief.category_id` and `kind` use `verb.solve_draft`. Additional tags
such as `domain:arithmetic`, `synthetic:true` and `spdx:MIT` are descriptive facets.
A primary category and all category aliases must agree. Multiple typed relations
or descriptive parents do not create executable inheritance or physical partitions.

Keep flexible metadata inside the allowed noun `value` or task `brief`. For
example, `extensions: {"example.org/library": {"service_window": "synthetic"}}`
can describe a domain facet without changing core columns. A namespace isolates
authority; a category organizes meaning. A schema describes a shape; a license tag
is a claim requiring provenance; neither proves the artifact is correct or safe.

The procedure in the example is ordinary data. Storing it does not install a tool,
run Python, wire a compiler node or activate a shim. A consuming worker must have
a compatible contract and explicit permission. The same applies to URLs, formulas,
files, feed items, API descriptions and DAG recipes.

## Work contract data inside a brief

The seed brief records outcome, pinned input references, output checks, required
capabilities, guidance strength, resource limits and review policy. These nested
fields are authoring data in an existing `TaskSpec`, not new server enforcement.
The current API enforces its identity, queue, effect, lease and storage boundaries.
An executing worker must enforce the brief's runtime/call budget and checks.

`depends_on` contains existing task ids, not file paths or future ids. Empty
dependencies in the example are intentional. Split work only when the child has
an independent outcome or meaningful permission/recovery boundary. Do not turn
each arithmetic operation or read into another scheduled task.

## Proposed manifest: review transport only

[pack-manifest.proposed.json](../examples/pack-manifest.proposed.json) groups the
candidate and seed files with SHA-256 byte digests. The `format` ends in
`proposal.v1`, `status` is `proposal_only`, and `importer` is `null` with a reason.
No current endpoint consumes it. It is not a promised future standard or a
separate catalog database. Accepted artifacts and evidence belong in Tessera.

The manifest's file digests pin the exact checked-in bytes, including whitespace.
They are not Tessera canonical receipt hashes. For remote references pin the real
namespace, store/key/version and content digest under their governing policy;
do not replace a missing hash with zeros or an invented measurement.

## Seed pack files

Each folder in [packs/](../packs/README.md) holds an authored `source.json`, a README and
three generated files. `scripts/build_packs.py` builds them offline and byte for byte;
`make check` fails when a committed byte differs from a fresh build.

| File | Contents |
| --- | --- |
| `nouns.json` | `RecordWrite` bodies: store, a key that carries the pack version, `expected_version: 0`, `surface_only` governance, a `status:quarantined` tag and the value. The namespace is assigned by the owner, so it is left out |
| `verbs.json` | `TaskSpec` templates in the placeholder queue `conformance-seed-packs`, with pinned pack nouns, unfilled slots, typed input and output schemas, outcomes, acceptance checks, bounds and an optional execution-report template |
| `manifest.json` | Format `ta-amps.seed-pack.proposal.v1`: file digests, each noun's value SHA-256, each verb's idempotency key and execution shape fingerprint, `importer: null` |

Pins use Tessera's `NounRef` fields exactly: `store`, `key`, `version` and
`value_sha256`, the SHA-256 of the value's canonical JSON. A template's slots are null
until a requester fills them with exact pins (`scripts/build_packs.py --instantiate`
checks the filled inputs against the template's input schema, takes `--queue` for an
assigned queue, prints the TaskSpec and never enqueues). Producer surface
`surface:tessera` is a placeholder: Tessera records the importing key's own surface, and
`surface_only` then shares the pack with keys on that surface only. Every output schema
has `proposed_verbs` and `proposed_nouns`, so a worker can return follow-up work it
never enqueues itself. Each noun value and verb brief carries
Tessera's required category dimensions at their lowest value, a `dimension_basis` that
says nothing was measured, and typed `relations` that its category allows.

The proposed override policy allows no automatic merge. A future resolver would
need explicit override slots, compatibility checks, immutable definitions and a
resolved manifest that workers can consume without manual merges. This repository
does not implement that resolver. Preserve both source versions when definitions
conflict, and obtain a clear owning decision before using a combined contract.
