# Wiring and conformance checks

## What this pack lets workers do

A collection of nouns and verbs for proving that what a code project has written and tested is
actually wired in. Well-tested capabilities often sit where nothing reaches them: a module no live
path imports, a setting saved but never read back, a health probe that answers yes whatever happens,
a check that silently stopped firing, or a documented behavior whose only test mocks the very code
it describes. Workers name the entry points at one commit, map every module from them and confirm
the leads with a runtime trace, round-trip every config field, stop each dependency to see whether
its probe fails, plant one canary per rule that its check must catch, and map each documented
behavior to a test of its real path. Every gap becomes a finding in the
[findings to fixes](../findings-to-fixes/README.md) shape, and a conformance report ties each rule's
result, evidence and canary to those findings.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | On a live path or a finding; a behavior is covered by its real path, not a mock; a canary for every rule |
| Live path rules | Entry points, what counts as an import, five module statuses, runtime traces for leads |
| Config round-trip rules | Set, save, load, compare; stable is not survived; unknown keys; synthetic values only |
| Health probe rules | Stop the dependency and the probe fails; hollow kinds; liveness apart from readiness |
| Behavior coverage rules | Promises with their locators, real paths, and real_path, mock_only or untested |
| Templates | Wiring scope, module map, round-trip report, probe report, behavior map, canary set and conformance report |
| Wiring checks | 12 deterministic checks with 2 synthetic good and 12 synthetic bad conformance reports, rechecked by `make check` |
| Tool card and code | Tested standard-library code in [code/](code/README.md): unused modules, mock-only tests, hollow probes |
| Sources | 7 dated public sources |
| Worked examples | A synthetic app's module map, behavior map, probe report, round trip, conformance report and one finding |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `scope-wiring` | agent | The commit, packages, entry points, config schemas, probes, docs and rules |
| `find-unused-modules` | agent, no model | The finder's map, then a runtime trace that settles its leads |
| `check-config-round-trip` | agent | One round-trip test per field, and what unknown keys do |
| `check-health-probes` | agent | Hollow probes found statically; the rest run with dependencies stopped |
| `map-behaviors-to-tests` | agent | Each promise, its real path and what its tests patch |
| `plant-canaries` | agent | One known-bad canary per rule, caught by its check |
| `record-wiring-findings` | agent | One finding per gap, in the findings to fixes shape |
| `compile-conformance-report` | agent, no model | Every rule, canary and finding in one checked report |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Canaries reuse the [checks of checks](../checks-of-checks/README.md) method, and
findings go on through triage, a fix, verification and a regression guard.

## Worked examples

All synthetic: a food pantry's appointment app in `code/tests/fixtures/pantry`. The tools' real
output on it finds two dark modules, one only tests reach and one used only for type checking, and
two that a computed export name loads, which the runtime trace confirms. A setting written as 48
comes back as its default 24, yet load, save and load is stable. Three probes are hollow on their
face, and `readyz` calls the store but passes with it stopped. Two behaviors are covered only by
tests that patch their own path. Twelve gaps become twelve findings. The code's tests recompute the
module map, behavior map and probe scan from this pack's nouns.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface,
then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Run the code with `make check` in `code/`; it needs Python 3.10
or later and nothing else.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The code reads Python only. A module a deployment loads by name from settings, or a plugin found
  at run time, is invisible to it until the scope names it as an entry point.
- Static results are leads. The runtime trace, the stopped dependency and the reading of each test
  decide; a test that patches nothing may still not reach its entry.
- Canaries prove a check fires on one known-bad example, not that it catches every case.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
