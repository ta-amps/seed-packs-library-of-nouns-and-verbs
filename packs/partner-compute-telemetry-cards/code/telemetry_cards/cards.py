"""Partner compute telemetry cards: one card per provider, honest by construction.

cards_from_cascade(record) -> cards from a partner_compute_cascade.json record
validate(card)             -> problems; a card may only show measured numbers when a live run produced them
render_html(card)          -> CSP-safe HTML (classes only, no inline styles), escaped
"""
import html
import json
import pathlib
import re

GRID = json.loads(pathlib.Path(__file__).with_name("card_grid.json").read_text(encoding="utf-8"))
RECEIPT_PREFIX_CHARS = GRID["receipt_prefix_chars"]
MODES = ("offline_check", "live_run")
NUMERIC_CLAIMS = ("cost", "usd", "throughput", "tpm", "tokens_per", "latency", "speedup", "accuracy", "score", "runs_per")
STAMPS = re.compile(r"\b(PLANNED|COMING SOON|NOT YET|ILLUSTRATION|NOT RUNNING)\b", re.I)
SHA = re.compile(r"^[0-9a-f]{64}$")

PROVIDERS = {
    "modal_qlora_and_sandbox": ("modal", "Modal", "Re-runs a seed pack's tests in an isolated sandbox, and fine-tunes Meta's open-weight models with QLoRA."),
    "baseten_2m_tpm_swarm": ("baseten", "Baseten", "Runs many workers at once on Meta's open-weight models, paced to stay under the account's tokens-a-minute limit."),
    "fireworks_multilora_shim": ("fireworks", "Fireworks AI", "Routes a task to a small specialist adapter behind Herma, with a different adapter as the checker."),
}


def _checked(key, rec):
    if key == "modal_qlora_and_sandbox":
        fits = all(c.get("fits_within_92pct_vram") for c in (rec.get("qlora_configs") or {}).values())
        out = ["Training settings fit the chosen GPUs' memory." if fits else "Some training settings do not fit the chosen GPUs' memory."]
        if (rec.get("sandbox_contract") or {}).get("contract_valid"):
            out.append("The sandbox contract is valid.")
        return out
    if key == "baseten_2m_tpm_swarm":
        out = []
        if rec.get("respected_2m_tpm_ceiling"):
            out.append("The pacing logic held a simulated burst under the limit.")
        if rec.get("retried_429_preserved_in_ledger"):
            out.append("Retried requests stay in the ledger with their receipts.")
        return out
    if key == "fireworks_multilora_shim":
        out = []
        if rec.get("shim_within_2ms"):
            out.append("The routing rule picked an adapter within Herma's 2 ms budget.")
        if rec.get("self_verification_blocked"):
            out.append("A worker checking its own output was blocked.")
        return out
    return []


def cards_from_cascade(record):
    cards = []
    for key, (pid, name, role) in PROVIDERS.items():
        rec = record.get(key)
        if not isinstance(rec, dict):
            continue
        live = rec.get("mode") == "live_measured" and rec.get("live_credentials_present") is True
        card = {
            "provider": pid, "name": name, "role": role,
            "mode": "live_run" if live else "offline_check",
            "checked": _checked(key, rec),
            "commands": list(rec.get("runnable_cloud_commands") or []),
            "receipt": {"sha256": rec.get("receipt_sha256") or record.get("artifact_sha256"), "kind": "cascade" if not rec.get("receipt_sha256") else "run"},
        }
        if live:
            card["measured"] = rec.get("measured") or {}
            card["measured_at"] = rec.get("measured_at")
            card["provider_request_ids"] = rec.get("provider_request_ids") or []
        cards.append(card)
    return cards


def validate(card):
    p = []
    if card.get("mode") not in MODES:
        p.append(f"mode must be one of {MODES}")
    r = (card.get("receipt") or {}).get("sha256")
    if not (isinstance(r, str) and SHA.match(r)):
        p.append("every card needs a 64-hex receipt")
    if card.get("mode") == "live_run":
        if not card.get("measured_at"):
            p.append("a live run needs measured_at")
        if not card.get("provider_request_ids"):
            p.append("a live run needs the provider's request ids")
        if not card.get("measured"):
            p.append("a live run needs its measured values")
    else:
        if card.get("measured"):
            p.append("an offline check cannot show measured values")
        for k in card:
            if any(n in k.lower() for n in NUMERIC_CLAIMS):
                p.append(f"an offline check cannot carry the claim field {k!r}")
    for k in ("credit_usd", "logo", "partner_since"):
        if k in card:
            p.append(f"field {k!r} is not allowed on a card")
    text = " ".join(str(v) for v in card.values() if isinstance(v, str)) + " " + " ".join(card.get("checked", []))
    if STAMPS.search(text):
        p.append("stamp words are not allowed; the status line says what ran")
    return p


def status_line(card):
    if card["mode"] == "live_run":
        return ("Last run: live", f"Ran on {card['name']} at {card.get('measured_at')}.")
    return ("Last check: offline", f"No {card['name']} account is connected yet, so nothing has run there. The code and its rules were checked on our machine.")


def render_html(card):
    e = html.escape
    title, text = status_line(card)
    items = "".join(f"<li>{e(x)}</li>" for x in card.get("checked", []))
    cmds = "".join(f'<pre class="pc-cmd"><code>{e(c)}</code></pre>' for c in card.get("commands", []))
    measured = ""
    if card["mode"] == "live_run":
        measured = "".join(f'<div class="pc-metric"><dt>{e(str(k))}</dt><dd>{e(str(v))}</dd></div>' for k, v in sorted(card.get("measured", {}).items()))
        measured = f'<dl class="pc-measured">{measured}</dl>'
    short_receipt = card["receipt"]["sha256"][:RECEIPT_PREFIX_CHARS]
    return (
        f'<article class="pc-card pc-{e(card["mode"])}" data-provider="{e(card["provider"])}">'
        f'<h3 class="pc-name">{e(card["name"])}</h3><p class="pc-role">{e(card["role"])}</p>'
        f'<p class="pc-status"><strong>{e(title)}</strong> {e(text)}</p>{measured}'
        f'<ul class="pc-checked">{items}</ul>{cmds}'
        f'<p class="pc-receipt">receipt {e(short_receipt)}…</p></article>'
    )
