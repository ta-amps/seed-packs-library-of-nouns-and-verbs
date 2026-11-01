"""The request page's view model, built only from events (events_v1.json).

reduce(events, voice)      -> what the page shows: progress strip, status pill, the four bands, story, library
replay_schedule(events)    -> how long each event holds during Replay (reading speed, never faster)
from_snapshot(payload)     -> events derived from today's GET /api/requests/:id snapshot (until /events exists)
validate(events)           -> problems with an event list (order, types, receipts)
"""
import json
import pathlib
import re

CONTRACT = json.loads(pathlib.Path(__file__).with_name("events_v1.json").read_text(encoding="utf-8"))
TYPES = set(CONTRACT["envelope"]["properties"]["type"]["enum"])
COPY = CONTRACT["plain_copy"]
GRID = CONTRACT["ui_grid"]
STRIP = list(GRID["strip"])
BAND_OF = dict(GRID["band_of"])
SHA = re.compile(r"^[0-9a-f]{64}$")


def _ordinal(n):
    mod_h = GRID["ordinal_mod_hundred"]
    mod_t = GRID["ordinal_mod_ten"]
    in_teens = GRID["ordinal_teen_min"] <= n % mod_h <= GRID["ordinal_teen_max"]
    suffix = "th" if in_teens else GRID["ordinal_suffixes"].get(str(n % mod_t), "th")
    return f"{n}{suffix}"


def plain_line(ev, voice="you"):
    """The one plain sentence for an event, in the requester's ('you') or the public voice."""
    t, d = ev["type"], ev.get("data") or {}
    key = t
    kind = (ev.get("actor") or {}).get("kind")
    if t == "part.queued" and d.get("fallback_at"):
        key = "part.queued.fallback"
    elif t == "part.queued" and d.get("volunteers_online") == 0:
        key = "part.queued.no_volunteers"
    elif t in ("part.claimed", "review.claimed") and kind == "eranos_worker":
        key = t + ".eranos_worker"
    elif t == "review.verdict":
        key = "review.verdict." + ("sent_back" if d.get("verdict") == "sent_back" else "approved")
    elif t == "person.decision":
        key = "person.decision." + ("changes" if d.get("decision") == "changes" else "use")
    if key not in COPY:
        return None
    text = COPY[key]["you" if voice == "you" else "public"]
    if not (ev.get("part_title") or d.get("part_title")):
        text = text.replace("“{part}”", "It" if text.startswith("“{part}”") else "it")
    if not (d.get("object") or {}).get("title"):
        text = text.replace("“{object}”", "It" if text.startswith("“{object}”") else "it")
    parts = d.get("parts") or []
    return text.format(
        n=len(parts) or d.get("n", ""),
        n_parts=f"{len(parts)} part" + ("" if len(parts) == 1 else "s"),
        ordinal=_ordinal(int(d.get("position", 1) or 1)),
        part=ev.get("part_title") or d.get("part_title") or "it",
        object=(d.get("object") or {}).get("title", "it"),
        passed=(d.get("checks") or {}).get("passed", ""),
        fallback=d.get("fallback_label") or _clock(d.get("fallback_at")),
    )


def _clock(iso):
    """'2026-11-01T18:30:00Z' -> '6:30 PM' (UTC; the page formats in the viewer's own time zone)."""
    m = re.search(r"T(\d\d):(\d\d)", iso or "")
    if not m:
        return ""
    half_day = GRID["clock_half_day_hours"]
    h, mi = int(m.group(1)), m.group(1 + 1)
    return f"{h % half_day or half_day}:{mi} {'AM' if h < half_day else 'PM'}"


def reduce(events, voice="you"):
    seen = {}
    for ev in events:
        seen.setdefault(ev["type"], []).append(ev)
    has = lambda t: t in seen  # noqa: E731
    last = lambda t: seen[t][-1] if t in seen else None  # noqa: E731
    verdict = (last("review.verdict") or {}).get("data", {}).get("verdict")
    decision = (last("person.decision") or {}).get("data", {}).get("decision")
    claimed = has("part.claimed") and (not has("part.released") or last("part.claimed")["seq"] > last("part.released")["seq"])
    queued_only = has("part.queued") and not claimed and not has("part.submitted")
    qdata = (last("part.queued") or {}).get("data") or {}
    nobody = queued_only and qdata.get("volunteers_online") == 0 and not qdata.get("fallback_at")

    if has("library.added"):
        step, pill = GRID["step_library_added"], ("In the shared library", "good")
    elif has("request.ready"):
        ready_label = (
            "Changes asked"
            if decision == "changes"
            else ("Decided: use it" if decision == "use" else ("Ready for your team" if voice == "you" else "Ready for the nonprofit"))
        )
        step, pill = GRID["step_request_ready"], (ready_label, "your-turn")
    elif verdict == "sent_back":
        step, pill = GRID["step_review"], ("Sent back for fixes", "your-turn")
    elif has("review.claimed"):
        step, pill = GRID["step_review"], ("Being checked", "working")
    elif has("part.submitted"):
        step, pill = GRID["step_review"], ("Made · waiting for a check", "waiting")
    elif claimed:
        step, pill = GRID["step_build"], ("Being made", "working")
    elif has("part.queued"):
        step, pill = GRID["step_build"], ("Waiting · no volunteer online" if nobody else "Waiting for a volunteer", "waiting")
    else:
        step, pill = GRID["step_sorted"], ("Being sorted", "waiting")

    ready_idx = GRID["track_ready_index"]
    lib_idx = GRID["track_library_index"]
    track = []
    for i, label in enumerate(STRIP):
        if i == ready_idx and voice == "you":
            label = "Ready for you"
        done = i < step or (i == lib_idx and has("library.added"))
        track.append({"label": label, "state": "done" if done else ("current" if i == step and not has("library.added") else "future")})

    lanes = {}
    for p in (last("request.split") or {}).get("data", {}).get("parts", []):
        lanes.setdefault(p.get("lane", "own_files"), []).append(p.get("title", ""))
    bands = {
        "step-split": {"done": has("request.split"), "lanes": lanes},
        "step-build": {"done": has("part.submitted"), "working": claimed and not has("part.submitted"),
                       "waiting": queued_only, "nobody_online": nobody,
                       "objects_made": [e["data"]["object"]["title"] for e in seen.get("part.object_made", [])],
                       "fallback_at": qdata.get("fallback_at") if queued_only else None,
                       "maker_kind": ((last("part.claimed") or {}).get("actor") or {}).get("kind")},
        "step-review": {"done": verdict == "approved", "working": has("review.claimed") and verdict is None,
                        "refusal": has("review.refused"), "verdict": verdict,
                        "checks": (last("review.verdict") or {}).get("data", {}).get("checks"),
                        "checker_kind": ((last("review.claimed") or {}).get("actor") or {}).get("kind")},
        "step-ready": {"ready": has("request.ready"), "decision": decision, "signoff": has("person.signoff"),
                       "deliverables": (last("request.ready") or {}).get("data", {}).get("deliverables", [])},
    }
    lib = last("library.added")
    library = {"added": bool(lib), "task_objects": len((lib or {}).get("data", {}).get("task_objects", [])),
               "tasks": len((lib or {}).get("data", {}).get("tasks", []))}
    story = [{"seq": e["seq"], "at": e.get("at"), "text": plain_line(e, voice)} for e in reversed(events) if e["type"] != "part.heartbeat"]
    story = [s for s in story if s["text"]]
    return {"step": step, "track": track, "pill": {"label": pill[0], "tone": pill[1]}, "bands": bands,
            "library": library, "story": story, "live": story[0]["text"] if story else ""}


def replay_schedule(events, voice="you"):
    """(index, hold seconds, band changed) per event. Hold = max(2.0, 0.5 + words/3.0); +1.0 s when the band changes."""
    out, prev_band = [], None
    min_hold = GRID["replay_min_hold_s"]
    base_s = GRID["replay_base_s"]
    wps = GRID["replay_words_per_s"]
    bonus_s = GRID["replay_band_change_bonus_s"]
    digits = GRID["replay_round_digits"]
    for i, ev in enumerate(events):
        if ev["type"] == "part.heartbeat":
            continue
        line = plain_line(ev, voice) or ""
        hold = max(min_hold, base_s + len(line.split()) / wps)
        band = BAND_OF[ev["type"]]
        changed = prev_band is not None and band != prev_band
        out.append({"index": i, "hold_s": round(hold + (bonus_s if changed else 0.0), digits), "band": band, "band_changed": changed})
        prev_band = band
    return out


def from_snapshot(snap):
    """Events derived from the current /api/requests/:id payload. Times are the receipt times when present;
    the snapshot has none yet, so only the first event carries a time."""
    ev, seq = [], 0
    sec_per_min = GRID["seconds_per_minute"]

    def add(t, data=None, actor=None, receipt=None, at=None):
        nonlocal seq
        seq += 1
        e = {"seq": seq, "type": t, "request_id": snap["request_id"], "data": data or {}}
        if at:
            e["at"] = at
        if actor:
            e["actor"] = actor
        if receipt:
            e["receipt"] = {"sha256": receipt}
        ev.append(e)

    add("request.received", {"plain_need": snap.get("plain_need"), "example_request": bool(snap.get("example_request"))}, at=snap.get("submitted_at"))
    sp = snap.get("split") or {}
    parts = [{"title": t, "lane": "own_files"} for t in (sp.get("private_lane") or {}).get("items", [])]
    parts += [{"title": t, "lane": "public_info"} for t in (sp.get("public_lane") or {}).get("items", [])]
    add("request.split", {"parts": parts}, actor={"role": "planner"}, receipt=sp.get("receipt"))
    qb = snap.get("queue_build") or {}
    if qb.get("claim_receipt"):
        add("part.claimed", {"lease": {"seconds": qb.get("lease_seconds") or sec_per_min * (qb.get("lease_minutes") or 0), "fencing_token": qb.get("fencing_token")}},
            actor={"role": "maker", "worker_id": qb.get("worker_id"), "harness": qb.get("harness")}, receipt=qb.get("claim_receipt"))
    if qb.get("build_receipt"):
        add("part.submitted", {"reused": qb.get("reused_pieces", [])}, actor={"role": "maker", "worker_id": qb.get("worker_id")}, receipt=qb.get("build_receipt"))
    ir = snap.get("independent_review") or {}
    ref = ir.get("self_approval_refusal")
    if ref:
        add("review.refused", {"rule": "maker_cannot_check", "http_status": ref.get("http_status")}, actor={"role": "maker", "worker_id": ref.get("actor")}, receipt=ref.get("receipt"))
    ap = ir.get("reviewer_approval")
    if ap:
        add("review.claimed", actor={"role": "checker", "worker_id": ap.get("actor"), "harness": ap.get("harness")})
        add("review.verdict", {"verdict": "approved", "checks": {"passed": ap.get("checks_passed"), "total": ap.get("checks_passed")}},
            actor={"role": "checker", "worker_id": ap.get("actor")}, receipt=ap.get("receipt"))
    sd = snap.get("steward_and_delivery") or {}
    if sd.get("steward_signed_off"):
        add("person.signoff", {"role": "steward", "note": sd.get("steward_note")}, actor={"role": "person"}, receipt=sd.get("steward_receipt"))
    if snap.get("status") == "delivered":
        deliv = []
        if sd.get("catalog_path"):
            deliv.append({"kind": "process", "title": snap.get("kit_title") or "Process", "url": sd["catalog_path"]})
        if sd.get("public_report_summary"):
            deliv.append({"kind": "information", "title": sd["public_report_summary"], "url": f"/requests/{snap['request_id']}/report"})
        add("request.ready", {"deliverables": deliv})
    return ev


def validate(events):
    problems, last_seq = [], 0
    for i, e in enumerate(events):
        if e.get("type") not in TYPES:
            problems.append((i, f"unknown type {e.get('type')!r}"))
        if not isinstance(e.get("seq"), int) or e["seq"] <= last_seq:
            problems.append((i, "seq must strictly increase"))
        last_seq = e.get("seq", last_seq) if isinstance(e.get("seq"), int) else last_seq
        r = (e.get("receipt") or {}).get("sha256")
        if r is not None and not SHA.match(r):
            problems.append((i, "receipt.sha256 must be 64 lowercase hex characters"))
        if e.get("type") == "review.verdict" and (e.get("data") or {}).get("verdict") not in ("approved", "sent_back"):
            problems.append((i, "verdict must be approved or sent_back"))
    ids = {e.get("request_id") for e in events}
    if len(ids) > 1:
        problems.append((None, f"events mix request ids: {sorted(map(str, ids))}"))
    return problems
