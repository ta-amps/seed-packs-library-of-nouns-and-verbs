"""Shot-list checks and a capture plan for website-first film recording (film-frame v6).

check_storyboard(sb)  -> problems in a storyboard (shape of claude-design storyboard.json v3)
capture_plan(sb, cut) -> one recorder step per footage shot: take ids, URL, window, anchor, actions
"""
import hashlib
import json
import pathlib
import re

FRAME = json.loads(pathlib.Path(__file__).with_name("frame_v6.json").read_text(encoding="utf-8"))
P = FRAME["pacing"]
FOOT = FRAME["footage"]
GRID = FRAME["checker_grid"]
READING_BASE_S = GRID["reading_base_s"]
READING_WORDS_PER_S = GRID["reading_words_per_s"]
SEAM_TOL_S = GRID["seam_tol_s"]
FLOAT_TOL_S = GRID["float_tol_s"]
ROUND_DIGITS = GRID["duration_round_digits"]
RETIRED_SHA256 = frozenset(GRID["retired_name_sha256"])

ALLOWED_HOSTS = ("eranos.ta-amps.workers.dev", "agora.ta-amps.workers.dev")
ER03_ANCHORS = {"#step-split", "#step-build", "#step-review", "#step-ready"}
STAMPS = ("PLANNED", "ILLUSTRATION", "SYNTHETIC EXAMPLE", "AI-GENERATED VOICE", "LOCAL RUN", "NOT YET", "COMING SOON", "NOT RUNNING", "SYNTHETIC DATA ONLY")
WORD_RE = re.compile(r"[a-z0-9]+")
COMPOUND_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")
# Tessera access contract: credentials never go in URLs (query or fragment).
CREDENTIAL_IN_URL = re.compile(r"[?&#](key|k|token|code|secret|auth|password)=", re.I)


def retired_name_in(text, hashes=RETIRED_SHA256):
    """True if text contains any retired name token or hyphenated compound matched by SHA-256."""
    low = text.lower()
    tokens = set(WORD_RE.findall(low)) | set(COMPOUND_RE.findall(low))
    return any(hashlib.sha256(tok.encode("utf-8")).hexdigest() in hashes for tok in tokens)


def reading_need(text):
    return READING_BASE_S + len(text.split()) / READING_WORDS_PER_S


def check_storyboard(sb, retired_hashes=RETIRED_SHA256):
    out = []
    for cut in sb.get("cuts", []):
        total = float(cut["duration"])
        prev_end = 0.0
        for s in cut["shots"]:
            sid = f"{cut['id']}:{s['id']}"
            d = s["end"] - s["start"]
            if abs(s["start"] - prev_end) > SEAM_TOL_S:
                out.append(("error", sid, f"starts at {s['start']} but the previous shot ends at {prev_end}"))
            prev_end = s["end"]
            if d < P["min_shot_s"] - FLOAT_TOL_S:
                out.append(("error", sid, f"{d:.2f} s is shorter than {P['min_shot_s']} s"))
            url = s.get("url") or ""
            if CREDENTIAL_IN_URL.search(url):
                out.append(("error", sid, f"credentials never go in URLs: {url!r}"))
            if s.get("source") == "footage":
                hosts = re.findall(r"https://([^/\s?#]+)", url)
                if not hosts or any(h not in ALLOWED_HOSTS for h in hosts):
                    out.append(("error", sid, f"footage must be on {', '.join(ALLOWED_HOSTS)}: {url!r}"))
                if not s.get("take_ids"):
                    out.append(("error", sid, "footage shot has no take_ids"))
                if s.get("screen_id", "") and s["screen_id"].startswith("ER-03") and s.get("anchor") not in ER03_ANCHORS:
                    out.append(("error", sid, f"request-page shot needs one of {sorted(ER03_ANCHORS)} as its anchor"))
            cam = s.get("camera") or {}
            if cam and (cam.get("scale", 1.0) != 1.0 or cam.get("drift_px", 0.0) != 0.0):
                out.append(("error", sid, "camera must stay at scale 1.000 with 0 px drift (no Ken Burns)"))
            if s.get("scroll_css_px_per_s", 0) > P["scroll_max_css_px_per_s"]:
                out.append(("error", sid, f"scroll faster than {P['scroll_max_css_px_per_s']} CSS px/s"))
            narrating = bool(s.get("cues"))
            for o in s.get("on_screen", []):
                text = o.get("text", "")
                if any(w in text.upper() for w in STAMPS):
                    out.append(("error", sid, f"stamp words in an overlay: {text!r}"))
                if o.get("must_read") and reading_need(text) > d + FLOAT_TOL_S:
                    out.append(("error", sid, f"'{text}' needs {reading_need(text):.1f} s on screen; the shot is {d:.1f} s"))
                if o.get("callout") and narrating and len(text.split()) > P["callout_max_words_while_narrating"]:
                    out.append(("error", sid, f"callout over {P['callout_max_words_while_narrating']} words while the voice speaks"))
            blob = json.dumps(s, ensure_ascii=False)
            if retired_name_in(blob, retired_hashes):
                out.append(("error", sid, "retired name in the shot"))
            if re.search(r"\bprov(e|es|en|ing)\b", blob, re.I):
                out.append(("error", sid, "lifecycle wording: use claim · do · report"))
        if abs(prev_end - total) > SEAM_TOL_S:
            out.append(("error", cut["id"], f"shots end at {prev_end}, the cut is {total} s"))
    return out


def capture_plan(sb, cut_id):
    cut = next(c for c in sb["cuts"] if c["id"] == cut_id)
    steps = []
    for s in cut["shots"]:
        if s.get("source") != "footage":
            continue
        steps.append({
            "shot": s["id"], "take_ids": s.get("take_ids", []), "url": s.get("url"), "anchor": s.get("anchor"),
            "window_css_px": FOOT["window_css_px"], "device_scale_factor": FOOT["device_scale_factor"],
            "min_seconds": round(s["end"] - s["start"], ROUND_DIGITS), "actions": s.get("action"),
            "rules": {"scroll_max_css_px_per_s": P["scroll_max_css_px_per_s"], "hold_after_scroll_s": P["hold_after_scroll_s"],
                      "pointer": P["pointer"], "camera_scale": P["camera_scale"]},
        })
    return steps
