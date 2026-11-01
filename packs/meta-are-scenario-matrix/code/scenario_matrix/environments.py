"""1,000 indexed environments/situations (ENV-0001..ENV-1000) across 25 domains x 10 constraints x 4 regimes."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

# 25 public-good and technical domains (inspired by Meta ARE / Gaia2 dynamic environments).
DOMAINS_25: tuple[dict[str, Any], ...] = (
    {
        "slug": "rural-shelter-intake",
        "title": "Rural shelter offline handwritten intake transcription",
        "sector": "public_good",
        "input_artifact": "scanned handwritten intake statements with regional slang and acronyms",
        "deliverable": "verbatim typed transcript with uncertainty flags and monthly shelter count summary",
        "human_only_boundary": "Crisis safety follow-up, bed allocation and individual intake sign-off stay human-only.",
        "tessera_noun_category": "noun.reflex_procedure",
        "tessera_verb_category": "verb.ingest",
    },
    {
        "slug": "multilingual-disaster-escrow",
        "title": "Multilingual disaster relief voucher and escrow verification",
        "sector": "public_good",
        "input_artifact": "four-language relief hub ledger and translated household notice flyers",
        "deliverable": "reconciled voucher line audit and number-preserving translation discrepancy table",
        "human_only_boundary": "Household eligibility rulings, escrow release and printed flyer approval stay human-only.",
        "tessera_noun_category": "noun.benchmark_suite",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "municipal-budget-audit",
        "title": "Municipal and state enacted budget appropriation line audit",
        "sector": "public_good",
        "input_artifact": "enacted state appropriation tables, supplemental schedules and committee footnotes",
        "deliverable": "statute-cited budget line comparison with exact page and line references",
        "human_only_boundary": "Advocacy testimony, policy recommendations and funder submissions stay human-only.",
        "tessera_noun_category": "noun.public_source",
        "tessera_verb_category": "verb.situate",
    },
    {
        "slug": "clinical-trial-table-extraction",
        "title": "Clinical trial adverse-event and subgroup table extraction",
        "sector": "technical_health",
        "input_artifact": "multi-page PDF registry tables, protocol amendments and CONSORT flow counts",
        "deliverable": "denominator-checked adverse-event schema records with row-sum reconciliation",
        "human_only_boundary": "Clinical interpretation, dosing guidance and patient medical decisions stay human-only.",
        "tessera_noun_category": "noun.eval_run",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "supply-chain-wage-theft-triage",
        "title": "Supply-chain timecard and piece-rate wage discrepancy triage",
        "sector": "public_good",
        "input_artifact": "synthetic or worker-consented shift logs, pay stubs and statutory minimum-wage tables",
        "deliverable": "arithmetic overtime and deduction discrepancy worksheet without legal accusations",
        "human_only_boundary": "Legal representation, agency complaints and settlement decisions stay human-only.",
        "tessera_noun_category": "noun.reflex_procedure",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "food-bank-cold-chain-routing",
        "title": "Food bank perishable cold-chain inventory and pickup scheduling",
        "sector": "public_good",
        "input_artifact": "pallet expiry manifests, cooler temperature logs and pantry van windows",
        "deliverable": "FEFO pickup schedule flagging Spoilage-risk lots and allergen separations",
        "human_only_boundary": "Food safety discard orders and emergency pantry dispatch overrides stay human-only.",
        "tessera_noun_category": "noun.scene_recipe",
        "tessera_verb_category": "verb.compile_dag",
    },
    {
        "slug": "eviction-defense-docket-watch",
        "title": "Housing court public docket and statutory notice-period verification",
        "sector": "public_good",
        "input_artifact": "public municipal landlord-tenant filing calendar and local notice ordinances",
        "deliverable": "statutory timeline checklist and anonymized filing-trend digest",
        "human_only_boundary": "Legal advice, tenant counseling and court filings stay strictly attorney-only.",
        "tessera_noun_category": "noun.public_source",
        "tessera_verb_category": "verb.probe_source",
    },
    {
        "slug": "accessibility-wcag-remediation",
        "title": "Public benefits portal WCAG 2.2 AA accessibility and screen-reader audit",
        "sector": "public_good",
        "input_artifact": "DOM landmark snapshots, sRGB palette pairs and keyboard tab-order traces",
        "deliverable": "criterion-cited WCAG 2.2 contrast and focus-trap remediation patches",
        "human_only_boundary": "Assistive-technology lived-experience sign-off and portal release stay human-only.",
        "tessera_noun_category": "noun.benchmark_suite",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "wildfire-smoke-school-advisory",
        "title": "Regional PM2.5 sensor fusion and school clean-air shelter readiness check",
        "sector": "public_good",
        "input_artifact": "EPA AirNow hourly feeds, HVAC MERV filter logs and district translation templates",
        "deliverable": "sensor drift check and multilingual parent advisory draft pinned to AQI thresholds",
        "human_only_boundary": "School closure orders, outdoor-activity cancellations and public alerts stay human-only.",
        "tessera_noun_category": "noun.feed_source",
        "tessera_verb_category": "verb.fetch_feed",
    },
    {
        "slug": "refugee-credential-equivalency",
        "title": "Foreign vocational syllabus and licensing hour-table mapping",
        "sector": "public_good",
        "input_artifact": "translated nursing or trade course syllabi and state licensing board hour rubrics",
        "deliverable": "credit-hour gap matrix mapping completed modules to state board requirements",
        "human_only_boundary": "Official credential evaluation letters and licensing determinations stay human-only.",
        "tessera_noun_category": "noun.skill_pack",
        "tessera_verb_category": "verb.situate",
    },
    {
        "slug": "community-water-lead-pipe-inventory",
        "title": "Municipal service-line material record digitization and EPA LCRR audit",
        "sector": "public_good",
        "input_artifact": "historical curb-stop install cards, plumbing permit scans and block parcel IDs",
        "deliverable": "material classification confidence table separating confirmed copper from unknown lead risk",
        "human_only_boundary": "Excavation priority orders, resident health notices and regulatory filings stay human-only.",
        "tessera_noun_category": "noun.public_source",
        "tessera_verb_category": "verb.ingest",
    },
    {
        "slug": "nonprofit-grant-renewal-evidence",
        "title": "Community nonprofit grant renewal outcome and receipt reconciliation",
        "sector": "public_good",
        "input_artifact": "quarterly service tallies, audited ledger totals and funder rubric questions",
        "deliverable": "number-traced impact narrative where every metric cites an internal ledger row",
        "human_only_boundary": "Executive director attestation, budget commitments and grant submission stay human-only.",
        "tessera_noun_category": "noun.scene_recipe",
        "tessera_verb_category": "verb.solve_draft",
    },
    {
        "slug": "elder-scam-synthetic-triage",
        "title": "Synthetic elder-fraud message pattern analysis for helpline training",
        "sector": "public_good",
        "input_artifact": "redacted synthetic phishing transcripts, gift-card coercion scripts and helpline rubrics",
        "deliverable": "red-flag indicator cards and calm de-escalation rehearsal prompts without accusing anyone",
        "human_only_boundary": "Live caller crisis counseling, bank freezes and protective referrals stay human-only.",
        "tessera_noun_category": "noun.skill_pack",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "rural-transit-paratransit-rostering",
        "title": "Wheelchair-accessible rural dial-a-ride and dialysis van scheduling",
        "sector": "public_good",
        "input_artifact": "clinic appointment windows, lift-equipped vehicle capacities and gravel-road travel times",
        "deliverable": "conflict-free paratransit route manifest respecting dwell times and oxygen-tank rules",
        "human_only_boundary": "Medical priority overrides, weather cancellations and driver dispatch stay human-only.",
        "tessera_noun_category": "noun.scene_recipe",
        "tessera_verb_category": "verb.compile_dag",
    },
    {
        "slug": "open-source-sbom-cve-audit",
        "title": "Civic software lockfile SBOM reachability and license conformance scan",
        "sector": "technical_engineering",
        "input_artifact": "pinned Python/Rust/JS lockfiles, AST call-graphs and advisory CVE bulletins",
        "deliverable": "call-path reachability triage separating live vulnerable imports from dead dev-only deps",
        "human_only_boundary": "Production dependency upgrades, risk waivers and disclosure advisories stay human-only.",
        "tessera_noun_category": "noun.code_node",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "multiframe-video-caption-qa",
        "title": "Educational public-health video multi-frame dwell and caption legibility audit",
        "sector": "technical_media",
        "input_artifact": "encoded 1080p MP4 frame timestamps, WebVTT caption cues and ITU-R BS.1770 loudness logs",
        "deliverable": "timestamped QA receipt catching flash cuts, text crossfades and speech-caption collisions",
        "human_only_boundary": "Editorial cut lock, cultural nuance sign-off and broadcast release stay human-only.",
        "tessera_noun_category": "noun.eval_run",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "post-cutoff-api-lora-distillation",
        "title": "Post-cutoff SDK specification compilation into holdout-disjoint LoRA pairs",
        "sector": "technical_ml",
        "input_artifact": "versioned API changelogs, deprecated method tombstones and pre-registered holdout prompts",
        "deliverable": "4-gram-disjoint SFT pairs plus paired bootstrap CI gate evaluation",
        "human_only_boundary": "Adapter admission, production model routing and spend approval stay human-only.",
        "tessera_noun_category": "noun.model_spec",
        "tessera_verb_category": "verb.distill_reflex",
    },
    {
        "slug": "hybrid-rag-injection-sanitization",
        "title": "Untrusted corpus retrieval sanitization and 0/1 token-knapsack context packing",
        "sector": "technical_ml",
        "input_artifact": "BM25 + dense candidate chunks containing adversarial prompt-injection decoys",
        "deliverable": "directive-redacted, MinHash-deduplicated context bundle within exact token ceiling",
        "human_only_boundary": "Corpus trust-root changes and security incident escalation stay human-only.",
        "tessera_noun_category": "noun.shim_provision",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "distributed-lease-fencing-audit",
        "title": "Work-queue lease expiry, fencing-token monotonicity and CAS replay verification",
        "sector": "technical_systems",
        "input_artifact": "synthetic multi-worker claim/expire/submit event traces and idempotency ledgers",
        "deliverable": "linearizability check verifying expired workers cannot overwrite newer fenced leases",
        "human_only_boundary": "Namespace ACL grants, operator key issuance and storage migrations stay human-only.",
        "tessera_noun_category": "noun.recovery_playbook",
        "tessera_verb_category": "verb.recover_fault",
    },
    {
        "slug": "agent-harness-pareto-benchmark",
        "title": "Cross-harness cost, latency and patch-pass Pareto frontier normalization",
        "sector": "technical_ml",
        "input_artifact": "pinned benchmark run logs across open and commercial agent harnesses",
        "deliverable": "HarnessTax overhead table and bootstrap-verified Pareto tier classification",
        "human_only_boundary": "Procurement choices and team default harness policies stay human-only.",
        "tessera_noun_category": "noun.benchmark_suite",
        "tessera_verb_category": "verb.benchmark_harness",
    },
    {
        "slug": "purged-regime-statistical-hygiene",
        "title": "Purged walk-forward regime validation and multiple-testing deflation check",
        "sector": "technical_quant",
        "input_artifact": "timestamped synthetic feature panels with embargo windows and trial-count ledgers",
        "deliverable": "non-advisory Rank IC, turnover drag and Deflated Sharpe Ratio audit report",
        "human_only_boundary": "Capital allocation, financial decisions and compliance sign-off stay human-only.",
        "tessera_noun_category": "noun.benchmark_suite",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "agricultural-coop-pest-advisory",
        "title": "Smallholder cooperative extension bulletin and weather-window synthesis",
        "sector": "public_good",
        "input_artifact": "land-grant university integrated pest management bulletins and 7-day rain forecasts",
        "deliverable": "cited non-chemical and threshold treatment checklist in local dialect",
        "human_only_boundary": "Restricted-use pesticide sign-off and agronomist field diagnosis stay human-only.",
        "tessera_noun_category": "noun.public_source",
        "tessera_verb_category": "verb.situate",
    },
    {
        "slug": "public-defender-transcript-indexing",
        "title": "Time-coded hearing transcript witness-statement cross-reference indexing",
        "sector": "public_good",
        "input_artifact": "consented synthetic deposition transcripts, exhibit page tables and timestamp logs",
        "deliverable": "page-and-line statement concordance flagging timeline contradictions for counsel review",
        "human_only_boundary": "Case strategy, motion drafting, witness examination and legal judgment stay human-only.",
        "tessera_noun_category": "noun.reflex_procedure",
        "tessera_verb_category": "verb.decompose_dag",
    },
    {
        "slug": "community-solar-interconnection-check",
        "title": "Low-income community solar tariff and utility interconnection queue audit",
        "sector": "public_good",
        "input_artifact": "public PUC tariff schedules, feeder hosting-capacity CSVs and subscriber split rules",
        "deliverable": "bill-credit math verification and interconnection milestone checklist",
        "human_only_boundary": "Subscriber contract execution, PE engineering stamps and PUC filings stay human-only.",
        "tessera_noun_category": "noun.public_source",
        "tessera_verb_category": "verb.verify_gate",
    },
    {
        "slug": "maternal-health-referral-directory",
        "title": "Perinatal community health worker Medicaid-accepting clinic directory refresh",
        "sector": "public_good",
        "input_artifact": "published state Medicaid provider directories, transit stops and language availability tables",
        "deliverable": "stale-phone flagged clinic directory with bus-route and interpreter notes",
        "human_only_boundary": "Patient triage, obstetric risk assessment and warm-handoff referrals stay human-only.",
        "tessera_noun_category": "noun.feed_source",
        "tessera_verb_category": "verb.recheck_fragility",
    },
)

# 10 operational constraints (Gaia2-inspired asynchronous events, dynamic drift, resource pressure).
OPERATIONAL_CONSTRAINTS_10: tuple[dict[str, Any], ...] = (
    {
        "slug": "mid-episode-schema-amendment",
        "title": "Mid-episode statutory or schema amendment arrives at step 3",
        "gaia2_perturbation": "async_rule_update",
        "latency_budget_ms": 12000,
        "max_token_budget": 6000,
        "requires_idempotent_replay": True,
    },
    {
        "slug": "noisy-ocr-and-code-switching",
        "title": "15 percent OCR character noise with bilingual colloquial code-switching",
        "gaia2_perturbation": "input_corruption_and_slang",
        "latency_budget_ms": 18000,
        "max_token_budget": 8000,
        "requires_idempotent_replay": False,
    },
    {
        "slug": "adversarial-prompt-injection-decoy",
        "title": "Embedded untrusted directive attempting to widen visibility or exfiltrate notes",
        "gaia2_perturbation": "indirect_prompt_injection",
        "latency_budget_ms": 8000,
        "max_token_budget": 4096,
        "requires_idempotent_replay": True,
    },
    {
        "slug": "strict-sub-2s-edge-triage",
        "title": "Sub-2-second interactive frontline triage ceiling on commodity CPU hardware",
        "gaia2_perturbation": "tight_wall_clock_deadline",
        "latency_budget_ms": 2000,
        "max_token_budget": 1500,
        "requires_idempotent_replay": False,
    },
    {
        "slug": "conflicting-source-versions",
        "title": "Two pinned source tables disagree on totals due to an unmerged corrigendum",
        "gaia2_perturbation": "contradictory_upstream_facts",
        "latency_budget_ms": 20000,
        "max_token_budget": 10000,
        "requires_idempotent_replay": True,
    },
    {
        "slug": "worker-lease-preemption-recovery",
        "title": "Primary worker lease expires mid-run; second worker claims with incremented fence",
        "gaia2_perturbation": "lease_timeout_failover",
        "latency_budget_ms": 30000,
        "max_token_budget": 12000,
        "requires_idempotent_replay": True,
    },
    {
        "slug": "zero-dollar-volunteer-burst",
        "title": "100-item backlog spike handled exclusively by donated spare-token capacity",
        "gaia2_perturbation": "queue_backpressure_surge",
        "latency_budget_ms": 45000,
        "max_token_budget": 16000,
        "requires_idempotent_replay": True,
    },
    {
        "slug": "strict-2048-context-knapsack",
        "title": "Hard 2,048-token context window requiring MinHash deduplication and pruning",
        "gaia2_perturbation": "tight_context_knapsack",
        "latency_budget_ms": 6000,
        "max_token_budget": 2048,
        "requires_idempotent_replay": False,
    },
    {
        "slug": "missing-denominator-abstention",
        "title": "Key denominator row omitted from source packet; worker must report unknown cleanly",
        "gaia2_perturbation": "partial_observability_trap",
        "latency_budget_ms": 10000,
        "max_token_budget": 5000,
        "requires_idempotent_replay": False,
    },
    {
        "slug": "cross-jurisdiction-cutoff-drift",
        "title": "Post-cutoff rule revision invalidates pretrained parametric assumptions",
        "gaia2_perturbation": "post_cutoff_temporal_shift",
        "latency_budget_ms": 15000,
        "max_token_budget": 9000,
        "requires_idempotent_replay": True,
    },
)

# 4 data-sensitivity and connectivity regimes (25 * 10 * 4 = 1,000 exact situations).
CONNECTIVITY_SENSITIVITY_REGIMES: tuple[dict[str, Any], ...] = (
    {
        "slug": "high-pii-offline-airgap",
        "sensitivity": "high_pii_local_only",
        "connectivity": "offline_airgap",
        "allows_cloud_raw_payload": False,
        "requires_local_kit_or_rule": True,
        "requires_lane_split_for_cloud": False,
    },
    {
        "slug": "mixed-private-and-public-intermittent",
        "sensitivity": "mixed_private_and_public",
        "connectivity": "intermittent_edge_sync",
        "allows_cloud_raw_payload": False,
        "requires_local_kit_or_rule": False,
        "requires_lane_split_for_cloud": True,
    },
    {
        "slug": "regulated-hipaa-legal-fenced",
        "sensitivity": "regulated_confidential",
        "connectivity": "surface_scoped_private_link",
        "allows_cloud_raw_payload": False,
        "requires_local_kit_or_rule": False,
        "requires_lane_split_for_cloud": True,
    },
    {
        "slug": "open-public-records-connected",
        "sensitivity": "public_records_only",
        "connectivity": "broadband_connected",
        "allows_cloud_raw_payload": True,
        "requires_local_kit_or_rule": False,
        "requires_lane_split_for_cloud": False,
    },
)


def generate_environment(
    index: int,
    llm_extender: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deterministically generate situation ENV-0001..ENV-1000 from 0-based index in [0, 999]."""
    if not (0 <= index < 1000):
        raise ValueError(f"environment index {index} out of [0, 999]")
    domain_idx = index // 40
    rem = index % 40
    constraint_idx = rem // 4
    regime_idx = rem % 4

    dom = DOMAINS_25[domain_idx]
    con = OPERATIONAL_CONSTRAINTS_10[constraint_idx]
    reg = CONNECTIVITY_SENSITIVITY_REGIMES[regime_idx]

    env_id = f"ENV-{index + 1:04d}"
    base: dict[str, Any] = {
        "env_id": env_id,
        "index": index,
        "domain_slug": dom["slug"],
        "domain_title": dom["title"],
        "sector": dom["sector"],
        "constraint_slug": con["slug"],
        "constraint_title": con["title"],
        "gaia2_perturbation": con["gaia2_perturbation"],
        "regime_slug": reg["slug"],
        "sensitivity": reg["sensitivity"],
        "connectivity": reg["connectivity"],
        "allows_cloud_raw_payload": reg["allows_cloud_raw_payload"],
        "requires_local_kit_or_rule": reg["requires_local_kit_or_rule"],
        "requires_lane_split_for_cloud": reg["requires_lane_split_for_cloud"],
        "latency_budget_ms": con["latency_budget_ms"],
        "max_token_budget": con["max_token_budget"],
        "requires_idempotent_replay": con["requires_idempotent_replay"],
        "input_artifact": dom["input_artifact"],
        "target_deliverable": dom["deliverable"],
        "human_only_boundary": dom["human_only_boundary"],
        "suggested_noun_category": dom["tessera_noun_category"],
        "suggested_verb_category": dom["tessera_verb_category"],
    }
    if llm_extender is not None:
        ext = llm_extender(dict(base))
        if isinstance(ext, dict) and ext.get("synthetic_vignette"):
            base["worker_llm_vignette"] = str(ext["synthetic_vignette"])[:600]
    digest = hashlib.sha256(
        json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    base["env_sha256"] = digest
    return base


def generate_environments_1000(
    llm_extender: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return all 1,000 indexed environments ENV-0001..ENV-1000."""
    return [generate_environment(i, llm_extender=llm_extender) for i in range(1000)]
