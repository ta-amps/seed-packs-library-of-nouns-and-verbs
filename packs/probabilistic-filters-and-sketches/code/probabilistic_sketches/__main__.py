"""CLI entry point for probabilistic-filters-and-sketches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .filters import (
    BlockedBloomFilter,
    CuckooFilter,
    StaticXorFingerprintFilter,
    load_default_grid_spec,
)
from .lsh import MinHashLshDecontaminator, benchmark_simhash_recall
from .sketches import ConservativeCountMinHeavyKeeperHll


def run_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    spec = bundle.get("grid_spec")
    cfg = spec if spec is not None else load_default_grid_spec()

    # 1. BlockedBloomFilter union and 0% false-negative check
    bloom_a = BlockedBloomFilter(spec=cfg)
    bloom_b = BlockedBloomFilter(spec=cfg)
    shard_a = [str(x) for x in bundle["bloom_shard_a"]]
    shard_b = [str(x) for x in bundle["bloom_shard_b"]]
    for item in shard_a:
        bloom_a.add(item)
    for item in shard_b:
        bloom_b.add(item)
    bloom_merged = bloom_a.union(bloom_b)
    bloom_all_present = all(bloom_merged.contains(x) for x in shard_a + shard_b)

    # 2. CuckooFilter insert, O(1) 404 delete and compact base64 round-trip
    cuckoo_items = [str(x) for x in bundle["cuckoo_items"]]
    cuckoo_gone = [str(x) for x in bundle["cuckoo_gone_items"]]
    cuckoo = CuckooFilter(capacity=len(cuckoo_items), spec=cfg)
    for item in cuckoo_items:
        cuckoo.insert(item)
    for gone_item in cuckoo_gone:
        cuckoo.delete(gone_item)
    encoded_cuckoo = cuckoo.to_base64()
    restored_cuckoo = CuckooFilter.from_base64(encoded_cuckoo, spec=cfg)
    gone_set = set(cuckoo_gone)
    live_items = [x for x in cuckoo_items if x not in gone_set]
    cuckoo_live_present = all(restored_cuckoo.contains(x) for x in live_items)
    cuckoo_deleted_absent = all(not restored_cuckoo.contains(x) for x in cuckoo_gone)

    # 3. StaticXorFingerprintFilter static edge set
    if "static_edge_count" in bundle:
        edge_prefix = str(bundle.get("static_edge_prefix", "edge"))
        static_edges = [f"{edge_prefix}:{i}->node:{i + 1}" for i in range(int(bundle["static_edge_count"]))]
    else:
        static_edges = [str(x) for x in bundle["static_edge_keys"]]
    xor_filter = StaticXorFingerprintFilter(static_edges, spec=cfg)
    xor_all_present = all(xor_filter.contains(x) for x in static_edges)

    # 4. MultiProbeSimHashLshExpander recall benchmark
    bench = benchmark_simhash_recall(
        distances=[int(d) for d in bundle["simhash_distances"]],
        trials_per_distance=int(bundle["simhash_trials"]),
        seed=int(bundle["simhash_seed"]),
        spec=cfg,
    )
    probe_dist = str(bundle["simhash_report_distance"])
    dist_metrics = bench["recall_by_hamming_distance"][probe_dist]

    # 5. MinHashLshDecontaminator holdout scan
    decontam = MinHashLshDecontaminator(spec=cfg)
    for hdoc in bundle["holdout_docs"]:
        decontam.index_holdout(str(hdoc["id"]), str(hdoc["text"]))
    scan_res = decontam.scan_candidates(list(bundle["candidate_docs"]))

    # 6. ConservativeCountMinHeavyKeeperHll streaming summary
    sketch = ConservativeCountMinHeavyKeeperHll(spec=cfg)
    for ev in bundle["stream_events"]:
        sketch.observe(str(ev["key"]), int(ev.get("count", 1)))
    top_entries = sketch.top_k()
    top_key = str(top_entries[0]["key"]) if top_entries else ""

    return {
        "bloom_zero_false_negatives": bloom_all_present,
        "bloom_theoretical_fpr": bloom_merged.theoretical_fpr(),
        "cuckoo_live_present": cuckoo_live_present,
        "cuckoo_deleted_absent": cuckoo_deleted_absent,
        "cuckoo_base64_chars": len(encoded_cuckoo),
        "xor_zero_false_negatives": xor_all_present,
        "xor_bits_per_key": xor_filter.bits_per_key(),
        "simhash_exact_probe_keys": int(bench["exact_probe_key_count"]),
        "simhash_1bit_probe_keys": int(bench["multiprobe_1bit_key_count"]),
        "simhash_pigeonhole_exact_hit": bool(bench["pigeonhole_1flip_per_band_exact_hit"]),
        "simhash_pigeonhole_1bit_hit": bool(bench["pigeonhole_1flip_per_band_1bit_hit"]),
        "simhash_target_exact_recall": float(dist_metrics["exact_0bit_recall"]),
        "simhash_target_1bit_recall": float(dist_metrics["multiprobe_1bit_recall"]),
        "contaminated_candidate_ids": [c["candidate_id"] for c in scan_res["contaminated"]],
        "clean_candidate_ids": list(scan_res["clean_ids"]),
        "heavy_hitter_top_key": top_key,
        "heavy_hitter_cms_estimate": sketch.estimate_frequency(top_key) if top_key else 0,
        "hll_distinct_estimate": sketch.estimate_cardinality(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run probabilistic-filters-and-sketches bundle evaluation.")
    parser.add_argument("--bundle", required=True, help="Path to JSON input bundle.")
    args = parser.parse_args()
    cfg = load_default_grid_spec()
    indent = int(cfg["formatting"]["json_indent"])
    payload = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    print(json.dumps(run_bundle(payload), indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
