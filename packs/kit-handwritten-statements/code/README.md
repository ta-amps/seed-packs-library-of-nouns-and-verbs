# Sample renderer for the handwritten statements kit

Renders the kit's synthetic handwritten pages from the pack's own test-cases noun
([source.json](../source.json)), so the sample text has one source. Each page is drawn on lined
paper with an openly licensed handwriting font (SIL Open Font License 1.1), fetched from a pinned
commit and checked by SHA-256, then stamped SYNTHETIC. Crossed-out words are struck through and one
word per page is smudged on purpose, so a transcription has to flag it.

```bash
make setup
make check                       # rebuilds every page and compares its pixel digest with the noun
make render OUT=/tmp/handwriting  # writes the PNG pages, only outside the library tree
```

The tests fetch the two fonts once into the user cache. Set `KIT_HANDWRITTEN_REQUIRE_FONTS=1` to turn
a missing font download into a failure instead of a skip, as CI does. Nothing here contacts a person,
calls a model, enqueues work or writes inside the library.
