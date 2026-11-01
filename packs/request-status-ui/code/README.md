# Request status UI code

Standard-library Python model (`request_status_ui/model.py`) and a dependency-free JavaScript port
(`js/request-status.mjs`) for a request status page (`/requests/:id`). Both read only request-status events
(`request_status_ui/events_v1.json`) and resolve timing, ordinal and band settings from `ui_grid`.

- `reduce(events, voice)`: progress strip, status pill, the four bands (`step-split`, `step-build`, `step-review`,
  `step-ready`), the shared-library count of `task objects` and `tasks` (things to do), and the plain story in the
  requester's voice (`you`) or the public voice.
- `replay_schedule(events)`: hold times for Replay, never faster than `0.5 + words/3` seconds (`2.0 s` minimum), plus
  `1.0 s` when the band changes.
- `from_snapshot(payload)`: events derived from a `GET /api/requests/:id` snapshot payload.
- `validate(events)`: order, types, receipts and single-request-id invariants.
- `ZeroHardcodedValuesAstGate`: AST conformance gate checking zero magic literals across `request_status_ui/`.

Run `make check` (Python compile, unit tests, AST gate and Node JS parity on the fixtures).
