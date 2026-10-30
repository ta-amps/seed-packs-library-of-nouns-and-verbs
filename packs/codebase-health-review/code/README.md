# Health checks

Two deterministic checks the codebase health review pack's verbs run inside a claimed verb. Python
3.10 or later, standard library only, with git for ages.

- `todos`: TODO, FIXME, XXX and HACK markers in comments, never in strings: Python through its
  tokenizer, other languages line by line with quote-aware comment detection, and HTML and Markdown
  inside comment blocks only. Each marker is aged by the author date `git blame --porcelain` gives
  its line, bucketed as fresh, aging, stale or ancient, and flagged when it names no owner, issue or
  link. Without history, for a line not committed yet, or in a shallow clone for lines blamed on the
  commit where the history is cut off, the age is unknown with the reason; a file's modification time
  is never used. Files that are not UTF-8 are listed as unreadable, never skipped silently.
- `swallowed`: Python exception handlers read with `ast`, never imported or run, classed as
  swallowed, suppress_broad, logged_only, fallback or narrow_ignored, with file, line range and
  enclosing function. A handler that raises in its own body, or does other work, is left alone, and
  a file that does not parse is listed, never skipped.

```bash
make check                                                  # compile, then every test
python -m health_checks todos . --as-of 2026-10-30 --fail-on ancient
python -m health_checks swallowed src --exclude "tests/*" --strict
```

`todos` exits 1 with `--fail-on` when a marker is in that bucket or older. `swallowed` exits 1 for a
swallowed handler or a broad suppress, and with `--strict` for logged-only, fallback and unparsed
files too. The tests build throwaway git repositories with fixed author dates, isolated from the
machine's git settings (CI sets `HEALTH_CHECKS_REQUIRE_GIT=1` so a missing git fails), check every
comment style and handler class, and recompute the pack's two scans from
[source.json](../source.json). The only programs started are read-only `git rev-parse` and
`git blame`. Nothing here opens a network connection, calls a model or writes a file. MIT license,
written for this pack by ta-amps.
