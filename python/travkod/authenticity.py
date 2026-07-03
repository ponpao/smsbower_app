"""Authenticity Report (BETA — experimental, may be wrong).

Returns a *calibrated probability* that a track is AI-generated, together with a
confidence interval and a plain-language caveat. This is informational only.

HONEST-DESIGN CONTRACT (see project NON-GOALS):
  * It never returns a bare single number presented as certainty.
  * It never frames output as "how to pass a check" or advises evasion.
  * Weights below are heuristic priors, NOT trained on a validated corpus, so the
    result stays behind a Beta label and carries a wide confidence interval.
  * Detection of AI-generated audio is an open research problem; a low P(AI) is
    not proof of human authorship, and a high P(AI) is not proof of the reverse.

The classifier is a small logistic model over interpretable acoustic features,
wrapped in temperature scaling (a standard calibration method). The confidence
interval comes from perturbing the features and re-scoring (a lightweight
sensitivity/bootstrap estimate), which is deliberately wide.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import soundfile as sf


# Logistic weights over standardized features (heuristic priors, not trained).
# Positive weight => feature pushes toward "more likely AI".
_FEATURES = ["spectral_flatness", "crest_factor", "stereo_corr",
             "noise_floor", "hf_rolloff", "onset_regularity"]
_W = np.array([1.1, -0.9, 0.7, -1.0, 0.5, 0.8])
_B = -0.2
# Temperature > 1 softens confidence (calibration). Kept high because the model
# is unvalidated: we do NOT want to sound certain.
_TEMPERATURE = 2.4

DISCLAIMER = (
    "Beta — experimental. This is a probabilistic estimate, not a verdict. "
    "AI-audio detection is unreliable; treat this as a rough signal only. "
    "A low probability is not proof of human authorship."
)


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + np.exp(-z))


def _features(audio: np.ndarray, sr: int) -> Dict[str, float]:
    mono = audio.mean(axis=1)
    n = mono.shape[0]

    # Spectral flatness (geometric/arithmetic mean of power) — AI renders can be
    # unusually flat/full-band.
    frame = 4096
    mags = []
    for start in range(0, max(1, n - frame), frame):
        seg = mono[start:start + frame] * np.hanning(frame)
        mags.append(np.abs(np.fft.rfft(seg)) ** 2 + 1e-12)
    P = np.mean(mags, axis=0) if mags else np.array([1.0])
    flatness = float(np.exp(np.mean(np.log(P))) / (np.mean(P) + 1e-12))

    # Crest factor (peak/RMS) — very consistent dynamics can look synthetic.
    rms = float(np.sqrt(np.mean(mono ** 2)) + 1e-12)
    crest = float(np.max(np.abs(mono)) / rms)

    # Stereo correlation.
    if audio.shape[1] >= 2:
        l, r = audio[:, 0], audio[:, 1]
        denom = (np.std(l) * np.std(r) + 1e-12)
        stereo_corr = float(np.clip(np.mean((l - l.mean()) * (r - r.mean())) / denom, -1, 1))
    else:
        stereo_corr = 1.0

    # Noise floor (10th-percentile short-term RMS in dB) — real captures carry
    # more low-level noise/room than clean synthesis.
    win = max(1, sr // 20)
    env = np.sqrt(np.convolve(mono ** 2, np.ones(win) / win, mode="valid") + 1e-12)
    noise_floor = float(20 * np.log10(np.percentile(env, 10) + 1e-9))

    # HF rolloff (fraction of energy above 10 kHz).
    full = np.abs(np.fft.rfft(mono[: min(n, sr * 30)] + 1e-12)) ** 2
    freqs = np.fft.rfftfreq(min(n, sr * 30), 1.0 / sr)
    hf = float(full[freqs > 10000].sum() / (full.sum() + 1e-12))

    # Onset regularity (coefficient of variation of inter-onset intervals).
    d = np.abs(np.diff(env))
    thr = np.percentile(d, 95)
    onsets = np.where(d > thr)[0]
    if onsets.size > 3:
        ioi = np.diff(onsets)
        onset_reg = float(1.0 - min(1.0, np.std(ioi) / (np.mean(ioi) + 1e-9)))
    else:
        onset_reg = 0.5

    return {
        "spectral_flatness": flatness,
        "crest_factor": crest,
        "stereo_corr": stereo_corr,
        "noise_floor": noise_floor,
        "hf_rolloff": hf,
        "onset_regularity": onset_reg,
    }


# Rough standardization constants (feature mean/std priors) so weights operate on
# comparable scales. Approximate; part of why the interval stays wide.
_MU = np.array([0.05, 8.0, 0.3, -45.0, 0.08, 0.5])
_SD = np.array([0.04, 3.0, 0.4, 12.0, 0.06, 0.25])


def _score(feat_vec: np.ndarray) -> float:
    z = (feat_vec - _MU) / _SD
    logit = float(np.dot(_W, z) + _B) / _TEMPERATURE
    return _sigmoid(logit)


def analyze(path: str) -> Dict:
    audio, sr = sf.read(path, always_2d=True, dtype="float32")
    feats = _features(audio, sr)
    vec = np.array([feats[k] for k in _FEATURES])

    p = _score(vec)

    # Confidence interval via feature perturbation (sensitivity bootstrap):
    # jitter each standardized feature and re-score to reflect model fragility.
    rng = np.random.default_rng(0)
    samples = []
    for _ in range(200):
        jitter = vec + rng.normal(0, 1, vec.shape) * _SD * 0.5
        samples.append(_score(jitter))
    lo, hi = np.percentile(samples, [10, 90])

    return {
        "p_ai": round(float(p), 3),
        "ci_low": round(float(lo), 3),
        "ci_high": round(float(hi), 3),
        "confidence_label": _band(hi - lo),
        "features": {k: round(float(v), 4) for k, v in feats.items()},
        "beta": True,
        "disclaimer": DISCLAIMER,
        "note": _plain_language(p, lo, hi),
    }


def _band(width: float) -> str:
    if width > 0.4:
        return "low confidence"
    if width > 0.2:
        return "moderate confidence"
    return "higher confidence"


def _plain_language(p: float, lo: float, hi: float) -> str:
    pct = int(round(p * 100))
    return (
        f"Estimated ~{pct}% chance this track is AI-generated "
        f"(range {int(round(lo*100))}-{int(round(hi*100))}%). "
        "This is an experimental estimate and can be wrong in either direction."
    )
