"""Biquad filter design and application (RBJ Audio EQ cookbook).

Pure numpy/scipy so the engine runs anywhere without native audio deps. All
functions operate on float32/float64 arrays shaped (n_samples, n_channels).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import sosfilt, sosfiltfilt, butter


def _apply_biquad(x: np.ndarray, b: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Apply a single biquad (transposed direct form II) per channel."""
    sos = np.concatenate([b, a]).reshape(1, 6)
    return sosfilt(sos, x, axis=0).astype(x.dtype, copy=False)


def _norm(b0, b1, b2, a0, a1, a2):
    b = np.array([b0 / a0, b1 / a0, b2 / a0], dtype=np.float64)
    a = np.array([1.0, a1 / a0, a2 / a0], dtype=np.float64)
    return b, a


def peaking(x, sr, f0, gain_db, q=0.9):
    if abs(gain_db) < 1e-4:
        return x
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    alpha = np.sin(w0) / (2 * q)
    cw = np.cos(w0)
    b0 = 1 + alpha * A
    b1 = -2 * cw
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * cw
    a2 = 1 - alpha / A
    b, a = _norm(b0, b1, b2, a0, a1, a2)
    return _apply_biquad(x, b, a)


def low_shelf(x, sr, f0, gain_db, s=0.7):
    if abs(gain_db) < 1e-4:
        return x
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / 2 * np.sqrt((A + 1 / A) * (1 / s - 1) + 2)
    tsa = 2 * np.sqrt(A) * alpha
    b0 = A * ((A + 1) - (A - 1) * cw + tsa)
    b1 = 2 * A * ((A - 1) - (A + 1) * cw)
    b2 = A * ((A + 1) - (A - 1) * cw - tsa)
    a0 = (A + 1) + (A - 1) * cw + tsa
    a1 = -2 * ((A - 1) + (A + 1) * cw)
    a2 = (A + 1) + (A - 1) * cw - tsa
    b, a = _norm(b0, b1, b2, a0, a1, a2)
    return _apply_biquad(x, b, a)


def high_shelf(x, sr, f0, gain_db, s=0.7):
    if abs(gain_db) < 1e-4:
        return x
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / 2 * np.sqrt((A + 1 / A) * (1 / s - 1) + 2)
    tsa = 2 * np.sqrt(A) * alpha
    b0 = A * ((A + 1) + (A - 1) * cw + tsa)
    b1 = -2 * A * ((A - 1) + (A + 1) * cw)
    b2 = A * ((A + 1) + (A - 1) * cw - tsa)
    a0 = (A + 1) - (A - 1) * cw + tsa
    a1 = 2 * ((A - 1) - (A + 1) * cw)
    a2 = (A + 1) - (A - 1) * cw - tsa
    b, a = _norm(b0, b1, b2, a0, a1, a2)
    return _apply_biquad(x, b, a)


def high_pass(x, sr, f0, order=2):
    """Zero-phase high-pass (Low-Cut). f0 in Hz."""
    if f0 <= 20:
        return x
    f0 = min(f0, sr * 0.45)
    sos = butter(order, f0 / (sr / 2), btype="highpass", output="sos")
    # filtfilt for zero phase so low-cut doesn't smear transients.
    return sosfiltfilt(sos, x, axis=0).astype(x.dtype, copy=False)


def band_pass(x, sr, f_lo, f_hi, order=2):
    f_lo = max(20.0, f_lo)
    f_hi = min(f_hi, sr * 0.45)
    sos = butter(order, [f_lo / (sr / 2), f_hi / (sr / 2)], btype="bandpass", output="sos")
    return sosfilt(sos, x, axis=0).astype(x.dtype, copy=False)
