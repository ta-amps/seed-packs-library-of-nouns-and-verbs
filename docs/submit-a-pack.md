# Submit a seed pack

This guide is for any agent or person who wants to add a seed pack to this library. A seed
pack is a collection of nouns (reusable things: knowledge, templates, tool cards, examples
and, optionally, tested code) and verbs (work an authorized worker can claim). A pack is
never a surface, a service or a scheduler, and reading or importing one runs nothing.

## 1. Generate the pack

1. Pick a plain-English id and title. The id is lowercase words joined by hyphens, such as
   `caption-translation`. The summary and the descriptor noun's title start with
   "A collection of nouns and verbs for ...". No product or surface names.
2. Start from the closest existing pack in [packs/](../packs/README.md) and copy its
   `source.json` and `README.md` into `packs/<id>/`. `source.json` is the only file you edit
   by hand: `pack_id`, `title`, `version`, `summary`, `nouns` and `verbs`, plus optional
   `dependencies`, `boundaries` and `moved_from`.
3. Write the nouns. Each has a `slug`, a registered `category`, a `role`, a `title` and a
   `value`. Templates carry a JSON `schema` that the outputs of your verbs must match. Link
   nouns with typed relations, and use `{"$pin": "<slug>"}` to pin one noun inside another.
4. Write the verbs. Each needs inputs (pins, slots and params), at least one deterministic
   acceptance check, the nouns it produces, a network mode and bounds. Every verb also keeps
   the `no_change`, `unknown` and `blocked` outcomes; the builder adds them.
5. Write the pack README: a title, then "What this pack lets workers do", "Nouns", "Verbs"
   and "Limits", in at most 90 lines. Say plainly what is real and what is not yet.
6. If the pack ships tested code, put it in `packs/<id>/code/` with its own project file,
   tests and Makefile. Point a tool card at it with `{"$code": "<id>"}`, and add a CI
   workflow with path filters for `packs/<id>/**` that runs the code's full tests. See
   [Adding code to a pack](../CONTRIBUTING.md#adding-code-to-a-pack).

## 2. Validate it locally

```bash
python3 scripts/build_packs.py          # writes nouns.json, verbs.json and manifest.json
make check                               # offline; needs only Python 3.10+ and Git
make check-tessera TESSERA_SRC=../tessera TESSERA_ARGS=--write
make check                               # again, with the new receipt
```

- `make check` rebuilds every pack byte for byte, validates it against a snapshot of
  Tessera's contract, recomputes worked examples and scans for secrets and private names.
- `make check-tessera` runs every noun and verb through Tessera's own models, using a
  Tessera checkout at the commit named in [VALIDATION.json](../packs/VALIDATION.json) with its
  `.venv` (run `uv sync --frozen` there). `--write` updates that receipt, which `make check`
  requires to cover every pack.
- Add your pack's row to the tables in [README.md](../README.md) and
  [packs/README.md](../packs/README.md), and update the totals there and in
  [status](status.md). `make check` fails until the numbers match the packs.
- If the pack has code, also run its own checks in `packs/<id>/code/`, with the flags that
  turn a missing tool into a failure instead of a skip.

## 3. Submit it as a pull request

1. Work on a branch, never on `main`. Commit with a plain message that says what the pack
   lets workers do. Leave out co-author and generated-by trailers.
2. Open a pull request. Say who the pack is for, list its nouns and verbs, which checks you
   ran and their results, where its content and code came from and under what license, and
   what is still unknown.
3. CI runs `make check`, and the code's own job when the pack has code. A reviewer reads the
   pack before it is merged.

Merging adds a proposal to the library. It does not install, import, admit or activate the
pack, and it publishes nothing. Those stay separate decisions with their own authority.

## What a pack must never do

- Contact people, publish, enqueue tasks or spend beyond a worker's own allowance.
- Add a scheduler, queue, importer, model caller, service or website, in data or in code.
- Carry credentials, private names, personal data, private notes or transcripts.
- Name a surface or product outside a descriptor's `provenance_notes` or `moved_from`.
