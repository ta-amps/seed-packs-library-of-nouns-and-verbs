# Seed pack library

A seed pack is a bundle of **nouns** (reusable knowledge, templates, tools and examples)
and **verbs** (work an authorized worker can claim). That is all a pack contains. It
adds no new kind of entity, runtime, agent authority or scheduler. Reading, exporting
or importing a pack runs nothing, activates nothing, admits or publishes nothing,
copies no credential and grants no permission. Tessera stays the authority for
identity, storage, leases and receipts.

**Status, October 29, 2026:** every pack here is a proposal and a validated example.
None is installed, imported, admitted or activated, and no worker has run these verbs.

## The packs

| Pack | What it lets workers do | Nouns | Verbs |
| --- | --- | --- | --- |
| [Repository review](repo-review/README.md) | Review a repository with 50 evidence-requiring questions in five families, privately | 66 | 6 |
| [Video showcase](video-showcase/README.md) | Make a truthful demo video, from script to QA, with evidence for every number | 18 | 9 |
| [Tool discovery](tool-discovery/README.md) | Find, trial and decide on new tools for your own hardware | 23 | 5 |
| [Evaluation design](evaluation-design/README.md) | Compare arms fairly: frozen sets, pass marks first, exact-match scoring | 10 | 7 |
| [Checks of checks](checks-of-checks/README.md) | Prove a test or rubric works before trusting it | 8 | 4 |
| [Decomposition patterns](decomposition-patterns/README.md) | Split work using shapes that worked, and learn which ones do | 24 | 4 |
| [Taste palettes](taste-palettes/README.md) | Show options side by side and record a person's choice as a preference | 8 | 5 |
| [Harness onboarding](harness-onboarding-e2e/README.md) | Connect a harness and prove the claim-to-submit lifecycle | 9 | 5 |

## What is in each pack folder

| File | What it is |
| --- | --- |
| `README.md` | A short, plain explanation, starting with what the pack lets workers do |
| `source.json` | The authored content. Edit this file |
| `nouns.json` | Generated. One Tessera `RecordWrite` body per line: create-only, private, quarantined |
| `verbs.json` | Generated. One Tessera `TaskSpec` template per line, with unfilled input slots |
| `manifest.json` | Generated. File digests, each noun's value SHA-256 and each verb's identity |

## How the pieces fit

- A **pin** is a Tessera `NounRef`: store, key, version and `value_sha256`, the SHA-256
  of the value's canonical JSON. Version 1 pins assume a create-only write succeeded;
  read the noun back and compare the digest before relying on it.
- A **verb template** lists pinned pack nouns, typed slots you fill with your own pins,
  typed input and output schemas, acceptance checks and the outcomes it may end with.
  Every template can end with `no_change`, `unknown` or `blocked`, each with a required
  explanation. `scripts/build_packs.py --instantiate` fills a template and prints it;
  it never enqueues.
- Each template carries an optional **execution report** in Tessera's version-1 format.
  Its contract copies the typed schemas, so runs of the same template share one shape
  fingerprint and can be compared later. What went right, what went wrong, next steps
  and ideas go in the task output's `run_notes`, because the version-1 report has no
  fields for them.
- Outputs are private. A private noun is readable only by the key that wrote it, so
  workers also return produced values in the task output with their pins.

## Choices worth knowing

- **Only registered categories.** Every noun and verb uses one of Tessera's 20 noun
  and 18 verb categories. Where the fit is not obvious the value says why in
  `category_reason`. Tessera has no category for profiles or preferences, so those use
  `noun.seed_hypothesis`, the closest fit: they are assumptions later evidence can
  confirm or contradict.
- **No invented scores.** Tessera requires four quality dimensions on every category.
  Each is set to its lowest value with tier `unverified` and a `dimension_basis` saying
  nothing was measured. Success records keep `trials` and `successes` null, so Tessera's
  rankings list them as unranked instead of scoring them from a prior.
- **Typed relations only.** Links between nouns use Tessera's relation types and the
  ones each category allows.

## How the packs are checked

| Check | What it does | Where it runs |
| --- | --- | --- |
| `scripts/build_packs.py --check` | Rebuilds every pack and fails if any committed byte differs | `make check`, CI |
| `scripts/validate_packs.py` | Shapes, categories, relations, pins, outcomes, authority limits, template examples, README rules and the three worked examples, against [a snapshot](tessera-contract.json) of Tessera's contract | `make check`, CI |
| `scripts/validate_against_tessera.py` | Every noun and verb through Tessera's own `RecordWrite`, `TaskSpec`, `canonical_category_tags`, `validate_category_payload`, `NounRef` and execution-report code, plus ten negative probes | Locally, with a Tessera checkout |

The last check writes [VALIDATION.json](VALIDATION.json) with the Tessera commit and the
digests it validated. `make check` fails if a pack changed after that validation, so
the receipt cannot silently go stale. None of these checks calls a service or a model,
writes a record or enqueues a task.

## Changing a pack

1. Edit `packs/<pack>/source.json` or its README.
2. Run `python3 scripts/build_packs.py` to regenerate the payloads.
3. Run `make check-tessera TESSERA_SRC=<path to a Tessera checkout>` with that
   checkout's Python environment.
4. Run `make check` before committing.
