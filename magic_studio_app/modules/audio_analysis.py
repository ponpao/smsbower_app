"""
audio_analysis.py — Honest local audio measurements.

This replaces the original "AI Music Detector / anti-detector shift" concept
with something legitimate: it reports real technical stats about a file
(duration, channels, sample rate, integrated loudness, true peak, RMS). These
are the kinds of numbers a mastering engineer actually checks. It makes no
claim about a track's origin and does nothing to hide or spoof provenance.
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


def analyze_file(path):
    """Return a dict of technical measurements for a local audio file."""
    if not _HAVE_AUDIO:
        raise RuntimeError(
            "Analysis needs numpy + soundfile. "
            "Install with: pip install numpy soundfile pyloudnorm"
        )

    info = sf.info(path)
    data, sr = sf.read(path, always_2d=True)

    duration = info.frames / float(info.samplerate) if info.samplerate else 0.0
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    true_peak_db = 20 * np.log10(peak) if peak > 0 else float("-inf")
    rms = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0
    rms_db = 20 * np.log10(rms) if rms > 0 else float("-inf")

    if _HAVE_LOUDNORM and data.size:
        try:
            meter = pyln.Meter(sr)
            lufs = float(meter.integrated_loudness(data))
        except Exception:  # noqa: BLE001
            lufs = float("nan")
    else:
        lufs = float("nan")

    return {
        "filename": os.path.basename(path),
        "duration": _fmt_time(duration),
        "channels": info.channels,
        "samplerate": f"{info.samplerate} Hz",
        "subtype": info.subtype or "",
        "lufs": _fmt_db(lufs, suffix=" LUFS"),
        "true_peak": _fmt_db(true_peak_db, suffix=" dBFS"),
        "rms": _fmt_db(rms_db, suffix=" dB"),
    }


def _fmt_time(seconds):
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


def _fmt_db(value, suffix=""):
    if value != value:  # NaN
        return "—"
    if value == float("-inf"):
        return f"-inf{suffix}"
    return f"{value:.1f}{suffix}"
