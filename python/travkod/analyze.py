"""File analysis for the batch-queue columns.

Reports: duration, type/codec, key + major/minor, sample rate + bit depth,
integrated loudness (LUFS), true peak (dBTP), channels. Uses soundfile for I/O
and pyloudnorm for loudness; key detection is a self-contained Krumhansl-Schmuckler
estimator over an FFT chromagram so it needs no extra native deps.
"""
from __future__ import annotations

import os
from typing import Dict, Optional

import numpy as np
import soundfile as sf

try:
    import pyloudnorm as pyln
    _HAVE_PYLN = True
except Exception:
    _HAVE_PYLN = False


_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler key profiles.
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _subtype_bits(subtype: str) -> Optional[int]:
    m = {
        "PCM_16": 16, "PCM_24": 24, "PCM_32": 32, "PCM_S8": 8, "PCM_U8": 8,
        "FLOAT": 32, "DOUBLE": 64, "ALAC_16": 16, "ALAC_24": 24,
    }
    return m.get(subtype)


def _chromagram(mono: np.ndarray, sr: int) -> np.ndarray:
    """12-bin pitch-class energy via magnitude FFT frames."""
    n = 4096
    hop = 2048
    if mono.shape[0] < n:
        mono = np.pad(mono, (0, n - mono.shape[0]))
    window = np.hanning(n)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    # Map each FFT bin to a pitch class (ignore <27.5 Hz / A0).
    valid = freqs > 27.5
    midi = np.zeros_like(freqs)
    midi[valid] = 69 + 12 * np.log2(freqs[valid] / 440.0)
    pc = np.mod(np.round(midi).astype(int), 12)

    chroma = np.zeros(12)
    for start in range(0, mono.shape[0] - n, hop):
        frame = mono[start:start + n] * window
        mag = np.abs(np.fft.rfft(frame))
        for k in range(12):
            chroma[k] += mag[valid & (pc == k)].sum()
    total = chroma.sum()
    return chroma / total if total > 0 else chroma


def detect_key(mono: np.ndarray, sr: int) -> str:
    chroma = _chromagram(mono, sr)
    if chroma.sum() == 0:
        return "—"
    best_score, best = -1e9, ("C", "major")
    for shift in range(12):
        rolled = np.roll(chroma, -shift)
        maj = float(np.corrcoef(rolled, _MAJOR)[0, 1])
        minr = float(np.corrcoef(rolled, _MINOR)[0, 1])
        if maj > best_score:
            best_score, best = maj, (_NOTES[shift], "major")
        if minr > best_score:
            best_score, best = minr, (_NOTES[shift], "minor")
    note, mode = best
    return f"{note} {'Maj' if mode == 'major' else 'Min'}"


def true_peak_dbtp(audio: np.ndarray, sr: int) -> float:
    """4x-oversampled true peak in dBTP."""
    from scipy.signal import resample_poly
    up = resample_poly(audio, 4, 1, axis=0)
    peak = float(np.max(np.abs(up))) + 1e-12
    return round(20 * np.log10(peak), 2)


def analyze_file(path: str) -> Dict:
    info = sf.info(path)
    audio, sr = sf.read(path, always_2d=True, dtype="float32")
    n, ch = audio.shape
    duration = n / float(sr)

    mono = audio.mean(axis=1)
    lufs = None
    if _HAVE_PYLN and n > sr * 0.4:
        try:
            lufs = round(float(pyln.Meter(sr).integrated_loudness(audio)), 1)
        except Exception:
            lufs = None

    result = {
        "path": path,
        "filename": os.path.basename(path),
        "duration": round(duration, 2),
        "duration_str": _fmt_dur(duration),
        "type": (info.format or "").upper(),
        "codec": info.subtype,
        "key": detect_key(mono, sr),
        "sample_rate": sr,
        "bit_depth": _subtype_bits(info.subtype),
        "loudness_lufs": lufs,
        "true_peak_dbtp": true_peak_dbtp(audio, sr),
        "channels": ch,
        "channel_label": {1: "Mono", 2: "Stereo"}.get(ch, f"{ch}ch"),
    }
    return result


def _fmt_dur(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"
