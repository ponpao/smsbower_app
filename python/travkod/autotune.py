"""Gentle vocal pitch correction (optional, off by default).

Deliberately conservative: it nudges detected pitch toward the nearest note of
the chosen scale by a user-controlled fraction. It is a musical polish tool, not
a hard-tune effect, and never fabricates content. Requires librosa; if unavailable
the audio is returned unchanged so the rest of the chain still runs.
"""
from __future__ import annotations

import numpy as np

try:
    import librosa
    _HAVE_LIBROSA = True
except Exception:
    _HAVE_LIBROSA = False


_SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "chromatic": list(range(12)),
}
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _scale_midi(key: str, scale: str) -> np.ndarray:
    root = _NOTES.index(key) if key in _NOTES else 0
    degrees = _SCALES.get(scale, _SCALES["major"])
    allowed = np.array([(root + d) % 12 for d in degrees])
    return allowed


def gentle_correct(x: np.ndarray, sr: int, strength_pct: float, key: str, scale: str) -> np.ndarray:
    if not _HAVE_LIBROSA or strength_pct <= 0:
        return x
    strength = max(0.0, min(1.0, strength_pct / 100.0)) * 0.7  # cap for gentleness
    allowed = _scale_midi(key, scale)

    out = np.empty_like(x)
    for c in range(x.shape[1]):
        mono = x[:, c].astype(np.float32)
        try:
            f0, voiced, _ = librosa.pyin(
                mono, fmin=80, fmax=1000, sr=sr,
                frame_length=2048, hop_length=256,
            )
        except Exception:
            return x
        if f0 is None or np.all(np.isnan(f0)):
            out[:, c] = mono
            continue

        # Per-frame semitone correction toward nearest allowed scale note.
        midi = 69 + 12 * np.log2(np.where(np.isnan(f0), 440.0, f0) / 440.0)
        pc = np.mod(np.round(midi), 12)
        target_pc = np.array([allowed[np.argmin(np.abs(((allowed - p + 6) % 12) - 6))]
                              for p in pc])
        delta_pc = ((target_pc - pc + 6) % 12) - 6
        semis = np.where(voiced, delta_pc * strength, 0.0)

        # Apply a single median shift per voiced region to stay gentle and
        # artifact-free rather than warping every frame.
        shift = float(np.nanmedian(semis[np.isfinite(semis)])) if np.any(np.isfinite(semis)) else 0.0
        if abs(shift) < 0.02:
            out[:, c] = mono
        else:
            out[:, c] = librosa.effects.pitch_shift(mono, sr=sr, n_steps=shift)
    return out.astype(x.dtype, copy=False)
