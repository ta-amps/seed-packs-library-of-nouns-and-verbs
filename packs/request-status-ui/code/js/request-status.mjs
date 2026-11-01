// Eranos request page view model (port of request_status_ui/model.py). No dependencies, no browser storage.
// Usage in web/src: import { reduce, replaySchedule, fromSnapshot } from "./request-status.mjs";
// The plain copy comes from claude-design-request-status-events.v1.json -> plain_copy; pass it in as `copy`.

const STRIP = ["Sent", "Sorted", "Being made", "Being checked", "Ready", "In the library"];
const BAND_OF = {
  "request.received": 1, "request.split": 1, "part.queued": 2, "part.claimed": 2, "part.heartbeat": 2,
  "part.released": 2, "part.object_made": 2, "part.submitted": 2, "review.claimed": 3, "review.refused": 3,
  "review.verdict": 3, "person.signoff": 4, "request.ready": 4, "person.decision": 4, "library.added": 4,
};

const ordinal = (n) => n + ((n % 100 >= 10 && n % 100 <= 20) ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th"));

export function plainLine(ev, copy, voice = "you") {
  const t = ev.type, d = ev.data || {};
  let key = t;
  const kind = ev.actor && ev.actor.kind;
  if (t === "part.queued" && d.fallback_at) key = "part.queued.fallback";
  else if (t === "part.queued" && d.volunteers_online === 0) key = "part.queued.no_volunteers";
  else if ((t === "part.claimed" || t === "review.claimed") && kind === "eranos_worker") key = t + ".eranos_worker";
  else if (t === "review.verdict") key = "review.verdict." + (d.verdict === "sent_back" ? "sent_back" : "approved");
  else if (t === "person.decision") key = "person.decision." + (d.decision === "changes" ? "changes" : "use");
  if (!copy[key]) return null;
  let text = copy[key][voice === "you" ? "you" : "public"];
  if (!(ev.part_title || d.part_title)) text = text.replace("“{part}”", text.startsWith("“{part}”") ? "It" : "it");
  if (!(d.object && d.object.title)) text = text.replace("“{object}”", text.startsWith("“{object}”") ? "It" : "it");
  const parts = d.parts || [];
  return text
    .replace("{n_parts}", `${parts.length} part${parts.length === 1 ? "" : "s"}`)
    .replace("{n}", String(parts.length || d.n || ""))
    .replace("{ordinal}", ordinal(Number(d.position || 1)))
    .replace("{part}", ev.part_title || d.part_title || "it")
    .replace("{object}", (d.object && d.object.title) || "it")
    .replace("{passed}", String((d.checks && d.checks.passed) ?? ""))
    .replace("{fallback}", d.fallback_label || clock(d.fallback_at));
}

// '2026-11-01T18:30:00Z' -> '6:30 PM' (UTC; the page formats in the viewer's own time zone).
function clock(iso) {
  const m = /T(\d\d):(\d\d)/.exec(iso || "");
  if (!m) return "";
  const h = Number(m[1]);
  return `${h % 12 || 12}:${m[2]} ${h < 12 ? "AM" : "PM"}`;
}

export function reduce(events, copy, voice = "you") {
  const seen = {};
  for (const ev of events) (seen[ev.type] = seen[ev.type] || []).push(ev);
  const has = (t) => !!seen[t];
  const last = (t) => (seen[t] ? seen[t][seen[t].length - 1] : null);
  const verdict = last("review.verdict")?.data?.verdict ?? null;
  const decision = last("person.decision")?.data?.decision ?? null;
  const claimed = has("part.claimed") && (!has("part.released") || last("part.claimed").seq > last("part.released").seq);
  const queuedOnly = has("part.queued") && !claimed && !has("part.submitted");
  const qdata = last("part.queued")?.data || {};
  const nobody = queuedOnly && qdata.volunteers_online === 0 && !qdata.fallback_at;
  let step, pill;
  if (has("library.added")) [step, pill] = [6, ["In the shared library", "good"]];
  else if (has("request.ready")) [step, pill] = [4, [decision === "changes" ? "Changes asked" : decision === "use" ? "Decided: use it" : voice === "you" ? "Ready for your team" : "Ready for the nonprofit", "your-turn"]];
  else if (verdict === "sent_back") [step, pill] = [3, ["Sent back for fixes", "your-turn"]];
  else if (has("review.claimed")) [step, pill] = [3, ["Being checked", "working"]];
  else if (has("part.submitted")) [step, pill] = [3, ["Made · waiting for a check", "waiting"]];
  else if (claimed) [step, pill] = [2, ["Being made", "working"]];
  else if (has("part.queued")) [step, pill] = [2, [nobody ? "Waiting · no volunteer online" : "Waiting for a volunteer", "waiting"]];
  else [step, pill] = [1, ["Being sorted", "waiting"]];
  const track = STRIP.map((label0, i) => {
    const label = i === 4 && voice === "you" ? "Ready for you" : label0;
    const done = i < step || (i === 5 && has("library.added"));
    return { label, state: done ? "done" : i === step && !has("library.added") ? "current" : "future" };
  });
  const lanes = {};
  for (const p of last("request.split")?.data?.parts || []) (lanes[p.lane || "own_files"] = lanes[p.lane || "own_files"] || []).push(p.title || "");
  const lib = last("library.added");
  const story = events.slice().reverse().filter((e) => e.type !== "part.heartbeat")
    .map((e) => ({ seq: e.seq, at: e.at ?? null, text: plainLine(e, copy, voice) })).filter((s) => s.text);
  return {
    step, track, pill: { label: pill[0], tone: pill[1] },
    bands: {
      "step-split": { done: has("request.split"), lanes },
      "step-build": { done: has("part.submitted"), working: claimed && !has("part.submitted"), waiting: queuedOnly, nobody_online: nobody,
        objects_made: (seen["part.object_made"] || []).map((e) => e.data.object.title),
        fallback_at: queuedOnly ? (qdata.fallback_at ?? null) : null, maker_kind: last("part.claimed")?.actor?.kind ?? null },
      "step-review": { done: verdict === "approved", working: has("review.claimed") && verdict === null, refusal: has("review.refused"), verdict,
        checks: last("review.verdict")?.data?.checks ?? null, checker_kind: last("review.claimed")?.actor?.kind ?? null },
      "step-ready": { ready: has("request.ready"), decision, signoff: has("person.signoff"), deliverables: last("request.ready")?.data?.deliverables || [] },
    },
    library: { added: !!lib, task_objects: (lib?.data?.task_objects || []).length, tasks: (lib?.data?.tasks || []).length },
    story, live: story.length ? story[0].text : "",
  };
}

export function replaySchedule(events, copy, voice = "you") {
  const out = [];
  let prev = null;
  events.forEach((ev, i) => {
    if (ev.type === "part.heartbeat") return;
    const line = plainLine(ev, copy, voice) || "";
    const words = line.split(/\s+/).filter(Boolean).length;
    const band = BAND_OF[ev.type];
    const changed = prev !== null && band !== prev;
    out.push({ index: i, hold_s: Math.round((Math.max(2.0, 0.5 + words / 3.0) + (changed ? 1.0 : 0.0)) * 100) / 100, band, band_changed: changed });
    prev = band;
  });
  return out;
}
