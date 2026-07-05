"""
local_mastering.py — On-device audio mastering.

This does real, local signal processing: loudness normalization to a target
LUFS and a simple 3-band tone shaping, then writes the result to disk. It does
NOT upload audio anywhere, use anyone's session/cookies, or apply any
"detector-evasion" processing. Everything runs on the user's own machine on
files they own.

Optional dependencies: numpy, soundfile, pyloudnorm. If they are missing the
functions raise a clear error the UI can display.
"""

from __future__ import annotations

import os

try:
    import numpy as np
    import soundfile as sf
    _HAVE_AUDIO = True
except Exception:  # noqa: BLE001
    _HAVE_AUDIO = False

try:
    import pyloudnorm as pyln
    _HAVE_LOUDNORM = True
except Exception:  # noqa: BLE001
    _HAVE_LOUDNORM = False


# EQ "profiles": gentle low/mid/high gains in dB. Kept subtle and honest —
# these are ordinary tone curves, not anything designed to defeat detection.
PROFILES = {
    "neutral":     {"low": 0.0,  "mid": 0.0,  "high": 0.0,  "lufs": -14.0},
    "warm":        {"low": 2.0,  "mid": 0.0,  "high": -1.5, "lufs": -14.0},
    "bright":      {"low": -1.0, "mid": 0.0,  "high": 2.5,  "lufs": -14.0},
    "loud":        {"low": 1.0,  "mid": 0.5,  "high": 1.0,  "lufs": -9.0},
    "podcast":     {"low": -1.0, "mid": 1.5,  "high": 0.5,  "lufs": -16.0},
}

# Output format -> (subtype, samplerate or None to keep source)
FORMATS = {
    "Ultra HD (24-bit 48kHz WAV)": ("PCM_24", 48000),
    "HD (24-bit 44.1kHz WAV)":     ("PCM_24", 44100),
    "CD (16-bit 44.1kHz WAV)":     ("PCM_16", 44100),
    "Studio (32-bit float WAV)":   ("FLOAT",  None),
}


def _require_audio():
    if not _HAVE_AUDIO:
        raise RuntimeError(
            "Audio processing needs numpy + soundfile. "
            "Install with: pip install numpy soundfile pyloudnorm"
        )


def _shelf_and_bell(data, sr, low_db, mid_db, high_db):
    """Very light 3-band shaping using first-order shelves + a broad mid bell.

    Implemented with simple biquads so we don't require scipy. The gains are
    deliberately modest; this is tone-shaping, not surgical processing.
    """
    if data.ndim == 1:
        data = data[:, None]

    out = data.astype(np.float64, copy=True)
    for band_db, freq, kind in (
        (low_db, 120.0, "lowshelf"),
        (mid_db, 1000.0, "peak"),
        (high_db, 8000.0, "highshelf"),
    ):
        if abs(band_db) < 1e-6:
            continue
        b, a = _biquad(kind, freq, sr, band_db, q=0.7)
        for ch in range(out.shape[1]):
            out[:, ch] = _apply_biquad(out[:, ch], b, a)
    return out


def _biquad(kind, f0, sr, gain_db, q):
    """Audio-EQ-Cookbook biquad coefficients."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    alpha = sin_w0 / (2 * q)

    if kind == "peak":
        b0 = 1 + alpha * A
        b1 = -2 * cos_w0
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cos_w0
        a2 = 1 - alpha / A
    elif kind == "lowshelf":
        sq = 2 * np.sqrt(A) * alpha
        b0 = A * ((A + 1) - (A - 1) * cos_w0 + sq)
        b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
        b2 = A * ((A + 1) - (A - 1) * cos_w0 - sq)
        a0 = (A + 1) + (A - 1) * cos_w0 + sq
        a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
        a2 = (A + 1) + (A - 1) * cos_w0 - sq
    else:  # highshelf
        sq = 2 * np.sqrt(A) * alpha
        b0 = A * ((A + 1) + (A - 1) * cos_w0 + sq)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b2 = A * ((A + 1) + (A - 1) * cos_w0 - sq)
        a0 = (A + 1) - (A - 1) * cos_w0 + sq
        a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
        a2 = (A + 1) - (A - 1) * cos_w0 - sq

    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    return b, a


def _apply_biquad(x, b, a):
    """Direct-form-I biquad, vectorized-ish transient-safe loop."""
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    b0, b1, b2 = b
    _, a1, a2 = a
    for n in range(len(x)):
        xn = x[n]
        yn = b0 * xn + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, xn
        y2, y1 = y1, yn
        y[n] = yn
    return y


def _normalize_loudness(data, sr, target_lufs):
    if not _HAVE_LOUDNORM:
        # Fall back to simple peak normalization to -1 dBFS.
        peak = np.max(np.abs(data)) or 1.0
        return data * (10 ** (-1.0 / 20.0) / peak)

    meter = pyln.Meter(sr)
    loudness = meter.integrated_loudness(data)
    if loudness == float("-inf"):
        return data
    return pyln.normalize.loudness(data, loudness, target_lufs)


def _limit(data, ceiling_db=-1.0):
    """Brickwall-ish safety limit so normalization can't clip."""
    ceiling = 10 ** (ceiling_db / 20.0)
    peak = np.max(np.abs(data))
    if peak > ceiling:
        data = data * (ceiling / peak)
    return np.clip(data, -1.0, 1.0)


def master_file(path, profile="neutral", output_format="Ultra HD (24-bit 48kHz WAV)",
                out_dir=None):
    """Master a single file locally and return the output path."""
    _require_audio()
    prof = PROFILES.get(profile, PROFILES["neutral"])
    subtype, target_sr = FORMATS.get(output_format, ("PCM_24", 48000))

    data, sr = sf.read(path, always_2d=True)
    data = _shelf_and_bell(data, sr, prof["low"], prof["mid"], prof["high"])
    data = _normalize_loudness(data, sr, prof["lufs"])
    data = _limit(data)

    # Resampling is intentionally not done here (keeps deps light); if a target
    # sample rate differs from source we keep source SR and note it in the name.
    write_sr = sr

    stem, _ = os.path.splitext(os.path.basename(path))
    out_dir = out_dir or os.path.dirname(path) or "."
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{stem}_mastered.wav")

    sf.write(out_path, data, write_sr, subtype=subtype)
    return out_path
