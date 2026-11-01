"""Deduplicate noisy raw notes, chunk text into content-addressed records, and score category gaps."""

from __future__ import annotations

import hashlib
import re
from typing import Any

DEFAULT_SHINGLE_SIZE = 5
_TOKEN_RE = re.compile(r"[A-Za-z0-9%]+")
_WEIGHT_LINE_RE = re.compile(r"^\s*(\d{1,3}(?:\.\d+)?)%\s*(?:\(([\d.]+)\s*pts?\))?\s*$", re.IGNORECASE)
_MD_HEADING_RE = re.compile(r"^\s*#{1,4}\s+(.+?)\s*$")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def word_shingles(text: str, k: int = DEFAULT_SHINGLE_SIZE) -> set[tuple[str, ...]]:
    """Return lowercase k-word shingles from text (falling back to single bag tuple for short text)."""
    words = [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]
    if not words:
        return set()
    if len(words) < k:
        return {tuple(words)}
    return {tuple(words[i : i + k]) for i in range(len(words) - k + 1)}


def shingle_jaccard(text_a: str, text_b: str, k: int = DEFAULT_SHINGLE_SIZE) -> float:
    """Compute word-shingle Jaccard similarity in [0.0, 1.0]."""
    sa = word_shingles(text_a, k=k)
    sb = word_shingles(text_b, k=k)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def split_repeated_pastes(
    raw_text: str,
    anchor_words: int = 6,
    min_repeat_words: int = 16,
) -> list[str]:
    """Split raw text into blocks, detecting inline concatenated clipboard repeats cleanly.

    Handles both blank-line separated blocks and accidental inline multi-pastes where the start
    of paste i+1 is glued directly onto the end of paste i without an intervening newline.
    """
    stripped = raw_text.strip()
    if not stripped:
        return []

    tokens = [(m.group(0).lower(), m.start(), m.end()) for m in _TOKEN_RE.finditer(raw_text)]
    if len(tokens) < max(anchor_words * 2, min_repeat_words * 2):
        parts = [p.strip() for p in re.split(r"\n\s*\n{2,}", raw_text) if p.strip()]
        return parts or [stripped]

    grams: dict[tuple[str, ...], list[int]] = {}
    for idx in range(len(tokens) - anchor_words + 1):
        gram = tuple(tokens[j][0] for j in range(idx, idx + anchor_words))
        grams.setdefault(gram, []).append(idx)

    cuts: set[int] = {0}
    for positions in grams.values():
        if len(positions) < 2:
            continue
        p0 = positions[0]
        for p in positions[1:]:
            if p0 > 0 and tokens[p0 - 1][0] == tokens[p - 1][0]:
                continue
            match_len = 0
            while p + match_len < len(tokens) and p0 + match_len < p and tokens[p0 + match_len][0] == tokens[p + match_len][0]:
                match_len += 1
            if match_len >= min_repeat_words:
                cuts.add(p0)
                cuts.add(p)
                if p + match_len < len(tokens):
                    cuts.add(p + match_len)

    if len(cuts) == 1:
        parts = [p.strip() for p in re.split(r"\n\s*\n{2,}", raw_text) if p.strip()]
        return parts or [stripped]

    sorted_cuts = sorted(cuts)
    blocks: list[str] = []
    for i, tok_idx in enumerate(sorted_cuts):
        start_char = 0 if tok_idx == 0 else tokens[tok_idx][1]
        end_char = tokens[sorted_cuts[i + 1]][1] if i + 1 < len(sorted_cuts) else len(raw_text)
        segment = raw_text[start_char:end_char].strip()
        if segment:
            blocks.append(segment)
    return blocks


def collapse_duplicate_blocks(
    blocks: list[str],
    near_dup_threshold: float = 0.85,
    shingle_size: int = DEFAULT_SHINGLE_SIZE,
) -> dict[str, Any]:
    """Collapse exact and near-duplicate blocks while preserving canonical order and repeat counts."""
    canonical: list[dict[str, Any]] = []
    norm_index: dict[str, int] = {}

    for raw_idx, block in enumerate(blocks):
        clean = block.strip()
        if not clean:
            continue
        norm = _normalize_whitespace(clean)
        norm_sha = _sha256_text(norm)
        if norm_sha in norm_index:
            entry = canonical[norm_index[norm_sha]]
            entry["occurrences"] += 1
            entry["raw_block_indices"].append(raw_idx)
            continue

        matched_idx: int | None = None
        for idx, existing in enumerate(canonical):
            sim = shingle_jaccard(norm, existing["_norm"], k=shingle_size)
            if sim >= near_dup_threshold:
                matched_idx = idx
                existing["occurrences"] += 1
                existing["near_duplicate_matches"] += 1
                existing["raw_block_indices"].append(raw_idx)
                break

        if matched_idx is None:
            norm_index[norm_sha] = len(canonical)
            canonical.append(
                {
                    "block_id": f"block.{len(canonical) + 1:02d}",
                    "canonical_sha256": _sha256_text(clean),
                    "normalized_sha256": norm_sha,
                    "byte_length": len(clean.encode("utf-8")),
                    "occurrences": 1,
                    "near_duplicate_matches": 0,
                    "raw_block_indices": [raw_idx],
                    "text": clean,
                    "_norm": norm,
                }
            )

    for item in canonical:
        item.pop("_norm", None)

    raw_count = len([b for b in blocks if b.strip()])
    unique_count = len(canonical)
    ratio = f"{raw_count}:{unique_count}" if unique_count > 0 else "0:0"
    return {
        "raw_block_count": raw_count,
        "unique_block_count": unique_count,
        "compression_ratio": ratio,
        "canonical_blocks": canonical,
    }


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug[:48] or "section"


def chunk_canonical_blocks(canonical_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split canonical blocks into content-addressed semantic sections (headings and weighted pillars)."""
    chunks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for block in canonical_blocks:
        text = block["text"]
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
        for p_idx, para in enumerate(paragraphs):
            lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
            if not lines:
                continue

            # Handle preamble + first weighted pillar sharing the opening paragraph
            if len(lines) >= 5 and _WEIGHT_LINE_RE.match(lines[3]):
                preamble_text = "\n".join(lines[:2])
                chunks.append(_make_chunk(lines[0], preamble_text, None, None, seen_ids))
                lines = lines[2:]

            title = lines[0]
            md = _MD_HEADING_RE.match(title)
            if md:
                title = md.group(1)

            weight_pct: float | None = None
            points: float | None = None
            if len(lines) >= 2:
                wm = _WEIGHT_LINE_RE.match(lines[1])
                if wm:
                    weight_pct = float(wm.group(1))
                    points = float(wm.group(2)) if wm.group(2) else round(weight_pct / 10.0, 3)

            chunk_text = "\n".join(lines)
            if len(title.split()) > 10:
                title = f"section_{p_idx + 1}"
            chunks.append(_make_chunk(title, chunk_text, weight_pct, points, seen_ids))

    return chunks


def _make_chunk(
    title: str,
    text: str,
    weight_pct: float | None,
    points: float | None,
    seen_ids: set[str],
) -> dict[str, Any]:
    base_slug = _slugify(title)
    chunk_id = f"chunk.{base_slug}"
    suffix = 2
    while chunk_id in seen_ids:
        chunk_id = f"chunk.{base_slug}_{suffix}"
        suffix += 1
    seen_ids.add(chunk_id)

    words = [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]
    signals = sorted(
        {
            w
            for w in words
            if w
            in {
                "specificity",
                "multimodal",
                "sam",
                "audio",
                "speech",
                "weights",
                "commit",
                "modular",
                "test",
                "suites",
                "workflows",
                "dockerfiles",
                "deployment",
                "video",
                "walkthroughs",
                "security",
                "unicode",
                "mcp",
                "persona",
                "harnesses",
            }
        }
    )
    out: dict[str, Any] = {
        "chunk_id": chunk_id,
        "title": title,
        "text_sha256": _sha256_text(text),
        "byte_length": len(text.encode("utf-8")),
        "token_estimate": max(1, round(len(words) * 1.3)),
        "signals": signals,
        "text": text,
    }
    if weight_pct is not None:
        out["weight_pct"] = weight_pct
        out["points"] = points
    return out


DEFAULT_CATEGORY_CATALOG: list[dict[str, Any]] = [
    {
        "category_id": "cat.submission-rubric-and-repo-readiness",
        "title": "Submission Rubric & Repository Readiness",
        "keywords": {"rubric", "specificity", "commit", "modular", "test", "workflows", "dockerfiles", "deployment", "video", "walkthroughs"},
        "existing_pack_count": 1,
        "default_actor": "engineering team preparing a public repository release",
        "default_constraint": "must verify code wiring, tests, CI, containers, live HTTP status, and walkthrough links deterministically",
    },
    {
        "category_id": "cat.multimodal-vision-audio-and-alignment",
        "title": "Multimodal Segmentation, Speech & Layout Alignment",
        "keywords": {"multimodal", "sam", "segmentation", "mask", "audio", "speech", "video", "caption"},
        "existing_pack_count": 1,
        "default_actor": "media pipeline worker processing segmented video and speech transcripts",
        "default_constraint": "captions and overlays must avoid occluding segmented foreground masks while keeping audio-visual sync tight",
    },
    {
        "category_id": "cat.open-weight-finetuning-and-adapter-ops",
        "title": "Open-Weight Fine-Tuning & Adapter Receipts",
        "keywords": {"weights", "fine", "tuned", "lora", "models", "sdks", "adapter", "calibration"},
        "existing_pack_count": 2,
        "default_actor": "ML engineer adapting open-weight models on domain corpora",
        "default_constraint": "adapter configs and dataset splits must be pinned with held-out evaluation checks before promotion",
    },
    {
        "category_id": "cat.agent-personas-harnesses-and-supply-chain",
        "title": "Agent Role Compilation & Config Supply-Chain Defense",
        "keywords": {"persona", "personas", "harnesses", "subagents", "unicode", "mcp", "hooks", "spoofing", "memory"},
        "existing_pack_count": 2,
        "default_actor": "multi-harness developer maintaining agent definitions and repository rules",
        "default_constraint": "role routing must stay separate from permissions and untrusted rule or MCP configs must be scanned before clone use",
    },
]


def extract_situations_and_gaps(
    chunks: list[dict[str, Any]],
    category_catalog: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Map content-addressed chunks to real-world situations and rank category coverage gaps."""
    catalog = category_catalog if category_catalog is not None else DEFAULT_CATEGORY_CATALOG
    situations: list[dict[str, Any]] = []
    demand_by_cat: dict[str, float] = {c["category_id"]: 0.0 for c in catalog}
    matched_chunks_by_cat: dict[str, list[str]] = {c["category_id"]: [] for c in catalog}

    for chunk in chunks:
        words = {m.group(0).lower() for m in _TOKEN_RE.finditer(chunk["text"])}
        weight_boost = float(chunk.get("weight_pct") or 10.0) / 10.0

        best_cat: dict[str, Any] | None = None
        best_overlap = 0
        for cat in catalog:
            overlap = len(words & set(cat["keywords"]))
            if overlap > best_overlap:
                best_overlap = overlap
                best_cat = cat

        if best_cat is None or best_overlap == 0:
            continue

        cid = best_cat["category_id"]
        demand_by_cat[cid] += round(best_overlap * weight_boost, 4)
        matched_chunks_by_cat[cid].append(chunk["chunk_id"])
        situations.append(
            {
                "situation_id": f"sit.{chunk['chunk_id'].replace('chunk.', '')}",
                "source_chunk_id": chunk["chunk_id"],
                "source_chunk_sha256": chunk["text_sha256"],
                "category_id": cid,
                "actor": best_cat["default_actor"],
                "problem": _normalize_whitespace(chunk["text"])[:240],
                "constraint": best_cat["default_constraint"],
                "keyword_overlap": best_overlap,
            }
        )

    ranked_categories: list[dict[str, Any]] = []
    for cat in catalog:
        cid = cat["category_id"]
        demand = round(demand_by_cat[cid], 4)
        existing = int(cat.get("existing_pack_count", 0))
        gap_score = round(demand / (1.0 + existing), 4)
        ranked_categories.append(
            {
                "category_id": cid,
                "title": cat["title"],
                "demand_score": demand,
                "existing_pack_count": existing,
                "gap_score": gap_score,
                "supporting_chunk_ids": matched_chunks_by_cat[cid],
            }
        )

    ranked_categories.sort(key=lambda r: (-r["gap_score"], r["category_id"]))
    return {
        "situations": situations,
        "ranked_category_gaps": ranked_categories,
    }


def mine_brainstorm_text(
    raw_text: str,
    near_dup_threshold: float = 0.85,
    category_catalog: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run end-to-end paste splitting, deduplication, chunking, situation extraction, and gap ranking."""
    raw_sha = _sha256_text(raw_text)
    split_blocks = split_repeated_pastes(raw_text)
    dedup = collapse_duplicate_blocks(split_blocks, near_dup_threshold=near_dup_threshold)
    chunks = chunk_canonical_blocks(dedup["canonical_blocks"])
    mined = extract_situations_and_gaps(chunks, category_catalog=category_catalog)
    return {
        "raw_bytes": len(raw_text.encode("utf-8")),
        "raw_sha256": raw_sha,
        "deduplication": {
            "raw_block_count": dedup["raw_block_count"],
            "unique_block_count": dedup["unique_block_count"],
            "compression_ratio": dedup["compression_ratio"],
            "canonical_blocks": [
                {
                    "block_id": b["block_id"],
                    "canonical_sha256": b["canonical_sha256"],
                    "byte_length": b["byte_length"],
                    "occurrences": b["occurrences"],
                    "near_duplicate_matches": b["near_duplicate_matches"],
                }
                for b in dedup["canonical_blocks"]
            ],
        },
        "chunks": chunks,
        "situations": mined["situations"],
        "ranked_category_gaps": mined["ranked_category_gaps"],
    }
