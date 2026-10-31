"""ITU-R BS.1770-4 loudness, loudness range (LRA), sample peak and 4x inter-sample true peak.

Pure Python standard-library implementation at 48 kHz using exact BS.1770-4 pre-filter and
RLB high-pass biquad coefficients, 400 ms gated blocks (-70 LUFS absolute, -10 LU relative),
3 s short-term LRA blocks (-70 LUFS absolute, -20 LU relative, P95 minus P10), and 4x cubic
Hermite / windowed-sinc inter-sample peak estimation.
"""

from __future__ import annotations

import hashlib
import math
import struct
import wave
from pathlib import Path
from typing import Any, Sequence

SR_DEFAULT = 48000

# ITU-R BS.1770-4 Table 1 (48 kHz) Stage 1 shelving pre-filter and Stage 2 RLB high-pass
KB1 = (1.53512485958697, -2.69169618940638, 1.19839281085285)
KA1 = (1.0, -1.69065929318241, 0.73248077421585)
KB2 = (1.0, -2.0, 1.0)
KA2 = (1.0, -1.99004745483398, 0.99007225036621)


def power_to_lufs(power: float) -> float:
    return -0.691 + 10.0 * math.log10(max(power, 1e-30))


def power_to_db(power: float, floor: float = -150.0) -> float:
    return max(floor, 10.0 * math.log10(max(power, 1e-30)))


def biquad_filter(samples: Sequence[float], b: tuple[float, float, float], a: tuple[float, float, float]) -> list[float]:
    """Direct Form II Transposed second-order IIR filter."""
    b0, b1, b2 = b
    _, a1, a2 = a
    out = [0.0] * len(samples)
    z1 = 0.0
    z2 = 0.0
    for i, x in enumerate(samples):
        xf = float(x)
        y = b0 * xf + z1
        z1 = b1 * xf - a1 * y + z2
        z2 = b2 * xf - a2 * y
        out[i] = y
    return out


def k_weighted_power_10ms(channels: Sequence[Sequence[float]], sample_rate: int = SR_DEFAULT) -> list[float]:
    """Return BS.1770 K-weighted mean-square power per 10 ms hop summed across L/R channels."""
    if not channels or not channels[0]:
        return []
    hop = max(1, sample_rate // 100)
    n_samples = min(len(ch) for ch in channels)
    n_frames = n_samples // hop
    if n_frames == 0:
        return []

    summed = [0.0] * n_frames
    for ch_idx, ch in enumerate(channels):
        weight = 1.41 if ch_idx in (3, 4) else 1.0
        stage1 = biquad_filter(ch[: n_frames * hop], KB1, KA1)
        stage2 = biquad_filter(stage1, KB2, KA2)
        for f in range(n_frames):
            base = f * hop
            acc = 0.0
            for k in range(hop):
                v = stage2[base + k]
                acc += v * v
            summed[f] += weight * (acc / hop)
    return summed


def _moving_mean(values: Sequence[float], window: int, step: int) -> list[float]:
    n = len(values)
    if n < window or window <= 0:
        return []
    prefix = [0.0] * (n + 1)
    for i, v in enumerate(values):
        prefix[i + 1] = prefix[i] + v
    out: list[float] = []
    for end in range(window, n + 1, step):
        out.append((prefix[end] - prefix[end - window]) / window)
    return out


def _percentile(sorted_vals: Sequence[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(math.floor(pos))
    hi = min(len(sorted_vals) - 1, lo + 1)
    frac = pos - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)


def integrated_lufs(kp_10ms: Sequence[float]) -> float | None:
    """BS.1770-4 gated integrated loudness over 400 ms blocks (40 x 10 ms) with 75% overlap (step 10)."""
    blocks = _moving_mean(kp_10ms, window=40, step=10)
    if not blocks:
        return None
    abs_gated = [b for b in blocks if power_to_lufs(b) > -70.0]
    if not abs_gated:
        return None
    rel_gate = power_to_lufs(sum(abs_gated) / len(abs_gated)) - 10.0
    rel_gated = [b for b in abs_gated if power_to_lufs(b) > rel_gate]
    if not rel_gated:
        return None
    return round(power_to_lufs(sum(rel_gated) / len(rel_gated)), 2)


def loudness_range_lu(kp_10ms: Sequence[float]) -> float | None:
    """EBU R128 / BS.1770 short-term (3.0 s) loudness range (P95 - P10 after -70 LUFS and -20 LU gates)."""
    st_blocks = _moving_mean(kp_10ms, window=300, step=10)
    if not st_blocks:
        return None
    abs_gated = [b for b in st_blocks if power_to_lufs(b) > -70.0]
    if not abs_gated:
        return None
    rel_gate = power_to_lufs(sum(abs_gated) / len(abs_gated)) - 20.0
    kept_lufs = sorted(power_to_lufs(b) for b in abs_gated if power_to_lufs(b) > rel_gate)
    if not kept_lufs:
        return None
    return round(_percentile(kept_lufs, 95.0) - _percentile(kept_lufs, 10.0), 2)


def sample_peak_dbfs(channels: Sequence[Sequence[float]]) -> float:
    best = 0.0
    for ch in channels:
        for s in ch:
            a = abs(float(s))
            if a > best:
                best = a
    return round(20.0 * math.log10(max(best, 1e-12)), 2)


def _sinc_fir_phases() -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """12-tap Hann-windowed sinc fractional-delay polyphase filters for phases 0.25, 0.50, 0.75."""
    phases = []
    taps = 12
    half = taps // 2
    for frac in (0.25, 0.50, 0.75):
        coeffs = []
        for m in range(-half + 1, half + 1):
            x = m - frac
            sinc = 1.0 if abs(x) < 1e-12 else math.sin(math.pi * x) / (math.pi * x)
            # Hann window over [-half, half]
            win = 0.5 * (1.0 + math.cos(math.pi * x / half))
            coeffs.append(sinc * win)
        norm = sum(coeffs)
        phases.append(tuple(c / norm for c in coeffs))
    return phases[0], phases[1], phases[2]


_PHASES_4X = _sinc_fir_phases()


def true_peak_dbtp(channels: Sequence[Sequence[float]]) -> float:
    """4x oversampled inter-sample true peak in dBTP using 12-tap windowed-sinc polyphase filters."""
    best = 0.0
    p1, p2, p3 = _PHASES_4X
    for ch in channels:
        n = len(ch)
        if n == 0:
            continue
        padded = [0.0] * 5 + [float(v) for v in ch] + [0.0] * 6
        for i in range(n):
            s0 = abs(padded[i + 5])
            if s0 > best:
                best = s0
            if s0 >= 0.25:
                # Evaluate fractional inter-sample peaks where waveform excursions can exceed sample peaks
                base = i
                for coeffs in (p1, p2, p3):
                    acc = 0.0
                    for k in range(12):
                        acc += coeffs[k] * padded[base + k]
                    aa = abs(acc)
                    if aa > best:
                        best = aa
    return round(20.0 * math.log10(max(best, 1e-12)), 2)


def evaluate_loudness(
    channels: Sequence[Sequence[float]],
    *,
    sample_rate: int = SR_DEFAULT,
    target_lufs: float = -16.0,
    tolerance_lu: float = 1.0,
    max_true_peak_dbtp: float = -1.0,
    max_lra_lu: float = 8.0,
) -> dict[str, Any]:
    """Measure BS.1770 loudness, LRA, sample peak and true peak and gate against delivery targets."""
    kp = k_weighted_power_10ms(channels, sample_rate=sample_rate)
    i_lufs = integrated_lufs(kp)
    lra = loudness_range_lu(kp)
    sp_dbfs = sample_peak_dbfs(channels)
    tp_dbtp = true_peak_dbtp(channels)

    findings: list[dict[str, Any]] = []
    if i_lufs is None:
        findings.append({"id": "loudness-silent", "severity": "blocker", "detail": "Integrated loudness gated out below -70 LUFS."})
    else:
        delta = round(i_lufs - target_lufs, 2)
        if abs(delta) > tolerance_lu:
            sev = "major" if abs(delta) > 2.5 else "minor"
            findings.append({
                "id": "integrated-loudness-offset",
                "severity": sev,
                "measured_lufs": i_lufs,
                "target_lufs": target_lufs,
                "delta_lu": delta,
            })
    if tp_dbtp > max_true_peak_dbtp:
        findings.append({
            "id": "true-peak-ceiling",
            "severity": "major" if tp_dbtp > -0.3 else "minor",
            "measured_dbtp": tp_dbtp,
            "ceiling_dbtp": max_true_peak_dbtp,
        })
    if lra is not None and lra > max_lra_lu:
        findings.append({
            "id": "loudness-range-wide",
            "severity": "minor",
            "measured_lu": lra,
            "max_lu": max_lra_lu,
        })

    return {
        "integrated_lufs": i_lufs,
        "loudness_range_lu": lra,
        "sample_peak_dbfs": sp_dbfs,
        "true_peak_dbtp": tp_dbtp,
        "target_lufs": target_lufs,
        "tolerance_lu": tolerance_lu,
        "max_true_peak_dbtp": max_true_peak_dbtp,
        "max_lra_lu": max_lra_lu,
        "findings": findings,
        "kp_10ms": kp,
    }


def read_wav_pcm(path: str | Path) -> tuple[list[list[float]], int, str]:
    """Read 16-bit or 32-bit PCM WAV into normalized [-1.0, 1.0] channel arrays, sample_rate and sha256."""
    p = Path(path)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    with wave.open(str(p), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    channels: list[list[float]] = [[] for _ in range(n_channels)]
    if sampwidth == 2:
        vals = struct.unpack(f"<{n_frames * n_channels}h", raw)
        scale = 1.0 / 32768.0
        for idx, v in enumerate(vals):
            channels[idx % n_channels].append(v * scale)
    elif sampwidth == 4:
        vals = struct.unpack(f"<{n_frames * n_channels}i", raw)
        scale = 1.0 / 2147483648.0
        for idx, v in enumerate(vals):
            channels[idx % n_channels].append(v * scale)
    else:
        raise ValueError(f"unsupported WAV sample width: {sampwidth} bytes")
    return channels, rate, digest
