# Edge case generator

A deterministic, seeded generator of labelled edge cases that the edge and corner cases pack's verbs
run inside a claimed verb. Python 3.10 or later, standard library only.

- `strings`: empty and whitespace values, sizes around a length limit, combining marks, right-to-left
  text, direction overrides, emoji sequences, zero-width characters, lookalikes, case mappings that
  change length, control characters and markup-shaped text.
- `numbers`: a field's limits and one step past them, integer and floating-point edges, NaN and
  Infinity, and other locales' and scripts' ways of writing a number, all as the text a person sends.
- `dates`: leap days, month ends, ISO week 53, daylight saving gaps and overlaps in New York, London
  and on Lord Howe Island by the rules in force since 2008 (earlier years are refused), unusual
  offsets, leap seconds, epoch edges, far years and ambiguous forms.
- `lists`: sizes around a page, duplicates in disguise, orders that trip sorting and odd items.
- `bodies`: JSON request bodies with broken syntax, valid syntax a schema must refuse, sizes past a
  limit and the wrong content type.

```bash
make check                                                     # compile, then every test
python -m edge_cases generate --kind strings --seed 20261030 --max-length 64
python -m edge_cases generate --kind numbers --kind dates --seed 7 --minimum 1 --maximum 6 --summary
python -m edge_cases labels --kind dates                      # what each label tests
```

Every case has an id, a label, its value and context, an ASCII-only escaped form that any JSON
parser turns back into the value, its sizes in code points, UTF-8 bytes and UTF-16 units, and a
SHA-256 of its kind, label, value and context. One digest covers the whole set. Seeded cases come
from a SplitMix64 stream per kind, pinned to published test vectors, so a seed gives the same cases
on every Python version and asking for fewer kinds never changes the others.

The tests check every label's claim with the standard library's Unicode data and `datetime`, the
daylight saving rules against the time zone database for ten years (CI sets
`EDGE_CASES_REQUIRE_TZDATA=1` so a missing database fails), determinism across processes and hash
seeds, and recompute the pack's case set and label nouns from [source.json](../source.json). Nothing
here sends a request, opens a network connection, calls a model or writes a file. MIT license,
written for this pack by ta-amps.
