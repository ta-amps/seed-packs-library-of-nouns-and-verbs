# Seed operations and the first daily research loop

Checked October 29, 2026. Three different things exist:

| Layer | Current capability | Limit |
| --- | --- | --- |
| Teleion Fabric seed expansion | Local seed nouns, expansion, candidate enrichment, distinct review and canonical output in an executable made-up demo | The demo does not establish unattended research quality or every hosted publication path |
| Teleion Fabric research seed authoring | Four bounded task stages using pinned nouns and existing task APIs, with explicit enqueue and local task-loop tests | The tool does not research, collect mail, execute generated code or install recurring schedules |
| This contribution repository | Ten reference meta-pack blueprints and capability research guidance | These are not automatically installed or activated packs |

See [Teleion Fabric research seeds](https://github.com/ta-amps/teleion-fabric-infrastructure-work-and-storage-engine/blob/main/docs/research-seeds.md)
and [existing expansion](https://github.com/ta-amps/teleion-fabric-infrastructure-work-and-storage-engine/blob/main/docs/expansion.md).
Use the owning implementation's exact schema and current tests when preparing work.

## A meta-seed that finds useful sources

The initial verb can read a pinned project profile and find a bounded list of
relevant publication sites, official release feeds, paper indexes or newsletters.
Its output is source nouns with source and proposed future seed nouns. This
is a useful meta-seed even though it does not install anything itself.

| Verb outcome | Nouns it produces | Follow-up |
| --- | --- | --- |
| Discover relevant sources | Publisher, endpoint, access method, topics, update cadence, restrictions and evidence | Test one shortlisted source |
| Prepare a collector | Versioned tool/code candidate, input/output contract, license/source evidence and tests | Qualify the collector under the owning policy |
| Propose daily work | Pinned source, collector and profile; UTC cadence; start/stop; queue; retry and resource limits | Activate through an authorized deterministic adapter |
| Scan once | Deduplicated items, source, content hashes, dates and cursor/replay evidence | Enqueue justified analysis within the remaining allowance |
| Assess project fit | Attributed claims, comparable observations and a concise decision | Trial, watch, reject or separately authorized adoption |

Use existing deterministic adapters before asking a worker to write a new one.
Most RSS/Atom sources should share a collector. Site-specific tools are justified
by an actual incompatible interface, not by every new feed URL. A tool is stored
as a noun with bytes, version, contract and evidence; workers invoke it within a
verb. A source label or successful compile alone cannot admit its code.

arXiv provides RSS and Atom feeds by category, including combined categories, so
it is a practical source family for the first collector trial. Source relevance
and source-specific limits still need checking. [arXiv RSS documentation](https://info.arxiv.org/help/rss.html).

## Recurring work

A schedule is versioned data. A deterministic tick reads an active authorized
schedule and enqueues a due scan verb using a stable schedule/version/window
identity. The worker runs the collector and stores results. The tick needs no LLM.

Teleion Fabric's one-time `not_before` is not recurring cron. Its fragility planner and
the existing Frontier discovery cron do not install arbitrary research schedules.
The general adapter remains to be built and tested. It needs duplicate-tick,
missed-window, outstanding-work, pause, expiry, revocation and crash-recovery
checks. A new version must not accidentally overlap an old active schedule.

Bound the whole chain: sources, fetches, items, child tasks, outstanding scans,
runtime, model use and delivery frequency. Do not let a generated seed spend a
fresh budget or recursively activate children. Deeper analysis is worthwhile only
when it can change a decision for the pinned profile.

## Newsletter intake

A dedicated receiving address keeps the intake separate from personal mail.
Store raw mail in a private scoped artifact store and derive sanitized item nouns.
Deduplicate by provider identity plus content evidence, preserve received and
published dates, handle retries and size limits, and avoid automatically fetching
tracking images or running attachments. Newsletter text remains untrusted input.

Two current setup paths are suitable for a pilot:

- An API inbox provider can provision a receiving inbox without managing MX
  records. AgentMail documents a receive-only signup path without an attached
  human email; attaching/verifying an owner changes available permissions. Its
  standard Free offer advertises three inboxes, and custom domains require a paid
  plan. Confirm the live plan's receive/storage limits when provisioning.
  [AgentMail quickstart](https://www.agentmail.to/docs/quickstart),
  [pricing](https://www.agentmail.to/pricing).
- A controlled domain on Cloudflare can route inbound mail to an `email()` Worker
  for parsing and storage. Email Routing supports Free and Paid plans; Worker
  execution and storage have their own usage costs. This is an intake handler,
  so an inbox browsing/replay interface must be provided separately.
  [Cloudflare email handler](https://developers.cloudflare.com/email-service/api/route-emails/email-handler/),
  [pricing](https://developers.cloudflare.com/email-service/platform/pricing/).

The account or address setup is a small part of the work. A reasonable engineering
estimate is 15-60 minutes for an available account/address, half a day to one day
for tested ingestion and noun creation, and another one to two days for recurring
work, recovery and a useful decision report. These are estimates, conditional on
account access, DNS, provider behavior and worker availability, not measured build
times or delivery guarantees.

No mailbox was provisioned, newsletter subscribed to, message sent or schedule
activated by this guide. The first operational pilot should use one profile, one
collector family and a small admitted source set, then add newsletter intake.
