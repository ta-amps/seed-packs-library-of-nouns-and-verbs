"""Unit tests for the 1,000-Scenario Matrix generator and stakeholder digester."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scenario_matrix import (
    ADDRESSABLE_TUPLES,
    COMPUTE_TIERS_6,
    DOMAINS_25,
    HARNESSES_5,
    STAKEHOLDER_POSITIONS_10,
    TOPOLOGIES_5,
    expand_combinatorial_slice,
    generate_environments_1000,
    generate_methods_1000,
    generate_personas_1000,
    generate_stakeholders_1000,
    resolve_tuple,
    resolve_tuple_by_global_index,
    run_latin_hypercube_sweep_1000,
    run_worked_example,
)


class ScenarioMatrixTests(unittest.TestCase):
    def test_1000_environments_cover_all_25_domains_10_constraints_4_regimes(self) -> None:
        envs = generate_environments_1000()
        self.assertEqual(len(envs), 1000)
        self.assertEqual(envs[0]["env_id"], "ENV-0001")
        self.assertEqual(envs[-1]["env_id"], "ENV-1000")
        self.assertEqual(len({e["env_sha256"] for e in envs}), 1000)
        self.assertEqual(len({e["domain_slug"] for e in envs}), len(DOMAINS_25))
        self.assertEqual(len({e["constraint_slug"] for e in envs}), 10)
        self.assertEqual(len({e["regime_slug"] for e in envs}), 4)
        for env in envs:
            self.assertIn("stay", env["human_only_boundary"])

    def test_llm_extender_hook_enriches_environment_deterministically(self) -> None:
        env = generate_environments_1000(
            llm_extender=lambda d: {"synthetic_vignette": f"Vignette for {d['env_id']}"}
        )[0]
        self.assertEqual(env["worker_llm_vignette"], "Vignette for ENV-0001")

    def test_1000_methods_cover_all_topologies_and_compute_tiers(self) -> None:
        meths = generate_methods_1000()
        self.assertEqual(len(meths), 1000)
        self.assertEqual(meths[0]["method_id"], "METH-0001")
        self.assertEqual(meths[-1]["method_id"], "METH-1000")
        self.assertEqual(len({m["method_sha256"] for m in meths}), 1000)
        self.assertEqual({m["topology"] for m in meths}, {t["slug"] for t in TOPOLOGIES_5})
        self.assertEqual({m["compute_tier"] for m in meths}, {c["slug"] for c in COMPUTE_TIERS_6})
        for meth in meths:
            self.assertEqual(meth["lifecycle"], "claim-do-report")

    def test_1000_personas_and_1000_stakeholders_are_distinct(self) -> None:
        pers = generate_personas_1000()
        stkhs = generate_stakeholders_1000()
        self.assertEqual(len(pers), 1000)
        self.assertEqual(len(stkhs), 1000)
        self.assertEqual({p["harness_preference"] for p in pers}, set(HARNESSES_5))
        self.assertEqual({s["position"] for s in stkhs}, {p["slug"] for p in STAKEHOLDER_POSITIONS_10})
        self.assertEqual(len({p["persona_sha256"] for p in pers}), 1000)
        self.assertEqual(len({s["stakeholder_sha256"] for s in stkhs}), 1000)

    def test_combinatorial_10_pow_12_addressing_and_stakeholder_blocking(self) -> None:
        self.assertEqual(ADDRESSABLE_TUPLES, 1_000_000_000_000)
        first = resolve_tuple_by_global_index(0)
        last = resolve_tuple_by_global_index(ADDRESSABLE_TUPLES - 1)
        self.assertEqual(first["tuple"]["env_id"], "ENV-0001")
        self.assertEqual(last["tuple"]["env_id"], "ENV-1000")
        self.assertEqual(last["tuple"]["stakeholder_id"], "STKH-1000")

        # ENV-0001 is high-pii-offline-airgap; a cloud tier method must be blocked!
        cloud_meth = next(m for m in generate_methods_1000() if m["is_cloud_compute"])
        blocked = resolve_tuple("ENV-0001", cloud_meth["method_id"], "PERS-0001", "STKH-0208")
        self.assertEqual(blocked["verdict"], "blocked")
        self.assertIn("cloud_tier_cannot_run_in_offline_airgap", blocked["block_reasons"])

        sub_slice = expand_combinatorial_slice([0, 1], [0, 1], [0], [0])
        self.assertEqual(len(sub_slice), 4)

    def test_latin_hypercube_1000_sweep_covers_every_index_and_ranks_24_candidates(self) -> None:
        digest_a = run_latin_hypercube_sweep_1000(seed=20261031)
        digest_b = run_latin_hypercube_sweep_1000(seed=20261031)
        self.assertEqual(digest_a["artifact_sha256"], digest_b["artifact_sha256"])
        self.assertEqual(digest_a["mode"], "local_verified")
        cov = digest_a["axis_coverage"]
        self.assertEqual(cov["environments_unique"], 1000)
        self.assertEqual(cov["methods_unique"], 1000)
        self.assertEqual(cov["personas_unique"], 1000)
        self.assertEqual(cov["stakeholders_unique"], 1000)
        self.assertEqual(len(digest_a["domain_breakdown"]), 25)
        self.assertEqual(len(digest_a["stakeholder_breakdown"]), 10)
        self.assertEqual(len(digest_a["top_24_digested_candidates"]), 24)
        metrics = digest_a["aggregate_metrics"]
        self.assertEqual(
            metrics["approved_direct_count"] + metrics["approved_partitioned_count"] + metrics["blocked_count"],
            1000,
        )
        self.assertGreater(metrics["blocked_count"], 0)
        self.assertGreater(metrics["approved_partitioned_count"], 0)
        self.assertGreater(metrics["approved_direct_count"], 0)

    def test_source_json_worked_example_recomputes_identically(self) -> None:
        source_path = Path(__file__).resolve().parents[2] / "source.json"
        if not source_path.exists():
            return
        source = json.loads(source_path.read_text(encoding="utf-8"))
        nouns = {n["slug"]: n["value"] for n in source["nouns"]}
        bundle = nouns["example.matrix-episode-bundle"]
        expected = nouns["example.matrix-digest"]["instance"]
        self.assertEqual(run_worked_example(bundle), expected)


if __name__ == "__main__":
    unittest.main()
