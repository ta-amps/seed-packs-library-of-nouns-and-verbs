# Seed-pack library – every pack of nouns and verbs

Instructions and synthetic examples for contributing useful noun records and
verb seeds to the [Tessera work fabric](https://github.com/ta-amps/tessera-infrastructure-work-and-storage-engine).
This repository is a guide and a library of seed packs, not an importer or service.
A pack may include tested code as nouns, in `packs/<pack>/code/`. The library never runs pack code except in its own CI tests; workers run it under their own permissions. Reading, exporting or importing a pack still runs nothing, activates nothing, publishes nothing and grants nothing.

A pack groups related inputs, reusable procedures, tools, resources and bounded
work contracts. Nouns hold versioned data and evidence. Verbs request an outcome
from an authorized worker. Both use Tessera's existing identity, namespaces,
storage, queues, leases and receipts.

## Seed pack library

The [packs/](packs/README.md) folder holds twenty proposed seed packs. Each is a
collection of nouns (knowledge, templates, tool cards and examples) and verbs (work an
authorized worker can claim), named in plain English and kept separate from any surface.
They are proposals and validated examples, **not installed, imported, admitted or
activated**, and no worker has run them yet.

| Pack | A collection of nouns and verbs for |
| --- | --- |
| [Repository review](packs/repo-review/README.md) | Reviewing a repository with 50 evidence-requiring questions |
| [Video and motion with code](packs/video-motion/README.md) | Video and motion made with code: seeking frames, fitting motion, compiling, rendering and checking |
| [Video showcase](packs/video-showcase/README.md) | Making a truthful demo video, from script to review and release |
| [Visual and 3D rendering](packs/visual-rendering/README.md) | Rendering images, motion graphics and 3D scenes and checking them |
| [Tool discovery](packs/tool-discovery/README.md) | Discovering, trialing, deciding on and refreshing new tools |
| [Prior art and alternatives](packs/prior-art-and-alternatives/README.md) | Finding what already exists and what the alternatives are, before anything new is built |
| [Benchmark scores](packs/benchmark-scores/README.md) | Keeping benchmark scores current and comparable |
| [Freshness checks](packs/freshness-checks/README.md) | Finding stale, deprecated or end-of-life knowledge |
| [Evaluation design](packs/evaluation-design/README.md) | Fair, pre-registered evaluations with exact-match scoring |
| [Checks of checks](packs/checks-of-checks/README.md) | Proving a test or rubric works before trusting it |
| [Decomposition patterns](packs/decomposition-patterns/README.md) | Breaking work into verbs with reusable patterns |
| [Code composition](packs/code-composition/README.md) | Composing verified code without rewriting it |
| [Taste palettes](packs/taste-palettes/README.md) | Comparing options side by side and keeping a person's choice |
| [Public-good kits](packs/public-good-kits/README.md) | Building agent kits that nonprofits can use |
| [Exploitation evidence](packs/exploitation-evidence/README.md) | Spotting exploitation and scams in synthetic cases, never accusing anyone |
| [Harness onboarding](packs/harness-onboarding-e2e/README.md) | Connecting an agent harness and proving its lifecycle |
| [Security review](packs/security-review/README.md) | Authorized, local-only security review of code |
| [Cost optimization](packs/cost-optimization/README.md) | Finding and measuring cost savings |
| [Docs improvement](packs/docs-improvement/README.md) | Making documentation clearer for a named reader |
| [Findings to fixes](packs/findings-to-fixes/README.md) | Turning every noticed error, issue, design flaw or annoyance into recorded, fixed and verified work |

Every noun is a Tessera `RecordWrite` body and every verb a `TaskSpec` template. Workers
create nouns and propose follow-up verbs; they never enqueue their proposals. All 411
nouns and 128 verb templates were checked offline with Tessera's own models at a pinned
commit, and a two-key probe on a throwaway local Store showed a team surface can read,
claim and update them while other keys see nothing; the [receipt](packs/VALIDATION.json)
records exactly what was checked. The [pack inventory](docs/pack-inventory.md) maps the
packs onto making a video, building nonprofit kits and keeping knowledge fresh, and lists
what is still missing. Reading or importing a pack runs and grants nothing.

## Start here

To add a pack, follow [Submit a seed pack](docs/submit-a-pack.md): generate it, validate it
locally with `make check` and `make check-tessera`, and open a pull request.

Start with [CONTRIBUTING.md](CONTRIBUTING.md), then follow the
[worker lifecycle](docs/lifecycle.md). [Formats](docs/formats.md) separates actual
HTTP/MCP payloads from the proposed manifest. [Status](docs/status.md) states what
these examples prove and what still needs an owning implementation.

The [self-improvement guide](docs/self-improvement.md) describes a bounded,
worker-led improvement loop and a reference-only meta-pack. It is a contribution
template, not an enabled autonomous process.
The [meta-pack blueprints](docs/meta-pack-blueprints.md) outline ten possible
improvement workflows, with a small first pilot and explicit rejection conditions.
The [context, combined outcomes and result guide](docs/context-composition-and-results.md)
explains bounded worker inputs, integration checks and concise receipt-backed updates.
The [capability research workflow](docs/capability-research.md) applies those ideas
to overloaded feeds and newsletters: consolidate claims, assess fit against a
versioned project profile, and run only justified comparisons before recommending
an adoption decision. It is a proposed seed-pack use case, not an active collector.
The [seed operations guide](docs/seed-operations.md) separates the existing seed
expander, the bounded research task authoring tool, reference meta-packs and the
remaining mailbox/scheduling work.

The [Opportunity Lab guide](docs/opportunity-lab.md) links the runnable Tessera
showcase: shared briefs, independent solutions, candidate nouns and later
comparison or remix verbs.

## Connect and inspect

Start at the [ecosystem connection page](https://home.ta-amps.workers.dev/connect)
or [Tessera connection page](https://tessera.ta-amps.workers.dev/connect).
An HTTP/MCP-capable harness can use:

| Purpose | Endpoint |
| --- | --- |
| Public MCP discovery | `https://tessera.ta-amps.workers.dev/mcp` |
| Access modes and limits | `https://tessera.ta-amps.workers.dev/connect.json` |
| API descriptions | `https://tessera.ta-amps.workers.dev/v1/openapi.json` |
| Public agent card | `https://tessera.ta-amps.workers.dev/.well-known/agent-card.json` |

Send the [initialize request](examples/mcp/initialize.json), then
[tools/list](examples/mcp/tools-list.json). Compare the returned descriptors with
the operations you need. A protocol version string alone does not establish every
optional MCP feature. An assistant without external HTTP/MCP tool access needs a
compatible connector; a longer prompt cannot grant that capability.

```bash
export TESSERA_URL=https://tessera.ta-amps.workers.dev
curl --fail-with-body "$TESSERA_URL/connect.json"
curl --fail-with-body -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data-binary @examples/mcp/tools-list.json "$TESSERA_URL/mcp"
```

Anonymous practice starts with `POST /v1/session/anonymous` and the
[session body](examples/http/session.json). The returned session token belongs in
`Authorization: Bearer <session_token>`. Keep it in your harness's credential
memory or approved secret store, never in a pack or conversation log. No existing
key is needed. Discover the current quotas and expiry from the response.

Anonymous work is isolated synthetic practice. It cannot publish a reusable pack,
claim production verbs or access another session's history. Durable contribution
work needs an operator-issued key scoped to the assigned namespace, queue and
effects. Key issuance remains operator-assisted. A personal label is not an
account role or authorization grant.

## First useful contribution

1. Agree on one outcome and existing queue with its owner. Find permitted prior
   nouns or execution observations before creating duplicate work.
2. Claim a bounded verb, inspect required capabilities and pin the input versions.
   Use a configured shim if helpful; ordinary HTTP/MCP also works without one.
3. Produce a private candidate, run the required checks and record failures as
   well as successes. Use the [synthetic noun body](examples/http/noun-put.json)
   and [verb seed body](examples/http/verb-enqueue.json) as shape examples.
4. Submit exact artifact references with a stable idempotency key. Optional
   execution telemetry is worker reported, not independent proof.
5. Request a review verb when the owning policy requires it. Admission and public
   publication remain separate authorized actions.

The [candidate manifest](examples/pack-manifest.proposed.json) is a proposal for
reviewing related files. **There is no manifest upload endpoint or generic pack
importer here.** A category name does not register executable code or activate a
shim. Do not upload an entire directory and assume that it becomes a workflow.

## Check a contribution locally

Python 3.10+ and Git are enough; no package install, network or service is needed.
Pack code has its own checks in `packs/<pack>/code/`, which a separate CI job runs.

```bash
make check
```

The checks parse JSON, enforce the documented example subset, validate local
manifest hashes and links, rebuild every seed pack byte for byte, validate the packs
against a snapshot of Tessera's contract, recompute the packs' worked examples, and
scan for secrets, private names and forbidden typography. They include negative
fixtures. They do not execute artifacts, certify a live deployment, prove licensing or
validate arbitrary JSON Schema.

With a local Tessera checkout, `make check-tessera TESSERA_SRC=<path>` also runs every
pack noun and verb through Tessera's own models; see the [library guide](packs/README.md).

The examples and packs are MIT-licensed authoring material. They are not production
packs or a second artifact library: accepted artifacts and evidence belong in Tessera.
Installing or activating packs waits for the owning infrastructure and contributor flow.
