# Partner compute telemetry cards code

Standard-library Python package for the `partner-compute-telemetry-cards` seed pack.

- `cards_from_cascade(record)`: one card per provider from a `partner_compute_cascade.json` record. A card is
  `live_run` only when the record says `mode: live_measured` with credentials present; otherwise `offline_check`.
- `validate(card)`: every card has a 64-hex receipt; a live run needs `measured_at`, the provider's request ids and
  its measured values; an offline check carries no cost, throughput, latency or accuracy fields; no credit amounts,
  logos or stamp words.
- `render_html(card)`: escaped HTML with classes only (Eranos and Agora use `style-src 'self'`).

The fixture is the Oct 31 cascade record (all keys unset, so all three cards are offline checks). Run `make check`.

Without make (the Makefile could not be written to the shared folder remotely; copy it from any pack in the library):

```bash
python3 -W error -m compileall -q telemetry_cards tests
python3 -W error -m unittest discover -s tests -v
```
