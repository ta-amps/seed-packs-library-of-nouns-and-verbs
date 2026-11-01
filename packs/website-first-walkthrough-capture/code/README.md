# Website-first walkthrough capture code

Standard-library Python package for the `website-first-walkthrough-capture` seed pack. It reads the frame contract
(`walkthrough_capture/frame_v6.json`) and:

- `check_storyboard(sb)`: every shot at least 1.8 s and back to back; footage only on eranos/agora
  `.ta-amps.workers.dev`, with take ids; request-page shots anchored to `#step-split`, `#step-build`,
  `#step-review` or `#step-ready`; must-read text gets 0.5 + words/3 seconds; no stamp words in overlays;
  camera scale 1.000 with no drift; scrolls at most 800 CSS px/s; callouts of at most 8 words while the voice
  speaks; no retired names; lifecycle wording claim · do · report.
- `capture_plan(sb, cut)`: one recorder step per footage shot (take ids, URL, anchor, window 1280×613 CSS px at
  device scale 1.5, minimum seconds, actions and rules).

The fixture is Claude Design's storyboard v3. Run `make check`.

Without make (the Makefile could not be written to the shared folder remotely; copy it from any pack in the library):

```bash
python3 -W error -m compileall -q walkthrough_capture tests
python3 -W error -m unittest discover -s tests -v
```
