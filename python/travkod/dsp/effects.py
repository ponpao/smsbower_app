"""Time/dynamics/spatial effects for the humanize + master chain.

Pure numpy/scipy. Every function takes and returns float arrays shaped
(n_samples, n_channels) and is driven by a normalized amount so the UI sliders
map straight through.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve

from . import filters


def _pct(x: float) -> float:
    return max(0.0, min(1.0, x / 100.0))


# ---------------------------------------------------------------------------
# Humanize: wow & flutter (slow + fast pitch/time modulation) via fractional
# delay resampling, plus a touch of micro-dynamic gain drift. This is what makes
# a rigid, quantized AI render breathe like a tape/analog transfer.
# ---------------------------------------------------------------------------
def wow_flutter(x: np.ndarray, sr: int, amount_pct: float, seed: int = 7) -> np.ndarray:
    amt = _pct(amount_pct)
    if amt <= 0:
        return x
    n = x.shape[0]
    rng = np.random.default_rng(seed)
    t = np.arange(n) / sr

    # Wow: ~0.5-1.2 Hz slow drift. Flutter: ~6-9 Hz. Depths scale with amount.
    wow_hz = 0.6 + 0.4 * rng.random()
    flu_hz = 6.5 + 2.0 * rng.random()
    wow_depth = amt * 0.0016          # up to ~0.16% pitch drift
    flu_depth = amt * 0.0006
    phase_w = rng.random() * 2 * np.pi
    phase_f = rng.random() * 2 * np.pi

    # Modulated read-position (in samples) for a fractional-delay line.
    mod = (wow_depth * np.sin(2 * np.pi * wow_hz * t + phase_w)
           + flu_depth * np.sin(2 * np.pi * flu_hz * t + phase_f))
    read_pos = np.arange(n) + np.cumsum(mod) * 0.0 + mod * sr * 0.5
    read_pos = np.clip(read_pos, 0, n - 1.001)
    idx = np.floor(read_pos).astype(np.int64)
    frac = (read_pos - idx)[:, None]

    out = x[idx] * (1 - frac) + x[np.minimum(idx + 1, n - 1)] * frac
    return out.astype(x.dtype, copy=False)


def micro_dynamics(x: np.ndarray, sr: int, amount_pct: float, seed: int = 11) -> np.ndarray:
    """Slow, low-depth gain drift so levels aren't machine-flat."""
    amt = _pct(amount_pct)
    if amt <= 0:
        return x
    n = x.shape[0]
    rng = np.random.default_rng(seed)
    # Smooth noise via cumulative random walk, then a moving-average lowpass.
    # uniform_filter1d is O(n) (not O(n*k)), so this stays fast on full songs.
    from scipy.ndimage import uniform_filter1d
    walk = np.cumsum(rng.normal(0, 1, n))
    k = max(1, int(sr * 0.25))
    smooth = uniform_filter1d(walk, size=k, mode="nearest")
    smooth = smooth / (np.max(np.abs(smooth)) + 1e-9)
    drift = 1.0 + smooth * amt * 0.03    # up to +/-3% at full humanize
    return (x * drift[:, None]).astype(x.dtype, copy=False)


# ---------------------------------------------------------------------------
# Saturation: analog-style soft harmonic drive (tanh + light 2nd harmonic).
# ---------------------------------------------------------------------------
def saturate(x: np.ndarray, amount_pct: float) -> np.ndarray:
    amt = _pct(amount_pct)
    if amt <= 0:
        return x
    drive = 1.0 + amt * 4.0
    wet = np.tanh(x * drive) / np.tanh(drive) * (1.0 - 0.5 * amt) + x * (0.5 * amt)
    # subtle asymmetry -> even harmonics = "warmth"
    wet = wet + amt * 0.05 * (wet ** 2 - np.mean(wet ** 2, axis=0, keepdims=True))
    mix = 0.15 + 0.85 * amt
    return (x * (1 - mix) + wet * mix).astype(x.dtype, copy=False)


# ---------------------------------------------------------------------------
# De-esser: split the sibilance band (5-9 kHz), compress it, recombine.
# ---------------------------------------------------------------------------
def de_ess(x: np.ndarray, sr: int, amount_pct: float) -> np.ndarray:
    amt = _pct(amount_pct)
    if amt <= 0:
        return x
    sib = filters.band_pass(x, sr, 5000, 9000, order=2)
    env = _envelope(np.abs(sib).mean(axis=1), sr, atk=0.001, rel=0.05)
    thr = np.percentile(env, 70) + 1e-6
    ratio = 1.0 + amt * 5.0
    over = np.maximum(env, thr) / thr
    gain = over ** (-(1 - 1 / ratio))
    gain = np.clip(gain, 1e-3, 1.0)[:, None]
    reduced = sib * gain
    return (x - sib + reduced).astype(x.dtype, copy=False)


# ---------------------------------------------------------------------------
# Noise gate (downward expansion of the quiet floor).
# ---------------------------------------------------------------------------
def gate(x: np.ndarray, sr: int, amount_pct: float) -> np.ndarray:
    amt = _pct(amount_pct)
    if amt <= 0:
        return x
    env = _envelope(np.abs(x).mean(axis=1), sr, atk=0.002, rel=0.08)
    peak = np.percentile(env, 99) + 1e-9
    thr = peak * (10 ** (-(40 - amt * 20) / 20.0))   # -40..-20 dB threshold
    g = np.clip((env / (thr + 1e-9)), 0.0, 1.0) ** (amt * 2.0)
    g = _smooth(g, sr, 0.02)[:, None]
    return (x * g).astype(x.dtype, copy=False)


# ---------------------------------------------------------------------------
# Bus compression (feed-forward, soft knee, auto make-up).
# ---------------------------------------------------------------------------
def compress(x: np.ndarray, sr: int, amount_pct: float) -> np.ndarray:
    amt = _pct(amount_pct)
    if amt <= 0:
        return x
    ratio = 1.5 + amt * 4.0            # 1.5:1 .. 5.5:1
    thr_db = -8.0 - amt * 12.0         # -8 .. -20 dBFS
    atk, rel = 0.010, 0.120
    mono = np.abs(x).mean(axis=1) + 1e-9
    env_db = 20 * np.log10(_envelope(mono, sr, atk, rel) + 1e-9)
    over = np.maximum(0.0, env_db - thr_db)
    gain_db = -over * (1 - 1 / ratio)
    makeup = -thr_db * (1 - 1 / ratio) * 0.5 * amt
    g = 10 ** ((gain_db + makeup) / 20.0)
    return (x * g[:, None]).astype(x.dtype, copy=False)


# ---------------------------------------------------------------------------
# Stereo width via mid/side. width_pct negative narrows, positive widens.
# ---------------------------------------------------------------------------
def stereo_width(x: np.ndarray, width_pct: float) -> np.ndarray:
    if x.shape[1] < 2 or abs(width_pct) < 1e-3:
        return x
    w = 1.0 + (width_pct / 100.0)      # 0% => 1.0, +100% => 2.0, -100% => 0.0
    w = max(0.0, w)
    mid = (x[:, 0] + x[:, 1]) * 0.5
    side = (x[:, 0] - x[:, 1]) * 0.5 * w
    out = np.stack([mid + side, mid - side], axis=1)
    return out.astype(x.dtype, copy=False)


# ---------------------------------------------------------------------------
# Air: very-high shelf shimmer (kept separate from Treble so both can stack).
# ---------------------------------------------------------------------------
def air(x: np.ndarray, sr: int, amount_pct: float) -> np.ndarray:
    amt = _pct(amount_pct)
    if amt == 0:
        return x
    return filters.high_shelf(x, sr, 14000, gain_db=amt * 6.0, s=0.6)


# ---------------------------------------------------------------------------
# Reverb (short plate impulse) and echo (slap) — subtle glue, mixed low.
# ---------------------------------------------------------------------------
def reverb(x: np.ndarray, sr: int, amount_pct: float, seed: int = 3) -> np.ndarray:
    amt = _pct(amount_pct)
    if amt <= 0:
        return x
    rng = np.random.default_rng(seed)
    length = int(sr * (0.35 + 0.4 * amt))
    t = np.arange(length) / sr
    decay = np.exp(-t * (6.0 - 3.0 * amt))
    ir = rng.normal(0, 1, (length, x.shape[1])) * decay[:, None]
    ir[0] = 1.0
    wet = np.stack([fftconvolve(x[:, c], ir[:, c])[: x.shape[0]]
                    for c in range(x.shape[1])], axis=1)
    wet /= (np.max(np.abs(wet)) + 1e-9)
    wet *= np.max(np.abs(x)) + 1e-9
    mix = amt * 0.28
    return (x * (1 - mix) + wet * mix).astype(x.dtype, copy=False)


def echo(x: np.ndarray, sr: int, amount_pct: float, delay_s: float = 0.18) -> np.ndarray:
    amt = _pct(amount_pct)
    if amt <= 0:
        return x
    d = int(sr * delay_s)
    out = x.copy()
    fb = 0.35 * amt
    tap = np.zeros_like(x)
    tap[d:] = x[:-d]
    for _ in range(3):
        out += tap * fb
        nxt = np.zeros_like(tap)
        nxt[d:] = tap[:-d]
        tap = nxt * fb
    mix = amt * 0.25
    return (x * (1 - mix) + out * mix).astype(x.dtype, copy=False)


# ---------------------------------------------------------------------------
# True-peak-aware brickwall limiter. `drive_pct` = how hard we push into it,
# `ceiling_db` is the output dBTP ceiling (default -1 dBTP).
# ---------------------------------------------------------------------------
def limiter(x: np.ndarray, sr: int, drive_pct: float, ceiling_db: float = -1.0) -> np.ndarray:
    drive = 1.0 + _pct(drive_pct) * 1.2
    x = x * drive
    ceiling = 10 ** (ceiling_db / 20.0)

    # Oversample x4 to catch inter-sample peaks for a true-peak estimate.
    os = 4
    up = _resample_poly(x, os)
    peak = np.max(np.abs(up), axis=1)
    lookahead = int(sr * os * 0.005)
    # Sliding max (attack lookahead) so gain reduction anticipates transients.
    peak_env = _sliding_max(peak, lookahead)
    reduce = np.ones_like(peak_env)
    mask = peak_env > ceiling
    reduce[mask] = ceiling / peak_env[mask]
    reduce = _smooth(reduce, sr * os, 0.02)
    reduce = _resample_poly(reduce[:, None], 1.0 / os)[:, 0]
    reduce = reduce[: x.shape[0]]
    if reduce.shape[0] < x.shape[0]:
        reduce = np.pad(reduce, (0, x.shape[0] - reduce.shape[0]), mode="edge")
    out = x * reduce[:, None]
    return np.clip(out, -ceiling, ceiling).astype(x.dtype, copy=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _one_pole(sig: np.ndarray, a: float, zi: float = 0.0) -> np.ndarray:
    """Vectorized one-pole lowpass: y[n] = a*y[n-1] + (1-a)*x[n]."""
    from scipy.signal import lfilter
    b = np.array([1 - a], dtype=np.float64)
    aa = np.array([1.0, -a], dtype=np.float64)
    z = np.array([a * zi], dtype=np.float64)
    out, _ = lfilter(b, aa, sig, zi=z)
    return out.astype(sig.dtype, copy=False)


def _envelope(mono: np.ndarray, sr: int, atk: float, rel: float) -> np.ndarray:
    """Attack/release envelope follower.

    Vectorized approximation: a fast attack one-pole gives the transient-hugging
    envelope, then a release one-pole lets it fall back gently. This tracks the
    same shape as a sample-by-sample asymmetric follower but runs in C.
    """
    a_a = np.exp(-1.0 / (sr * max(atk, 1e-6)))
    a_r = np.exp(-1.0 / (sr * max(rel, 1e-6)))
    fast = _one_pole(mono, a_a, zi=mono[0])
    # Release stage: only allow decay slower than a_r by taking a running
    # elementwise max against a released version of the fast envelope.
    rel_env = _one_pole(fast, a_r, zi=fast[0])
    return np.maximum(fast, rel_env)


def _smooth(sig: np.ndarray, sr: int, tau: float) -> np.ndarray:
    a = np.exp(-1.0 / (sr * max(tau, 1e-6)))
    return _one_pole(sig, a, zi=sig[0])


def _sliding_max(sig: np.ndarray, w: int) -> np.ndarray:
    if w <= 1:
        return sig
    pad = np.pad(sig, (w, 0), mode="edge")
    # Cheap rolling max via strided windows.
    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(pad, w + 1)
    return np.max(win, axis=1)[: sig.shape[0]]


def _resample_poly(x: np.ndarray, factor: float) -> np.ndarray:
    from scipy.signal import resample_poly
    if factor >= 1:
        up, down = int(factor), 1
    else:
        up, down = 1, int(round(1.0 / factor))
    return resample_poly(x, up, down, axis=0).astype(x.dtype, copy=False)
