"""TRAVKOD humanize + master engine.

Signal chain (spec order):
    low-cut -> humanize (wow/flutter + micro-dynamics) -> saturation ->
    tonal EQ (strip bells/shelves + 10-band graphic) -> de-harsh/de-ess ->
    gate -> compression -> air -> reverb/echo -> stereo width ->
    gain trim -> limiter (true-peak) -> LUFS normalize

Every stage is driven by `Params` (see params.py), which mirrors the UI console
one-to-one. `process()` accepts a progress callback so the orchestrator can
stream per-file stage events into the batch queue.

Honest-use note: this module only improves audio quality (warmth, de-harsh,
loudness). It contains nothing that targets or attempts to defeat AI-detection.
"""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from .params import Params, EQ_BANDS
from .dsp import filters, effects
from . import autotune as _autotune

try:
    import pyloudnorm as pyln
    _HAVE_PYLN = True
except Exception:  # pragma: no cover - metering degrades gracefully
    _HAVE_PYLN = False


ProgressFn = Callable[[str, float], None]


STAGES = [
    "low-cut", "humanize", "autotune", "saturation", "eq", "de-harsh",
    "gate", "compress", "air", "space", "width", "limit", "normalize",
]


def _noop(_stage: str, _frac: float) -> None:
    pass


def measure_lufs(audio: np.ndarray, sr: int) -> Optional[float]:
    if not _HAVE_PYLN:
        return None
    if audio.shape[0] < sr * 0.4:      # meter needs ~400ms
        return None
    meter = pyln.Meter(sr)
    try:
        return float(meter.integrated_loudness(audio))
    except Exception:
        return None


def process(
    audio: np.ndarray,
    sr: int,
    params: Params,
    progress: Optional[ProgressFn] = None,
) -> np.ndarray:
    """Run the full chain. `audio` is (n_samples, n_channels) float in [-1, 1]."""
    progress = progress or _noop
    x = np.asarray(audio, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] == 1:                # work in stereo so width/space apply
        x = np.repeat(x, 2, axis=1)

    s = params.strip
    total = len(STAGES)
    step = 0

    def tick(name):
        nonlocal step
        step += 1
        progress(name, step / total)

    # 1. Low-cut (high-pass) to clear sub rumble.
    x = filters.high_pass(x, sr, s.low_cut)
    tick("low-cut")

    # 2. Humanize: wow/flutter + micro-dynamic drift.
    if params.humanize > 0:
        x = effects.wow_flutter(x, sr, params.humanize)
        x = effects.micro_dynamics(x, sr, params.humanize)
    tick("humanize")

    # 3. Autotune (optional, gentle, vocal). Off by default.
    if params.autotune_enabled and params.autotune_strength > 0:
        x = _autotune.gentle_correct(
            x, sr, params.autotune_strength, params.autotune_key, params.autotune_scale
        )
    tick("autotune")

    # 4. Saturation (harmonic warmth).
    x = effects.saturate(x, s.saturation)
    tick("saturation")

    # 5. Tonal shaping — strip bells/shelves, then the 10-band graphic EQ.
    x = filters.low_shelf(x, sr, 45, s.deep)         # Deep (sub)
    x = filters.low_shelf(x, sr, 80, s.bass)         # Bass
    x = filters.peaking(x, sr, 800, s.mid, q=0.8)    # Mid
    x = filters.peaking(x, sr, 3000, s.clear, q=0.9) # Clear/clarity
    x = filters.peaking(x, sr, 5000, s.presence, q=1.0)  # Presence
    x = filters.high_shelf(x, sr, 8000, s.treble)    # Treble
    for f, g in zip(EQ_BANDS, params.eq):
        if f <= 60:
            x = filters.low_shelf(x, sr, f, g)
        elif f >= 10000:
            x = filters.high_shelf(x, sr, f, g)
        else:
            x = filters.peaking(x, sr, f, g, q=1.1)
    tick("eq")

    # 6. De-harsh: de-ess the sibilance band.
    x = effects.de_ess(x, sr, s.de_ess)
    tick("de-harsh")

    # 7. Gate the noise floor.
    x = effects.gate(x, sr, s.gate)
    tick("gate")

    # 8. Bus compression.
    x = effects.compress(x, sr, s.comp)
    tick("compress")

    # 9. Air shimmer.
    x = effects.air(x, sr, s.air)
    tick("air")

    # 10. Space: reverb + echo glue.
    x = effects.reverb(x, sr, s.reverb)
    x = effects.echo(x, sr, s.echo)
    tick("space")

    # 11. Stereo width.
    x = effects.stereo_width(x, s.width)
    tick("width")

    # 12. Output trim + true-peak limiter.
    if abs(s.gain) > 1e-4:
        x = x * (10 ** (s.gain / 20.0))
    x = effects.limiter(x, sr, s.limit, ceiling_db=params.true_peak_ceiling)
    tick("limit")

    # 13. LUFS normalize to target (if set), re-limited to hold the ceiling.
    if params.lufs_target is not None and _HAVE_PYLN:
        x = _normalize_lufs(x, sr, params.lufs_target, params.true_peak_ceiling)
    tick("normalize")

    return np.clip(x, -1.0, 1.0).astype(np.float32)


def _normalize_lufs(x: np.ndarray, sr: int, target: float, ceiling_db: float) -> np.ndarray:
    cur = measure_lufs(x, sr)
    if cur is None or not np.isfinite(cur):
        return x
    gain_db = target - cur
    x = x * (10 ** (gain_db / 20.0))
    # Gaining up can breach the true-peak ceiling; catch it with the limiter.
    ceiling = 10 ** (ceiling_db / 20.0)
    if np.max(np.abs(x)) > ceiling:
        x = effects.limiter(x, sr, drive_pct=0.0, ceiling_db=ceiling_db)
    return x
