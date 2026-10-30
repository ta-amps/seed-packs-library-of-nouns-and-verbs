# Code composition: tested code

The tested code of the [code-composition seed pack](../README.md), kept in the pack as nouns. The pack's tool card pins this folder by the digest that the pack manifest lists, and its runtime, node and recipe nouns pin module, node source, recipe and run digests; `tests/test_pack_pins.py` checks those pins against this code. The library never runs this code except in its CI tests. A worker runs it under its own permissions, from a checkout whose files match those digests. Importing the pack runs nothing.

## Run the checks

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
cd packs/code-composition/code
make setup
make check   # ruff lint and format check, mypy strict, pytest
make demo    # 18 nodes, 3 recipes, Python equivalence and cached prefix reuse
make tessera-integration TESSERA_DIR=<Tessera checkout at the commit the tool card names>
```

The two Tessera tests skip without a Tessera environment; `make tessera-integration` runs them with `CODE_COMPOSITION_REQUIRE_TESSERA=1`, so a missing Tessera fails instead of skipping. The pack pin tests skip outside the library; CI sets `CODE_COMPOSITION_REQUIRE_PACK=1`, so a missing `nouns.json` fails instead.

## What is here

- `code_composition/`: the package: 18 prewritten nodes, the SQLite node database, the compiler, the runtime, the optional composer, the `code-composition` command, the offline seed export and the worker-side pin check.
- `tests/`: its tests.
- `examples/recipes/`: the three authored recipes, which the wheel ships as package data.
- `pyproject.toml` and `uv.lock`: the package and its locked environment.
