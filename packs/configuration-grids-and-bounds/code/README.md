# configuration-grids-and-bounds (`config_grids`)

Standard-library implementation of:
- `NodeParameter`, `ParameterBounds`, and `NodeGrid` (declarative multi-dimensional configuration grids with cross-parameter constraints and automatic boundary expansion when empirical optima saturate an axis ceiling/floor).
- `GridLedger` (`represented -> applicable -> proposed -> dispatched -> evaluated -> verified -> promoted`, refusing unverified or self-approved promotions) and `OperationCostLedger` (contextual workload-regime cell resolution).
- `ZeroHardcodedValuesAstGate` (mechanical Python `ast` scanner rejecting non-identity numeric magic literals inside operational functions/classes).

Run checks:
```bash
make check
```
