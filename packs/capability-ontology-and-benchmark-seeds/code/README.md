# capability-ontology-seeds

Zero-dependency Python 3.10+ standard-library package for polyhierarchical capability ontology graphs, typed AI tool, MCP server, feed and OSS release intelligence cards, bounded multi-generation seed digestion and multi-axis Pareto benchmark ranking.

## Modules

- `capability_ontology_seeds/grid_config.py`: `NodeParameter`, `ParameterBounds`, `NodeGrid`, `GridLedger`, `OperationCostLedger`, `ZeroHardcodedValuesAstGate` and `DomainAgnosticNamingGate` backed by `config/ontology_seed_grid.json`.
- `capability_ontology_seeds/ontology_engine.py`: `CapabilityNode`, polyhierarchical `parent_ids` DAG validation, cycle detection, multi-parent facet projection and shingle Jaccard deduplication.
- `capability_ontology_seeds/intelligence_cards.py`: `ToolProfile`, typed schema checks, canonical I/O-port signature hashing and OSS release diffing.
- `capability_ontology_seeds/seed_bloom_planner.py`: `VerbEnvelope` and 1-hop (`generation_depth + 1`) seed digestion producing `/q/submit`-compatible `task_objects` and `queued_verbs`.
- `capability_ontology_seeds/pareto_benchmark.py`: `EvaluationRecord`, multi-objective Pareto frontier dominance, contextual regime rubric scoring and deterministic demo walkthrough synthesis.

## Run tests

```bash
make check
python3 -m capability_ontology_seeds --self-test
```

License: MIT.
