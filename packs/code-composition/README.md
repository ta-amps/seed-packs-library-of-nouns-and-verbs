# Code composition

## What this pack lets workers do

A collection of nouns and verbs for composing verified code without rewriting it. Instead
of writing new code for routine data steps, a worker writes a small declarative recipe that
wires prewritten, tested code nodes together. A compiler checks the recipe before anything
runs. The runtime then executes it with no model calls, reuses cached results of unchanged
steps and proves that the emitted standalone Python gives byte-identical outputs.

The tested code is part of the pack, as nouns, in [code/](code/README.md). The tool card pins
that folder by the digest the manifest also lists; the build recomputes it from the files, and
the code's own tests check the module, node and recipe pins in CI. The library never runs the
code except in CI tests; workers run it under their own permissions. Importing runs nothing.

## Nouns

| Noun | What it holds |
| --- | --- |
| Tool card | The code folder's path and digest, license, requirements, interfaces, checks and cautions |
| Compiler and runtime | Entry points, compile checks, runtime behavior and the SHA-256 of the six modules every compile and run uses |
| Node catalog | Signatures of the 18 nodes, port and parameter types, the edge rule and the code digest rule |
| Prewritten nodes (18) | One per node: typed ports and parameters, source digest, license, built-in tests and the recipes that use it |
| Recipes (3) | Telemetry anomaly triage, incident log digest and A/B candidate selection, with plan, output and receipt digests |
| Method | How to compose without rewriting code, and how to repair each compiler refusal |
| Templates (8) | Recipe candidate, compile report, run inputs, run receipt, verification report, comparison, node proposal and review notes |
| Worked example | MADE-UP: a variant that changes one step reuses the 7 unchanged upstream steps from the cache |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| verify-tools | agent | Checks the code folder of a fresh library checkout: folder and module digests, node tests and the code's own checks |
| compose-recipe | agent | Turns a goal into a recipe the pinned compiler accepts, repairing it from the diagnostics |
| compile-recipe | agent | Compiles a recipe twice and records its plan digest and emitted module; deterministic |
| run-recipe | agent | Runs it with pinned inputs and records the receipt; no model calls |
| compare-runs | agent | Runs a baseline and a variant in one cache and ties output differences to the changed steps |
| propose-node | agent | Writes a tested node candidate when no catalog node fits |
| review-node | a different agent or a person | Rechecks a proposal and decides accept, revise or reject |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose follow-up
verbs. compare-runs follows the baseline-then-variant pattern from
[decomposition patterns](../decomposition-patterns/README.md), and propose-node uses the
[checks of checks](../checks-of-checks/README.md) method for its tests.

## How to use it

Run verify-tools first in each sandbox; every other verb takes its report as a pin. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to
your team's surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## How to check it

- In this library, `make check` rebuilds the pack byte for byte and validates it, and
  `make check-tessera TESSERA_SRC=<Tessera checkout>` runs it through Tessera's own models.
- In `code/`, run `make setup`, `make check` and `make demo`, and with a prepared Tessera
  checkout `make tessera-integration TESSERA_DIR=<path>`. A path-filtered CI job runs all of
  them, the Tessera integration at the tool card's Tessera commit included, whenever this
  pack changes.

## Real and planned

- Real: on October 29, 2026 the pack author ran the code in this folder on Python 3.12.13 and
  3.13.13. All 18 node tests passed, the three recipes compiled and ran with identical digests
  on both, pytest reported 41 passed and 2 skipped on both, and the Tessera integration passed
  2 of 2. Node, recipe, plan, input, output and receipt digests are unchanged from version
  0.1.0; module and emitted-module digests changed with the code's plain name. This is the
  author's measurement, not independent verification.
- Not done: no worker has claimed these verbs, and nothing is installed, imported, admitted
  or activated. The pack's `moved_from` field records the repository and commit its code came from.

## Limits

- The digests hold for the pinned code only. A code change gives a new folder digest and needs
  a new pack version, as 0.2.0 did when the code moved here.
- Node code and emitted Python run in the worker's own process; this is not a sandbox.
- The holdout split keeps its original default salt so earlier partitions reproduce; pass
  `salt` explicitly, as the bundled A/B recipe does.
- The catalog covers tabular, text and evaluation steps. Anything else needs propose-node and
  an independent review.
