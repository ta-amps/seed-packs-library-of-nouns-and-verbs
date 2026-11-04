# Wiring checks

Deterministic checks the wiring and conformance checks pack's verbs run inside a claimed verb, for
Python code. Python 3.10 or later, standard library only. Every check reads source with `ast`;
nothing imports or runs the code it reads.

```bash
make check                                                     # compile, then every test
python -m wiring_checks modules src --tests tests --base .     # modules no live path imports
python -m wiring_checks mocks tests --behaviors behaviors.json # behaviors whose tests patch their path
python -m wiring_checks probes src --base .                    # health probes that probe nothing
```

`modules` walks the import graph from the entry points: those named with `--entry`, those a
`pyproject.toml` declares with `--pyproject`, or else every `__main__` module. It follows relative
imports, parent packages, `from x import n` submodules and string-literal `importlib` calls, keeps
`if TYPE_CHECKING:` imports apart, and gives each module one status: live, dynamic_candidate,
type_only, test_only or dark. A computed module name leaves the graph open, and the modules it
could load are candidates, not dark: static reading is a lead that a runtime import trace confirms.

`mocks` lists what every test patches, through `unittest.mock` in any of its forms or pytest's
`monkeypatch`, resolved through the test file's imports. Given a behavior map, it marks each
documented behavior real_path, mock_only or untested. A test that patches nothing on the path may
still not reach it; the scan catches replaced paths, not missing calls.

`probes` finds functions named or routed like health probes and marks each constant, flag_only or
calls. Constant and flag-only probes are hollow. A probe that calls something is a lead: stopping
the dependency and watching the probe fail is what shows it probes.

The tests cover every rule on small made-up packages and on the made-up pantry app in
`tests/fixtures/pantry`, and recompute the pack's three worked examples from
[source.json](../source.json). Nothing here opens a network connection, calls a model or writes a
file. MIT license, written for this pack by ta-amps.
