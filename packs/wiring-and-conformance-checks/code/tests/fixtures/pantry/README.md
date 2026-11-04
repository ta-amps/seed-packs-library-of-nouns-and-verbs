# Made-up pantry app

A made-up appointment app for a food pantry, used only as input to the wiring checks' tests and the
pack's worked examples. Its files are read with `ast`; nothing here is installed, imported or run.

- `src/pantry_app` is the package. `python -m pantry_app` would be its entry point.
- `tests` holds its tests, which the mock scan reads.
- `behaviors.json` maps four documented behaviors to their real paths and tests.

Planted on purpose: two dark modules, one module only tests reach, one reached only for type
checking, two reachable only through a computed import name, three probes that are hollow on their
face and one (`readyz`) that calls the store but ignores its answer, two behaviors whose only tests
patch their own path, a settings field (`reminder_hours`) that `save_config` writes but
`load_config` never reads back, and a loader that silently drops keys it does not know.
