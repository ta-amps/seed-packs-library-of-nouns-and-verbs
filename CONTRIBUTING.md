# Contributing instructions and examples

Submit a focused change that helps a human or external worker produce one useful,
verifiable contribution. Start with the [worker lifecycle](docs/lifecycle.md) and
the [format boundaries](docs/formats.md). Keep examples synthetic and small.

An issue or pull request should explain:

- The problem and intended beneficiary or consumer.
- Which current noun/task/API contract the example uses.
- Required input versions, capabilities, permissions and output checks.
- Which checks were actually run, their results, and remaining unknowns.
- Source and license provenance; any review or publication authority still needed.

Do not paste bearer tokens, provider keys, personal information, private prompts,
raw harness transcripts or unrelated project names. A log is untrusted data and
can contain sensitive material even when a task itself is public. Include a
bounded, sanitized problem summary and exact permitted artifact references.

## Authoring rules

Use one primary category and any number of compatible descriptive facets. Keep
the category field and category tag consistent. Category membership, a related
concept or a suggested tool does not inherit permissions or executable behavior.

Distinguish required steps, preferred methods, suggestions and requested discovery.
Optional guidance must not silently become a mandatory tool or an exclusive search
space. Required capabilities do not override the harness's sandbox, provider,
network, spending or publication policies.

Use existing CAS, task and execution APIs. The examples do not create a new queue,
registry, scheduler, compiler, reasoning service or pack importer. Validation code
may inspect repository files offline; it must not issue API requests or run user
content. No new server-paid model layer is introduced by a contribution guide.

## Changing a seed pack

Edit `packs/<pack>/source.json` or the pack README, never the generated `nouns.json`,
`verbs.json` or `manifest.json`. Run `python3 scripts/build_packs.py`, then
`make check-tessera TESSERA_SRC=<path>` with a Tessera checkout's own Python
environment, then `make check`. Use only registered categories and the relations each
category allows; say why in `category_reason` when the fit is not obvious. Name and
describe a pack in plain English as "a collection of nouns and verbs for ...", and keep
surface or product names in the descriptor's `provenance_notes`. Keep dimensions at the
unmeasured floor, keep every verb's `no_change`, `unknown` and `blocked` outcomes, give
each verb a network mode, and never add a step that contacts people, publishes, enqueues
children or spends beyond the worker's own allowance; the validator flags such steps.

## Revisions, extensions and forks

Pin dependencies to immutable record versions, file digests or source revisions.
A display version such as `0.1.0` is not a substitute for a content identity. When
an input changes, create a new candidate version using CAS and rerun affected
checks. Retain the prior evidence rather than overwriting its interpretation.

For a domain extension, add descriptive facets and namespaced extension metadata
inside the value or brief. Do not add arbitrary top-level API fields. A synthetic
library-hours example could share a date/interval schema with an event schedule
while retaining different acceptance criteria and provenance. This is authoring
guidance, not an implemented industry adapter.

A fork records its original pinned source, license, changed assumptions and new
owner/namespace. It does not inherit verification or publication rights. If two
definitions conflict, stop and identify the field and both versions. A proposed
override needs an explicitly allowed slot and a fresh resolved contract. Do not
ask workers to merge competing arrays by last-write-wins. General automatic
profile composition is not implemented by these examples.

## Verification and review

Run `make check` before committing. Add a negative example check when a new shape
introduces a meaningful boundary. Do not change a failing acceptance criterion
just to make an artifact pass. The validator intentionally checks a narrow example
profile; it is not a complete SDK or server-side authorization test.

Workers self-check first. Additional judgment uses a capable authorized review
worker only when required. Preserve distinct drafter/reviewer rules where the
owning workflow requires independence. This can be an external agent or a human;
it does not imply a mandatory paid server model. A missing reviewer leaves work
pending, not automatically approved.

Keep unknown measurements as `null` with a reason. Record separately whether an
observation came from a synthetic fixture, an actual harness, a provider counter
or independent verification. A receipt proves accepted task output identity;
it does not prove that the work is correct or publicly admitted.

Open a normal pull request for later changes. Do not force-push main. Keep the
ta-amps repository identity and omit coauthor or generated-by trailers. Public
publishing and deployments remain the owner's coordinated release actions.
