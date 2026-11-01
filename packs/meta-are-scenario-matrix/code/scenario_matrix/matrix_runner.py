"""1,000-cell 4D Latin-hypercube sweep and 10^12 combinatorial expansion API."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from typing import Any, Callable

from .environments import DOMAINS_25, generate_environment, generate_environments_1000
from .methods import generate_method, generate_methods_1000
from .personas import generate_persona, generate_personas_1000
from .stakeholders import (
    STAKEHOLDER_POSITIONS_10,
    evaluate_and_digest_episode,
    generate_stakeholder,
    generate_stakeholders_1000,
)

ADDRESSABLE_TUPLES: int = 1_000 * 1_000 * 1_000 * 1_000  # 10^12


def _parse_axis_index(ref: int | str, prefix: str) -> int:
    if isinstance(ref, int):
        if not (0 <= ref < 1000):
            raise ValueError(f"{prefix} index {ref} out of [0, 999]")
        return ref
    text = ref.strip().upper()
    if text.startswith(prefix + "-"):
        num = int(text.split("-", 1)[1])
        if not (1 <= num <= 1000):
            raise ValueError(f"{ref} out of {prefix}-0001..{prefix}-1000")
        return num - 1
    raise ValueError(f"unrecognized {prefix} identifier {ref!r}")


def resolve_tuple(
    env_ref: int | str,
    meth_ref: int | str,
    pers_ref: int | str,
    stkh_ref: int | str,
    llm_extender: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate any single 4-tuple out of the 10^12 addressable scenario matrix on demand."""
    ei = _parse_axis_index(env_ref, "ENV")
    mi = _parse_axis_index(meth_ref, "METH")
    pi = _parse_axis_index(pers_ref, "PERS")
    si = _parse_axis_index(stkh_ref, "STKH")
    global_idx = ((ei * 1000 + mi) * 1000 + pi) * 1000 + si
    ep = evaluate_and_digest_episode(
        generate_environment(ei, llm_extender=llm_extender),
        generate_method(mi),
        generate_persona(pi),
        generate_stakeholder(si),
    )
    ep["global_tuple_index"] = global_idx
    return ep


def resolve_tuple_by_global_index(
    global_index: int,
    llm_extender: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Bijective O(1) lookup from [0, 10^12 - 1] into (ENV, METH, PERS, STKH) episode evaluation."""
    if not (0 <= global_index < ADDRESSABLE_TUPLES):
        raise ValueError(f"global_index {global_index} out of [0, {ADDRESSABLE_TUPLES - 1}]")
    si = global_index % 1000
    rem1 = global_index // 1000
    pi = rem1 % 1000
    rem2 = rem1 // 1000
    mi = rem2 % 1000
    ei = rem2 // 1000
    return resolve_tuple(ei, mi, pi, si, llm_extender=llm_extender)


def expand_combinatorial_slice(
    env_indices: list[int],
    meth_indices: list[int],
    pers_indices: list[int],
    stkh_indices: list[int],
    max_cells: int = 10_000,
) -> list[dict[str, Any]]:
    """Evaluate a bounded Cartesian sub-slice of the 10^12 matrix."""
    total = len(env_indices) * len(meth_indices) * len(pers_indices) * len(stkh_indices)
    if total > max_cells:
        raise ValueError(f"requested slice size {total} exceeds max_cells={max_cells}")
    out: list[dict[str, Any]] = []
    for ei in env_indices:
        for mi in meth_indices:
            for pi in pers_indices:
                for si in stkh_indices:
                    out.append(resolve_tuple(ei, mi, pi, si))
    return out


def _stratified_bijection_1000(rng: random.Random) -> list[int]:
    """Stratified 10-stratum x 100-item Latin-hypercube permutation over 0..999."""
    strata = [list(range(s * 100, (s + 1) * 100)) for s in range(10)]
    for bucket in strata:
        rng.shuffle(bucket)
    order: list[int] = []
    for step in range(100):
        stratum_ring = list(range(10))
        rng.shuffle(stratum_ring)
        for s in stratum_ring:
            order.append(strata[s][step])
    return order


def run_latin_hypercube_sweep_1000(
    seed: int = 20261031,
    llm_extender: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run a 1,000-episode 4D Latin-hypercube sweep covering 100% of all four 1,000-element axes."""
    rng = random.Random(seed)
    envs = generate_environments_1000(llm_extender=llm_extender)
    meths = generate_methods_1000()
    pers = generate_personas_1000()
    stkhs = generate_stakeholders_1000()

    perm_env = list(range(1000))
    perm_meth = _stratified_bijection_1000(rng)
    perm_pers = _stratified_bijection_1000(rng)
    perm_stkh = _stratified_bijection_1000(rng)

    verdict_counts: Counter[str] = Counter()
    block_reason_counts: Counter[str] = Counter()
    topology_counts: Counter[str] = Counter()
    compute_tier_counts: Counter[str] = Counter()
    harness_counts: Counter[str] = Counter()

    domain_stats: dict[str, dict[str, Any]] = {
        d["slug"]: {
            "domain_slug": d["slug"],
            "domain_title": d["title"],
            "sector": d["sector"],
            "human_only": d["human_only_boundary"],
            "episodes": 0,
            "approved_direct": 0,
            "approved_partitioned": 0,
            "blocked": 0,
        }
        for d in DOMAINS_25
    }
    stakeholder_stats: dict[str, dict[str, Any]] = {
        p["slug"]: {
            "position": p["slug"],
            "veto_axis": p["veto_axis"],
            "episodes": 0,
            "approved_direct": 0,
            "approved_partitioned": 0,
            "blocked": 0,
        }
        for p in STAKEHOLDER_POSITIONS_10
    }

    noun_tallies: Counter[str] = Counter()
    noun_exemplars: dict[str, dict[str, Any]] = {}
    verb_tallies: Counter[str] = Counter()
    verb_exemplars: dict[str, dict[str, Any]] = {}

    sample_by_verdict: dict[str, dict[str, Any]] = {}

    for step in range(1000):
        env = envs[perm_env[step]]
        meth = meths[perm_meth[step]]
        per = pers[perm_pers[step]]
        stkh = stkhs[perm_stkh[step]]
        ep_id = f"LHS-{step + 1:04d}"
        ep = evaluate_and_digest_episode(env, meth, per, stkh, episode_id=ep_id)

        verdict = ep["verdict"]
        verdict_counts[verdict] += 1
        for reason in ep["block_reasons"]:
            block_reason_counts[reason] += 1
        topology_counts[meth["topology"]] += 1
        compute_tier_counts[meth["compute_tier"]] += 1
        harness_counts[per["harness_preference"]] += 1

        d_row = domain_stats[env["domain_slug"]]
        d_row["episodes"] += 1
        d_row[verdict] += 1

        s_row = stakeholder_stats[stkh["position"]]
        s_row["episodes"] += 1
        s_row[verdict] += 1

        if verdict in {"approved_direct", "approved_partitioned"}:
            n_cand = ep["digested_noun"]
            v_cand = ep["digested_verb"]
            noun_tallies[n_cand["slug"]] += 1
            noun_exemplars.setdefault(n_cand["slug"], n_cand)
            verb_tallies[v_cand["slug"]] += 1
            verb_exemplars.setdefault(v_cand["slug"], v_cand)

        if verdict not in sample_by_verdict:
            sample_by_verdict[verdict] = ep

    top_nouns = [
        {
            **noun_exemplars[slug],
            "supporting_episodes": count,
        }
        for slug, count in sorted(noun_tallies.items(), key=lambda kv: (-kv[1], kv[0]))[:12]
    ]
    top_verbs = [
        {
            **verb_exemplars[slug],
            "supporting_episodes": count,
        }
        for slug, count in sorted(verb_tallies.items(), key=lambda kv: (-kv[1], kv[0]))[:12]
    ]
    top_24_candidates = top_verbs + top_nouns

    domain_list = []
    for d in DOMAINS_25:
        row = dict(domain_stats[d["slug"]])
        ep_n = row["episodes"]
        row["approval_rate"] = round((row["approved_direct"] + row["approved_partitioned"]) / ep_n, 4)
        row["block_rate"] = round(row["blocked"] / ep_n, 4)
        domain_list.append(row)

    stakeholder_list = []
    for p in STAKEHOLDER_POSITIONS_10:
        row = dict(stakeholder_stats[p["slug"]])
        ep_n = row["episodes"]
        row["approval_rate"] = round((row["approved_direct"] + row["approved_partitioned"]) / ep_n, 4)
        row["block_rate"] = round(row["blocked"] / ep_n, 4)
        stakeholder_list.append(row)

    approved_total = verdict_counts["approved_direct"] + verdict_counts["approved_partitioned"]
    digest_doc: dict[str, Any] = {
        "schema_version": "ta-amps.scenario-matrix-digest.v1",
        "mode": "local_verified" if llm_extender is None else "worker_llm_extended",
        "inspired_by": [
            "facebookresearch/meta-agents-research-environments (Meta ARE / Gaia2)",
            "facebookresearch/matrix (Synthetic Multi-Agent Scenario Scaling)",
        ],
        "seed": seed,
        "addressable_tuple_space": ADDRESSABLE_TUPLES,
        "combinatorial_expansion_api": {
            "bijective_index_range": [0, ADDRESSABLE_TUPLES - 1],
            "entrypoint": "scenario_matrix.resolve_tuple_by_global_index(global_index)",
            "slice_entrypoint": "scenario_matrix.expand_combinatorial_slice(env_ids, meth_ids, pers_ids, stkh_ids)",
        },
        "evaluated_lhs_episodes": 1000,
        "axis_coverage": {
            "environments_unique": len(set(perm_env)),
            "methods_unique": len(set(perm_meth)),
            "personas_unique": len(set(perm_pers)),
            "stakeholders_unique": len(set(perm_stkh)),
            "environment_range": "ENV-0001..ENV-1000",
            "method_range": "METH-0001..METH-1000",
            "persona_range": "PERS-0001..PERS-1000",
            "stakeholder_range": "STKH-0001..STKH-1000",
        },
        "aggregate_metrics": {
            "approved_direct_count": verdict_counts["approved_direct"],
            "approved_partitioned_count": verdict_counts["approved_partitioned"],
            "blocked_count": verdict_counts["blocked"],
            "overall_approval_rate": round(approved_total / 1000.0, 4),
            "partitioned_lane_rate": round(verdict_counts["approved_partitioned"] / 1000.0, 4),
            "stakeholder_block_rate": round(verdict_counts["blocked"] / 1000.0, 4),
            "unique_digested_noun_patterns": len(noun_tallies),
            "unique_digested_verb_patterns": len(verb_tallies),
            "block_reasons": dict(sorted(block_reason_counts.items())),
            "topology_distribution": dict(sorted(topology_counts.items())),
            "compute_tier_distribution": dict(sorted(compute_tier_counts.items())),
            "harness_distribution": dict(sorted(harness_counts.items())),
        },
        "domain_breakdown": domain_list,
        "stakeholder_breakdown": stakeholder_list,
        "top_24_digested_candidates": top_24_candidates,
        "sample_episodes": {k: sample_by_verdict[k] for k in sorted(sample_by_verdict)},
    }
    digest_doc["artifact_sha256"] = hashlib.sha256(
        json.dumps(digest_doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest_doc


def run_worked_example(bundle: dict[str, Any]) -> dict[str, Any]:
    """Deterministic recomputation for the pack's synthetic worked example."""
    tuples = bundle["tuples"]
    verdicts: list[str] = []
    digested_verbs: list[str] = []
    digested_nouns: list[str] = []
    blocked_reasons: list[str] = []
    for item in tuples:
        ep = resolve_tuple(item["env_id"], item["method_id"], item["persona_id"], item["stakeholder_id"])
        verdicts.append(ep["verdict"])
        if ep["verdict"] == "blocked":
            blocked_reasons.extend(ep["block_reasons"])
        else:
            digested_verbs.append(ep["digested_verb"]["slug"])
            digested_nouns.append(ep["digested_noun"]["slug"])
    return {
        "evaluated_count": len(tuples),
        "verdicts": verdicts,
        "approved_count": sum(v != "blocked" for v in verdicts),
        "blocked_count": sum(v == "blocked" for v in verdicts),
        "blocked_reasons": sorted(set(blocked_reasons)),
        "digested_verbs": digested_verbs,
        "digested_nouns": digested_nouns,
    }
