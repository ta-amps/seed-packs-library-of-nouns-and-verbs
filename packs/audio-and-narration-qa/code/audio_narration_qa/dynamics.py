"""Sidechain pause-pumping detection, hold-bridged duck envelopes, and edit-point click detection."""

from __future__ import annotations

import math
from typing import Any, Sequence

from .loudness import SR_DEFAULT, power_to_db, power_to_lufs


def _median(vals: Sequence[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    mid = len(s) // 2
    if len(s) % 2 == 1:
        return float(s[mid])
    return 0.5 * (float(s[mid - 1]) + float(s[mid]))


def detect_pause_pumping(
    music_kp_10ms: Sequence[float],
    speech_phrases: Sequence[tuple[float, float]],
    *,
    min_pause_s: float = 0.30,
    max_pause_s: float = 1.00,
    rise_threshold_db: float = 3.0,
    min_pumping_pauses: int = 2,
) -> dict[str, Any]:
    """Detect sidechain compressor release pumping during short inter-phrase pauses (0.3..1.0 s).

    Computes 100 ms moving music loudness (10 x 10 ms frames) and checks whether the music swells
    by `rise_threshold_db` or more inside short speech pauses compared with the 0.60 s speech
    window immediately preceding each pause.
    """
    n = len(music_kp_10ms)
    if n < 10 or len(speech_phrases) < 2:
        return {
            "pauses_checked": 0,
            "pauses_rising_over_threshold": 0,
            "median_rise_db": 0.0,
            "max_rise_db": 0.0,
            "events": [],
            "finding": None,
        }

    # 100 ms (10-frame) moving loudness in LUFS
    mm_100ms: list[float] = []
    acc = 0.0
    for i, v in enumerate(music_kp_10ms):
        acc += v
        if i >= 10:
            acc -= music_kp_10ms[i - 10]
        win = min(i + 1, 10)
        mm_100ms.append(power_to_lufs(acc / win))

    events: list[dict[str, Any]] = []
    rises: list[float] = []
    ordered = sorted(speech_phrases, key=lambda p: p[0])
    for (_, prev_end), (next_start, _) in zip(ordered[:-1], ordered[1:]):
        pause_dur = next_start - prev_end
        if not (min_pause_s <= pause_dur < max_pause_s):
            continue
        i0 = max(0, min(n - 1, int(round(prev_end / 0.01))))
        i1 = max(i0 + 1, min(n, int(round(next_start / 0.01))))
        pre_start = max(0, i0 - 60)
        baseline = _median(mm_100ms[pre_start:i0]) if i0 > pre_start else mm_100ms[i0]
        peak = max(mm_100ms[i0:i1])
        rise_db = round(peak - baseline, 2)
        rises.append(rise_db)
        events.append({
            "pause_start_s": round(prev_end, 3),
            "pause_end_s": round(next_start, 3),
            "pause_dur_s": round(pause_dur, 3),
            "baseline_lufs": round(baseline, 2),
            "peak_lufs": round(peak, 2),
            "rise_db": rise_db,
            "pumps": rise_db >= rise_threshold_db,
        })

    over = [e for e in events if e["pumps"]]
    severe = [e for e in over if e["rise_db"] >= 6.0]
    finding = None
    if len(over) >= min_pumping_pauses:
        finding = {
            "id": "sidechain-pause-pumping",
            "severity": "major" if len(severe) >= min_pumping_pauses else "minor",
            "pauses_checked": len(events),
            "pauses_pumping": len(over),
            "max_rise_db": max(rises) if rises else 0.0,
            "remediation": "Bridge speech gaps shorter than 1.2 s with a lookahead hold ducking envelope instead of fast sidechain release.",
        }

    return {
        "pauses_checked": len(events),
        "pauses_rising_over_threshold": len(over),
        "median_rise_db": round(_median(rises), 2) if rises else 0.0,
        "max_rise_db": round(max(rises), 2) if rises else 0.0,
        "events": events,
        "finding": finding,
    }


def build_hold_duck_envelope(
    speech_phrases: Sequence[tuple[float, float]],
    duration_s: float,
    *,
    hold_s: float = 1.2,
    depth_db: float = 11.0,
    attack_s: float = 0.15,
    release_s: float = 0.40,
    pad_s: float = 0.15,
) -> list[tuple[float, float]]:
    """Build piecewise-linear music ducking control points `(time_s, gain_db)` holding across short gaps."""
    blocks: list[list[float]] = []
    for s, e in sorted(speech_phrases, key=lambda p: p[0]):
        if blocks and s - blocks[-1][1] < hold_s:
            blocks[-1][1] = max(blocks[-1][1], e)
        else:
            blocks.append([s, e])

    pts: list[tuple[float, float]] = [(0.0, 0.0)]
    for s, e in blocks:
        down_start = max(pts[-1][0], s - pad_s - attack_s)
        down_end = max(down_start, s - pad_s)
        up_start = min(duration_s, e + pad_s)
        up_end = min(duration_s, up_start + release_s)
        pts.extend([
            (round(down_start, 3), 0.0),
            (round(down_end, 3), -abs(depth_db)),
            (round(up_start, 3), -abs(depth_db)),
            (round(up_end, 3), 0.0),
        ])
    pts.append((round(max(duration_s, pts[-1][0]), 3), 0.0))

    cleaned: list[tuple[float, float]] = []
    for t, g in pts:
        if cleaned and t <= cleaned[-1][0]:
            if t == cleaned[-1][0]:
                cleaned[-1] = (t, min(cleaned[-1][1], g))
            continue
        cleaned.append((t, round(g, 2)))
    return cleaned


def detect_edit_point_clicks(
    mono: Sequence[float],
    *,
    sample_rate: int = SR_DEFAULT,
    speech_phrases: Sequence[tuple[float, float]] = (),
    edit_times_s: Sequence[float] = (),
    min_dbfs: float = -50.0,
    ratio_threshold: float = 12.0,
    concentration_min: float = 0.50,
    edit_tolerance_s: float = 0.035,
) -> dict[str, Any]:
    """Detect zero-crossing / splice discontinuities via 2nd-difference impulse concentration.

    Computes `d2[t] = x[t+2] - 2*x[t+1] + x[t]` in 1 ms blocks, compares each 1 ms RMS against
    the local 21 ms median RMS (`>= ratio_threshold`), checks that at least `concentration_min`
    of the surrounding 5 ms second-difference energy sits inside that single 1 ms bin, and marks
    whether the impulse falls near a declared edit boundary.
    """
    n = len(mono)
    ms_samples = max(1, sample_rate // 1000)
    n_ms = (n - 2) // ms_samples
    if n_ms < 25:
        return {"clicks": [], "edit_boundary_clicks": 0, "finding": None}

    d2_energy_1ms = [0.0] * n_ms
    peak_1ms = [0.0] * n_ms
    for m in range(n_ms):
        base = m * ms_samples
        e_acc = 0.0
        pk = 0.0
        for k in range(ms_samples):
            idx = base + k
            x0 = float(mono[idx])
            x1 = float(mono[idx + 1])
            x2 = float(mono[idx + 2])
            d2 = x2 - 2.0 * x1 + x0
            e_acc += d2 * d2
            ax = abs(x1)
            if ax > pk:
                pk = ax
        d2_energy_1ms[m] = e_acc / ms_samples
        peak_1ms[m] = pk

    d2_rms_1ms = [math.sqrt(e) for e in d2_energy_1ms]

    def _in_speech(t_s: float) -> bool:
        return any(s <= t_s <= e for s, e in speech_phrases)

    clicks: list[dict[str, Any]] = []
    last_click_ms = -50
    for m in range(10, n_ms - 10):
        if m - last_click_ms < 15:
            continue
        t_s = (m + 0.5) * 0.001
        if _in_speech(t_s):
            continue
        amp_dbfs = power_to_db(peak_1ms[m] * peak_1ms[m])
        if amp_dbfs < min_dbfs:
            continue
        local_med = max(_median(d2_rms_1ms[m - 10 : m + 11]), 1e-12)
        ratio = d2_rms_1ms[m] / local_med
        if ratio < ratio_threshold:
            continue
        five_ms_energy = sum(d2_energy_1ms[m - 2 : m + 3])
        conc = d2_energy_1ms[m] / max(five_ms_energy, 1e-30)
        if conc < concentration_min:
            continue
        near_edit = any(abs(t_s - et) <= edit_tolerance_s for et in edit_times_s)
        last_click_ms = m
        clicks.append({
            "time_s": round(t_s, 4),
            "peak_dbfs": round(amp_dbfs, 2),
            "impulse_ratio": round(ratio, 2),
            "energy_concentration_1ms_over_5ms": round(conc, 3),
            "near_edit_boundary": near_edit,
        })

    edit_clicks = sum(1 for c in clicks if c["near_edit_boundary"])
    finding = None
    if clicks:
        finding = {
            "id": "edit-point-clicks",
            "severity": "major" if edit_clicks > 0 or any(c["peak_dbfs"] > -24.0 for c in clicks) else "minor",
            "click_count": len(clicks),
            "edit_boundary_clicks": edit_clicks,
            "remediation": "Apply a 5 to 15 ms equal-power crossfade at every audio splice and stem boundary.",
        }
    return {
        "clicks": clicks,
        "edit_boundary_clicks": edit_clicks,
        "finding": finding,
    }
