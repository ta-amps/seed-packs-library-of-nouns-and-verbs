"""Speaking WPM pacing, WebVTT caption-pause alignment, and ASR Character Error Rate (CER) gating."""

from __future__ import annotations

import re
from typing import Any, Sequence

WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['\-][A-Za-z0-9]+)*")
TS_RE = re.compile(r"((?:\d+:)?\d{1,2}:\d{2}[.,]\d{3})\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d{3})")


def _parse_ts(raw: str) -> float:
    parts = raw.replace(",", ".").split(":")
    sec = float(parts[-1])
    if len(parts) >= 2:
        sec += 60.0 * int(parts[-2])
    if len(parts) == 3:
        sec += 3600.0 * int(parts[-3])
    return sec


def parse_webvtt(vtt_text: str) -> list[dict[str, Any]]:
    """Parse WebVTT cues into `{id, start_s, end_s, lines, text, words}` dicts."""
    clean = vtt_text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", clean)
    cues: list[dict[str, Any]] = []
    auto_id = 0
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines or lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        ts_idx = next((i for i, ln in enumerate(lines) if TS_RE.search(ln)), None)
        if ts_idx is None:
            continue
        m = TS_RE.search(lines[ts_idx])
        assert m is not None
        auto_id += 1
        cue_id = lines[ts_idx - 1] if ts_idx > 0 else f"cue-{auto_id:03d}"
        start_s = _parse_ts(m.group(1))
        end_s = _parse_ts(m.group(2))
        body_lines = [re.sub(r"<[^>]+>", "", ln).strip() for ln in lines[ts_idx + 1 :] if ln.strip()]
        joined = " ".join(body_lines)
        words = WORD_RE.findall(joined)
        cues.append({
            "id": cue_id,
            "start_s": round(start_s, 3),
            "end_s": round(end_s, 3),
            "duration_s": round(end_s - start_s, 3),
            "lines": body_lines,
            "text": joined,
            "word_count": len(words),
        })
    return cues


def evaluate_wpm_and_caption_alignment(
    cues: Sequence[dict[str, Any]],
    speech_phrases: Sequence[tuple[float, float]],
    duration_s: float,
    *,
    target_wpm: tuple[float, float] = (140.0, 165.0),
    flag_wpm: tuple[float, float] = (110.0, 180.0),
    min_words_for_cue_wpm: int = 5,
    window_s: float = 10.0,
    max_start_err_s: float = 0.25,
    max_end_err_s: float = 0.50,
    min_voice_coverage: float = 0.95,
) -> dict[str, Any]:
    """Evaluate speaking WPM, 10 s sliding-window WPM stretches, and WebVTT caption-pause alignment."""
    phrases = sorted(speech_phrases, key=lambda p: p[0])
    total_words = sum(int(c["word_count"]) for c in cues)
    voiced_s = sum(max(0.0, e - s) for s, e in phrases)
    speaking_span_s = (phrases[-1][1] - phrases[0][0]) if phrases else duration_s

    speaking_wpm = round(total_words / max(speaking_span_s, 0.05) * 60.0, 1) if total_words else 0.0
    articulation_wpm = round(total_words / max(voiced_s, 0.05) * 60.0, 1) if total_words else 0.0

    cue_metrics: list[dict[str, Any]] = []
    word_times: list[float] = []
    findings: list[dict[str, Any]] = []

    for idx, c in enumerate(cues):
        cs, ce = float(c["start_s"]), float(c["end_s"])
        dur = max(0.01, ce - cs)
        wc = int(c["word_count"])
        overlapping = [(max(s, cs - 0.3), min(e, ce + 0.3)) for s, e in phrases if e > cs - 0.3 and s < ce + 0.3]

        for w_i in range(wc):
            frac = (w_i + 0.5) / max(1, wc)
            word_times.append(cs + dur * frac)

        start_err = None
        end_err = None
        wpm_line = round(wc / dur * 60.0, 1)
        if overlapping:
            on = overlapping[0][0]
            off = overlapping[-1][1]
            nxt = next((s for s, _ in phrases if s >= off - 0.01), duration_s)
            pause_after = min(max(0.0, nxt - off), 1.0)
            wpm_line = round(wc / max(off - on + pause_after, 0.05) * 60.0, 1)

            near_onsets = [s for s, _ in phrases if abs(s - cs) <= 1.5]
            if near_onsets:
                nearest_on = min(near_onsets, key=lambda s: abs(s - cs))
                # Ignore chained cues split mid-phrase
                if not any(s < cs - 0.15 and e > cs + 0.15 for s, e in phrases):
                    start_err = round(cs - nearest_on, 3)

            near_offsets = [e for _, e in phrases if abs(e - ce) <= 1.5]
            if near_offsets:
                nearest_off = min(near_offsets, key=lambda e: abs(e - ce))
                if not any(s < ce - 0.15 and e > ce + 0.15 for s, e in phrases):
                    end_err = round(ce - nearest_off, 3)

        if start_err is not None and abs(start_err) > max_start_err_s:
            findings.append({
                "id": f"caption-start-sync-{c['id']}",
                "severity": "minor",
                "cue": c["id"],
                "start_err_s": start_err,
                "limit_s": max_start_err_s,
            })
        if end_err is not None and abs(end_err) > max_end_err_s:
            findings.append({
                "id": f"caption-end-bleed-into-pause-{c['id']}",
                "severity": "major" if end_err > 1.0 else "minor",
                "cue": c["id"],
                "end_err_s": end_err,
                "limit_s": max_end_err_s,
            })
        if wc >= min_words_for_cue_wpm and (wpm_line < flag_wpm[0] or wpm_line > flag_wpm[1]):
            findings.append({
                "id": f"cue-wpm-pacing-{c['id']}",
                "severity": "minor",
                "cue": c["id"],
                "wpm_line": wpm_line,
                "flag_band": list(flag_wpm),
            })

        cue_metrics.append({
            "id": c["id"],
            "start_s": cs,
            "end_s": ce,
            "word_count": wc,
            "wpm_line": wpm_line,
            "start_err_s": start_err,
            "end_err_s": end_err,
        })

    # Voice frame coverage at 10 ms resolution
    n_fr = max(1, int(round(duration_s / 0.01)))
    voiced_mask = [False] * n_fr
    covered_mask = [False] * n_fr
    for s, e in phrases:
        for f in range(max(0, int(s / 0.01)), min(n_fr, int(e / 0.01))):
            voiced_mask[f] = True
    for c in cues:
        for f in range(max(0, int(float(c["start_s"]) / 0.01)), min(n_fr, int(float(c["end_s"]) / 0.01))):
            covered_mask[f] = True
    voiced_frames = sum(1 for v in voiced_mask if v)
    covered_voiced = sum(1 for v, cov in zip(voiced_mask, covered_mask) if v and cov)
    coverage = round(covered_voiced / max(1, voiced_frames), 4) if voiced_frames else 1.0
    if coverage < min_voice_coverage:
        findings.append({
            "id": "caption-voice-coverage",
            "severity": "major",
            "coverage": coverage,
            "min_coverage": min_voice_coverage,
        })

    # Sliding windows for WPM pacing
    windows: list[dict[str, float]] = []
    if phrases and speaking_span_s >= window_s:
        c0 = phrases[0][0] + window_s / 2.0
        end_c = phrases[-1][1] - window_s / 2.0
        while c0 <= end_c + 1e-6:
            cnt = sum(1 for wt in word_times if (c0 - window_s / 2.0) <= wt < (c0 + window_s / 2.0))
            windows.append({"center_s": round(c0, 2), "wpm": round(cnt / window_s * 60.0, 1)})
            c0 += 1.0

    return {
        "total_words": total_words,
        "speaking_wpm": speaking_wpm,
        "articulation_wpm": articulation_wpm,
        "target_wpm": list(target_wpm),
        "flag_wpm": list(flag_wpm),
        "voice_coverage": coverage,
        "cues": cue_metrics,
        "windows": windows,
        "findings": findings,
    }


def _normalize_chars_for_cer(text: str) -> str:
    """Lowercase alphanumeric and single-space normalization for deterministic ASR CER."""
    folded = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    tokens = WORD_RE.findall(folded)
    return " ".join(tokens)


def levenshtein_distance(ref: str, hyp: str) -> int:
    """Space-efficient exact character Levenshtein edit distance."""
    if ref == hyp:
        return 0
    if not ref:
        return len(hyp)
    if not hyp:
        return len(ref)
    prev = list(range(len(hyp) + 1))
    for i, rc in enumerate(ref, start=1):
        curr = [i] + [0] * len(hyp)
        for j, hc in enumerate(hyp, start=1):
            cost = 0 if rc == hc else 1
            curr[j] = min(
                prev[j] + 1,       # deletion
                curr[j - 1] + 1,   # insertion
                prev[j - 1] + cost # substitution
            )
        prev = curr
    return prev[-1]


def evaluate_asr_cer_gate(
    reference_script: str,
    asr_transcript: str,
    *,
    pass_max_cer: float = 0.02,
    minor_max_cer: float = 0.05,
) -> dict[str, Any]:
    """Gate synthesized or recorded narration against its script using Character Error Rate (CER)."""
    norm_ref = _normalize_chars_for_cer(reference_script)
    norm_hyp = _normalize_chars_for_cer(asr_transcript)
    if not norm_ref:
        raise ValueError("reference_script must contain at least one alphanumeric token")

    dist = levenshtein_distance(norm_ref, norm_hyp)
    cer = round(dist / len(norm_ref), 4)
    if cer <= pass_max_cer:
        verdict = "pass"
        severity = "none"
    elif cer <= minor_max_cer:
        verdict = "warn"
        severity = "minor"
    else:
        verdict = "fail"
        severity = "major"

    return {
        "reference_chars": len(norm_ref),
        "hypothesis_chars": len(norm_hyp),
        "edit_distance": dist,
        "cer": cer,
        "pass_max_cer": pass_max_cer,
        "minor_max_cer": minor_max_cer,
        "verdict": verdict,
        "severity": severity,
    }
