# Seed pack library

A seed pack is a collection of **nouns** (reusable knowledge, templates, tool cards and
examples) and **verbs** (work an authorized worker can claim). That is all a pack
contains. Packs are separate from surfaces: a website, app or chat client can show what a
pack produces, but no pack is part of a surface, and packs carry plain-English names, not
product names. A pack adds no new kind of entity, runtime, agent authority or scheduler.
Reading, exporting or importing a pack runs nothing, activates nothing, admits or
publishes nothing, copies no credential and grants no permission. Tessera stays the
authority for identity, storage, leases and receipts.

**Status, October 29, 2026:** every pack here is a proposal and a validated example.
None is installed, imported, admitted or activated, and no worker has run these verbs.

## The packs

| Pack | A collection of nouns and verbs for | Nouns | Verbs |
| --- | --- | --- | --- |
| [Repository review](repo-review/README.md) | Reviewing a code repository with 50 evidence-requiring questions | 66 | 6 |
| [Video showcase](video-showcase/README.md) | Making a truthful demo video, from script to QA, review and release | 22 | 11 |
| [Visual and 3D rendering](visual-rendering/README.md) | Rendering images, motion graphics and 3D scenes and checking them | 11 | 5 |
| [Tool discovery](tool-discovery/README.md) | Discovering, trialing, deciding on and refreshing new tools | 23 | 7 |
| [Benchmark scores](benchmark-scores/README.md) | Keeping benchmark scores current and comparable | 10 | 5 |
| [Freshness checks](freshness-checks/README.md) | Finding stale, deprecated or end-of-life knowledge | 7 | 4 |
| [Evaluation design](evaluation-design/README.md) | Fair, pre-registered evaluations with exact-match scoring | 10 | 7 |
| [Checks of checks](checks-of-checks/README.md) | Proving a test or rubric works before trusting it | 8 | 4 |
| [Decomposition patterns](decomposition-patterns/README.md) | Breaking work into verbs with reusable patterns | 24 | 4 |
| [Code composition](code-composition/README.md) | Composing verified code without rewriting it | 35 | 7 |
| [Taste palettes](taste-palettes/README.md) | Comparing options side by side and keeping a person's choice | 8 | 5 |
| [Public-good kits](public-good-kits/README.md) | Building agent kits that nonprofits can use | 15 | 8 |
| [Exploitation evidence](exploitation-evidence/README.md) | Spotting exploitation and scams in synthetic cases, never accusing anyone | 69 | 11 |
| [Harness onboarding](harness-onboarding-e2e/README.md) | Connecting an agent harness and proving its lifecycle | 9 | 5 |
| [Security review](security-review/README.md) | Authorized, local-only security review of code | 11 | 6 |
| [Cost optimization](cost-optimization/README.md) | Finding and measuring cost savings | 8 | 6 |
| [Docs improvement](docs-improvement/README.md) | Making documentation clearer for a named reader | 8 | 5 |

Together: 344 nouns and 106 verb templates across seventeen packs. The
[pack inventory](../docs/pack-inventory.md) maps them onto three goals (making a video,
building nonprofit kits and keeping knowledge fresh) and lists what is still missing.

## What is in each pack folder

| File | What it is |
| --- | --- |
| `README.md` | A short, plain explanation, starting with what the pack lets workers do |
| `source.json` | The authored content. Edit this file |
| `nouns.json` | Generated. One Tessera `RecordWrite` body per line: create-only, `surface_only`, quarantined |
| `verbs.json` | Generated. One Tessera `TaskSpec` template per line, with unfilled input slots |
| `manifest.json` | Generated. File digests, each noun's value SHA-256 and each verb's identity |

## Workers create nouns and verbs

Every verb template says what its worker creates. The worker **writes nouns**: the ones
listed in the template's output contract, returned with their pins. The worker also
**proposes verbs**: follow-up work the results justify, such as a breakdown into smaller
verbs, a trial of a changed tool or a research follow-up, returned in the output's
`proposed_verbs` with the pins they need, and nouns worth creating later in
`proposed_nouns`. Workers never enqueue their proposals; an authorized requester enqueues
the ones worth doing. Examples: repository review's `select-questions` proposes one
`investigate-family` verb per family, `flag-stale` proposes refreshes and comparisons,
and decomposition's breakdowns become child task previews.

## How the pieces fit

- A **pin** is a Tessera `NounRef`: store, key, version and `value_sha256`, the SHA-256
  of the value's canonical JSON. Keys carry the pack version, so a new version never
  collides with an old one. Version 1 pins assume a create-only write succeeded; read the
  noun back and compare the digest before relying on it.
- A **verb template** lists pinned pack nouns, typed slots you fill with your own pins,
  typed input and output schemas, acceptance checks, a network mode and the outcomes it
  may end with. Every template can end with `no_change`, `unknown` or `blocked`, each
  with a required explanation. `scripts/build_packs.py --instantiate` fills a template,
  checks the result against its input schema and prints it, optionally for your queue
  with `--queue`; it never enqueues.
- Each template carries an optional **execution report** in Tessera's version-1 format.
  Its contract copies the typed schemas, so runs of the same template share one shape
  fingerprint. What went right, what went wrong, next steps and ideas go in the task
  output's `run_notes`, because the version-1 report has no fields for them.
- **Scope.** Payloads are `surface_only`. Import them with a key scoped to your team's
  surface; Tessera records that surface as the producer. Workers, requesters and
  reviewers on the same surface can then read the nouns, claim the verbs and read each
  other's outputs, while keys on other surfaces, or with none, see nothing. Workers write
  their outputs the same way.

## Choices worth knowing

- **Only registered categories.** Every noun and verb uses one of Tessera's 20 noun
  and 18 verb categories, with `category_reason` where the fit is not obvious. Tessera
  has no category for profiles or preferences, so those use `noun.seed_hypothesis`: they
  are assumptions later evidence can confirm or contradict.
- **No invented scores.** Tessera requires four quality dimensions on every category.
  Each starts at its lowest value with tier `unverified` and a `dimension_basis` saying
  nothing was measured. Success records keep `trials` and `successes` null, so Tessera's
  rankings list them as unranked instead of scoring them from a prior.
- **Typed relations only**, of the kinds each category allows.
- **No branding.** Surface and product names appear only in a descriptor's
  `provenance_notes`, which say where an idea came from.

## How the packs are checked

| Check | What it does | Where it runs |
| --- | --- | --- |
| `scripts/build_packs.py --check` | Rebuilds every pack and fails if any committed byte differs | `make check`, CI |
| `scripts/validate_packs.py` | Shapes, categories, relations, pins, outcomes, scope, network modes, authority limits, instructions to contact or publish, branding, template and example conformance, README rules, the counts stated in these docs and the six worked examples, against [a snapshot](tessera-contract.json) of Tessera's contract | `make check`, CI |
| `scripts/validate_against_tessera.py` | Every noun and verb through Tessera's own `RecordWrite`, `TaskSpec`, tag projection, `validate_category_payload`, `NounRef` and execution-report code, ten negative probes, and a two-key lifecycle probe on a throwaway local Store | Locally, with a clean Tessera checkout |

The last check writes [VALIDATION.json](VALIDATION.json) with the Tessera commit, whether
its files were clean, and the digests it validated. `make check` fails if a pack changed
after that validation, so the receipt cannot silently go stale. None of these checks
calls a service or a model or writes to a real fabric.

## Changing a pack

1. Edit `packs/<pack>/source.json` or its README.
2. Run `python3 scripts/build_packs.py` to regenerate the payloads.
3. Run `make check-tessera TESSERA_SRC=<clean Tessera checkout> TESSERA_ARGS=--write`
   with that checkout's Python environment.
4. Run `make check` before committing.
