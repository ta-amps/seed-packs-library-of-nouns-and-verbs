"""SiraNounEnricher: offline corpus-discriminative enrichment for Task Objects and Seed Packs."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "before", "by", "can", "collection",
        "do", "does", "each", "every", "for", "from", "has", "have", "in", "into", "is",
        "it", "its", "lets", "not", "nouns", "of", "on", "only", "or", "pack", "packs",
        "so", "stays", "that", "the", "their", "them", "then", "this", "to", "under",
        "use", "uses", "using", "verbs", "what", "when", "where", "while", "who", "with",
        "without", "work", "worker", "workers",
    }
)

TOKEN_RE = re.compile(r"[a-z0-9]+")
HEX_LIKE_RE = re.compile(r"^[0-9a-f]{6,}$")
TIMESTAMP_FRAG_RE = re.compile(r"^\d+t\d+$")

# General concept-bridge thesaurus applied offline during SIRA document expansion
# when a pack's deep noun/verb graph exhibits >= 2 specific technical markers.
CONCEPT_EXPANSION_RULES: tuple[tuple[frozenset[str], tuple[str, ...]], ...] = (
    (
        frozenset({"handwritten", "slang", "illegible", "smudg", "abbreviation"}),
        ("cursive intake notes", "regional dialect", "smudged paper form", "uncertain reading flag"),
    ),
    (
        frozenset({"wcag", "contrast", "luminance", "reflow", "a11y"}),
        ("colorblind palette", "low vision", "screen reader navigation", "keyboard tab focus"),
    ),
    (
        frozenset({"lufs", "loudness", "cer", "asr", "ducking"}),
        ("voiceover clipping", "background music ducking", "speaking pace", "caption sync"),
    ),
    (
        frozenset({"dwell", "crossfade", "burns", "pill", "drift"}),
        ("flash cut", "ghosting transition", "camera pan drift", "split attention overload"),
    ),
    (
        frozenset({"minhash", "knapsack", "rrf", "sanitized", "injected"}),
        ("context window overflow", "near duplicate chunks", "prompt injection defense", "token budget packing"),
    ),
    (
        frozenset({"lora", "bootstrap", "disjointness", "shim"}),
        ("post cutoff api facts", "parametric adapter vs prompt shim", "volatile policy revocation"),
    ),
    (
        frozenset({"purged", "embargo", "sharpe", "icir", "turnover"}),
        ("temporal lookahead leak", "causal cohort split", "multiple hypothesis deflation", "volatility regime"),
    ),
    (
        frozenset({"mutations", "kills", "operators", "trusted"}),
        ("meta test suite", "grading the grader", "catch broken validator", "mutation kill rate"),
    ),
    (
        frozenset({"tombstone", "deprecations", "upstream", "staleness"}),
        ("outdated upstream docs", "sunset dependency", "bitrot expiration", "superseding replacement"),
    ),
    (
        frozenset({"fy2026", "fy2027", "appropriations", "fiscal"}),
        ("municipal treasury spending", "enacted line item", "appropriation table citation"),
    ),
    (
        frozenset({"translations", "printing", "multilingual", "clinic"}),
        ("bilingual community leaflet", "dropped contact numbers", "plain reading level"),
    ),
    (
        frozenset({"pantry", "allergen", "perishable", "pickup"}),
        ("household food box", "cold chain expiry", "dietary restriction pickup"),
    ),
    (
        frozenset({"anonymous", "greeting", "goods", "donor"}),
        ("charitable contribution receipt", "acknowledgment letter", "anonymous giver opt out"),
    ),
    (
        frozenset({"volunteer", "shift", "relief", "fatigue"}),
        ("emergency shelter roster", "on call relief staffing", "rest gap check"),
    ),
    (
        frozenset({"victim", "referral", "warm", "trauma"}),
        ("survivor crisis directory", "confidential shelter handoff", "trauma informed referral"),
    ),
    (
        frozenset({"ftc", "payee", "deposit", "loan"}),
        ("advance fee scam red flags", "coercive payment demand", "non accusatory fraud dossier"),
    ),
    (
        frozenset({"tpm", "baseten", "fireworks", "modal", "qlora", "multilora"}),
        ("rate paced burst swarm", "serverless gpu qlora", "specialist adapter hot swap", "partner compute credits"),
    ),
    (
        frozenset({"hypercube", "stakeholders", "personas", "gaia2"}),
        ("thousand scenario simulation", "combinatorial stress matrix", "multi stakeholder veto"),
    ),
    (
        frozenset({"sira", "analogy", "isomorphism", "dgmh"}),
        ("single shot cross domain search", "self learning retrieval", "execution report reflection"),
    ),
    (
        frozenset({"blame", "todo", "swallowed", "todos"}),
        ("technical debt scan", "silent exception catch", "rotting todo markers"),
    ),
    (
        frozenset({"readyz", "canary", "reload", "unwired"}),
        ("dead unwired module", "config hot reload", "shallow healthz endpoint"),
    ),
    (
        frozenset({"annoyances", "complaint", "papercuts", "friction"}),
        ("ux frustration tour", "complaint frequency ranking", "cli papercut triage"),
    ),
    (
        frozenset({"void", "declined", "fallbacks", "night"}),
        ("autonomous overnight batch", "morning audit log", "unsupervised fallback receipt"),
    ),
    (
        frozenset({"filesystem", "deletions", "archive", "disk"}),
        ("messy shared drive", "dedup folder archive", "zero deletion organizer"),
    ),
)


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokenizer with stopword filtering and simple stem normalization."""
    raw = TOKEN_RE.findall(text.lower())
    out: list[str] = []
    for tok in raw:
        if tok in STOPWORDS or len(tok) < 2:
            continue
        out.append(tok)
        if len(tok) > 5 and tok.endswith("ing"):
            out.append(tok[:-3])
        elif len(tok) > 4 and tok.endswith("ed"):
            out.append(tok[:-2])
        elif len(tok) > 4 and tok.endswith("es"):
            out.append(tok[:-2])
        elif len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            out.append(tok[:-1])
    return out


def _is_noise_token(term: str) -> bool:
    if len(term) < 3 or term.isdigit():
        return True
    if TIMESTAMP_FRAG_RE.match(term):
        return True
    if HEX_LIKE_RE.match(term) and any(ch.isdigit() for ch in term):
        return True
    return False


def _flatten_strings(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        res: list[str] = []
        for k, v in obj.items():
            res.append(str(k))
            res.extend(_flatten_strings(v))
        return res
    if isinstance(obj, list):
        res = []
        for item in obj:
            res.extend(_flatten_strings(item))
        return res
    return []


class SiraNounEnricher:
    """Offline corpus-discriminative enricher for Seed Packs and Task Objects (Meta SIRA pattern)."""

    def __init__(self, top_k_discriminative: int = 45) -> None:
        self.top_k_discriminative = top_k_discriminative

    @staticmethod
    def load_packs_from_directory(packs_dir: Path) -> list[dict[str, Any]]:
        packs: list[dict[str, Any]] = []
        for child in sorted(packs_dir.iterdir()):
            src_path = child / "source.json"
            if child.is_dir() and src_path.is_file():
                data = json.loads(src_path.read_text(encoding="utf-8"))
                data["_has_code_dir"] = (child / "code").is_dir()
                packs.append(data)
        return packs

    def enrich_corpus(self, packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compute discriminative terms, I/O signatures, capability facets and predictive query expansions."""
        n_docs = max(1, len(packs))
        deep_token_counters: list[Counter[str]] = []
        doc_freq: Counter[str] = Counter()

        for pack in packs:
            deep_text = " ".join(_flatten_strings(pack))
            counts = Counter(tokenize(deep_text))
            deep_token_counters.append(counts)
            for term in counts:
                doc_freq[term] += 1

        enriched_records: list[dict[str, Any]] = []
        for pack, counts in zip(packs, deep_token_counters):
            pack_id = pack["pack_id"]
            total_terms = max(1, sum(counts.values()))

            scored_terms: list[tuple[float, str]] = []
            for term, tf in counts.items():
                if _is_noise_token(term):
                    continue
                df = doc_freq[term]
                if df > max(2, int(0.40 * n_docs)):
                    continue
                idf = math.log((n_docs + 1.0) / (df + 0.5))
                tf_norm = (tf / total_terms) ** 0.65
                scored_terms.append((tf_norm * idf, term))
            scored_terms.sort(key=lambda item: (-item[0], item[1]))
            discriminative_terms = [t for _, t in scored_terms[: self.top_k_discriminative]]

            nouns = pack.get("nouns", [])
            verbs = pack.get("verbs", [])
            noun_categories = sorted({n["category"] for n in nouns})
            verb_kinds = sorted({v["kind"] for v in verbs})
            slot_categories = sorted(
                {s["category"] for v in verbs for s in v.get("slots", [])}
            )
            template_cat_by_slug = {n["slug"]: n["category"] for n in nouns}
            produced_categories = sorted(
                {
                    template_cat_by_slug.get(p["template"], "noun.external")
                    for v in verbs
                    for p in v.get("produces", [])
                }
            )
            claimants = sorted({v.get("claimant", "agent") for v in verbs})
            model_modes = sorted({v.get("model_use", "worker_allowance") for v in verbs})
            review_modes = sorted({v.get("review", "owning_policy") for v in verbs})

            facets: list[str] = []
            if pack_id.startswith("kit-") or "public-good-kits" in pack.get("dependencies", []):
                facets.append("nonprofit_agent_kit")
            if pack.get("_has_code_dir") or any(n["category"] == "noun.code_node" for n in nouns):
                facets.append("tested_executable_code")
            if "distinct_reviewer" in review_modes:
                facets.append("two_step_distinct_reviewer")
            if model_modes == ["none"]:
                facets.append("zero_model_deterministic")
            if "human" in claimants:
                facets.append("explicit_human_claimant")
            if any("update_slot" in v for v in verbs):
                facets.append("compare_and_set_mutation")

            term_set = set(counts)
            pqe_phrases: list[str] = []
            for triggers, expansions in CONCEPT_EXPANSION_RULES:
                if len(term_set & triggers) >= 2:
                    pqe_phrases.extend(expansions)

            for v in verbs:
                pqe_phrases.append(f"{v['title']} -> {v['outcome']}")
            for n in nouns:
                if n.get("role") in {"guardrail", "spec", "rules"}:
                    pqe_phrases.append(n["title"])

            surface_text = f"{pack_id.replace('-', ' ')} {pack['title']} {pack['summary']}"
            enriched_text = " ".join(
                [
                    surface_text,
                    surface_text,
                    " ".join(discriminative_terms * 2),
                    " ".join(facets),
                    " ".join(noun_categories + verb_kinds + slot_categories),
                    " ".join(pqe_phrases),
                ]
            )
            record = {
                "pack_id": pack_id,
                "title": pack["title"],
                "summary": pack["summary"],
                "surface_lexical_text": surface_text,
                "discriminative_terms": discriminative_terms,
                "io_signatures": {
                    "slot_categories": slot_categories,
                    "produced_categories": produced_categories,
                    "noun_categories": noun_categories,
                    "verb_kinds": verb_kinds,
                    "claimants": claimants,
                    "model_use": model_modes,
                    "review_modes": review_modes,
                },
                "capability_facets": facets,
                "predictive_query_expansions": pqe_phrases[:18],
                "sira_enriched_text": enriched_text,
            }
            record["enrichment_sha256"] = hashlib.sha256(
                json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            enriched_records.append(record)
        return enriched_records
