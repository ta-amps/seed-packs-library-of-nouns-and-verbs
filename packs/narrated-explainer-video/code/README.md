# Explainer checks

Deterministic checks the narrated explainer video pack's verbs run inside a claimed verb: the
frame clock of a cut plan, caption cues timed to a narration track with their WebVTT and SRT text,
release manifest rows and file checks, and the receipts ledger check. Python 3.10 or later,
standard library only. Times are whole milliseconds and frames, so results are exact.

```bash
make check                                    # compile, then every test
python -m explainer_checks clock --cut-plan PLAN.json --cut 20s --track TRACK.json
python -m explainer_checks captions --cut-plan PLAN.json --cut 20s --track TRACK.json --out /tmp/captions
```

The tests recompute the pack's worked example from [source.json](../source.json) and the voice
narration pack's placed lines, and check that the caption numbers match the video showcase style
guide. Nothing here renders, encodes, calls a model, opens a network connection or writes inside
the seed-pack library. MIT license, written for this pack by ta-amps.
