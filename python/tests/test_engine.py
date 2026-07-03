"""End-to-end DSP checks against the acceptance criteria.

  * LUFS target hit within +/-0.5 LU.
  * True peak <= -1 dBTP.
  * Warmth: harsh high-frequency energy is reduced by the de-harsh chain.
"""
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from travkod import humanize_master as engine          # noqa: E402
from travkod import analyze as analyze_mod              # noqa: E402
from travkod.params import Params, MasterStrip          # noqa: E402
import pyloudnorm as pyln                                # noqa: E402


def _harsh_track(sr=44100, secs=6.0):
    """Bright, brittle, quantized-sounding stereo test signal."""
    n = int(sr * secs)
    t = np.arange(n) / sr
    rng = np.random.default_rng(42)
    tone = 0.2 * np.sin(2 * np.pi * 220 * t)            # body
    harsh = 0.25 * np.sin(2 * np.pi * 3500 * t)         # brittle presence
    fizz = 0.15 * np.sin(2 * np.pi * 8000 * t)          # harsh air
    sig = tone + harsh + fizz + 0.02 * rng.standard_normal(n)
    stereo = np.stack([sig, sig * 0.98], axis=1).astype(np.float32)
    stereo /= np.max(np.abs(stereo)) + 1e-9
    return stereo * 0.9, sr


def _hf_energy(audio, sr, f_lo=3000):
    mono = audio.mean(axis=1)
    mag = np.abs(np.fft.rfft(mono)) ** 2
    freqs = np.fft.rfftfreq(mono.shape[0], 1.0 / sr)
    return float(mag[freqs > f_lo].sum() / (mag.sum() + 1e-12))


def test_lufs_target_and_true_peak():
    audio, sr = _harsh_track()
    params = Params(
        strip=MasterStrip(de_ess=45, clear=-2.5, saturation=25, comp=25,
                          air=6, treble=-1.0, limit=85),
        humanize=40, lufs_target=-14.0, true_peak_ceiling=-1.0,
    )
    out = engine.process(audio, sr, params)

    lufs = pyln.Meter(sr).integrated_loudness(out)
    assert abs(lufs - (-14.0)) <= 0.5, f"LUFS {lufs} not within 0.5 of -14"

    tp = analyze_mod.true_peak_dbtp(out, sr)
    assert tp <= -1.0 + 1e-6, f"true peak {tp} exceeds -1 dBTP"


def test_deharsh_reduces_high_frequency_harshness():
    audio, sr = _harsh_track()
    params = Params(
        strip=MasterStrip(de_ess=60, clear=-3.0, presence=-2.0, saturation=30,
                          treble=-2.0),
        humanize=30, lufs_target=None,
    )
    out = engine.process(audio, sr, params)
    # Compare HF *proportion* so the loudness match doesn't skew the ratio.
    before = _hf_energy(audio, sr)
    after = _hf_energy(out, sr)
    assert after < before, f"HF proportion not reduced: {before} -> {after}"


def test_off_target_leaves_loudness_alone():
    audio, sr = _harsh_track()
    params = Params(strip=MasterStrip(limit=85), humanize=0, lufs_target=None)
    out = engine.process(audio, sr, params)
    assert np.max(np.abs(out)) <= 10 ** (-1.0 / 20.0) + 1e-3


def test_mono_input_becomes_stereo():
    audio, sr = _harsh_track()
    mono = audio.mean(axis=1, keepdims=True)
    out = engine.process(mono, sr, Params(lufs_target=None))
    assert out.shape[1] == 2


def test_processing_is_fast_enough_for_batch():
    """Guards against O(n*k) regressions (e.g. large-kernel np.convolve).

    A ~6s track must process well under real-time so a 15+ file batch stays
    responsive across the worker pool.
    """
    import time
    audio, sr = _harsh_track(secs=6.0)
    params = Params(strip=MasterStrip(de_ess=40, comp=25, saturation=25, limit=85),
                    humanize=60, lufs_target=-14.0)
    t0 = time.time()
    engine.process(audio, sr, params)
    elapsed = time.time() - t0
    assert elapsed < 6.0, f"processing a 6s file took {elapsed:.1f}s (too slow)"


def test_analyze_and_release_check(tmp_path=None):
    import tempfile, os
    from travkod import analyze as an
    from travkod import release as rel
    audio, sr = _harsh_track(secs=3.0)
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.wav")
    sf.write(p, audio, sr, subtype="PCM_24")
    meta = an.analyze_file(p)
    assert meta["channels"] == 2 and meta["sample_rate"] == sr
    assert meta["bit_depth"] == 24 and meta["key"] != ""
    check = rel.check(meta, lufs_target=-14.0, is_ai=True)
    # AI source must add a disclosure reminder (never a bypass).
    assert any(i["name"] == "AI disclosure" for i in check["items"])


def test_authenticity_reports_interval_not_certainty():
    import tempfile, os
    from travkod import authenticity as auth
    audio, sr = _harsh_track(secs=3.0)
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.wav")
    sf.write(p, audio, sr, subtype="PCM_24")
    rep = auth.analyze(p)
    assert rep["beta"] is True
    assert rep["ci_low"] <= rep["p_ai"] <= rep["ci_high"]
    assert rep["ci_high"] > rep["ci_low"], "must report a range, not a single number"


if __name__ == "__main__":
    test_lufs_target_and_true_peak()
    test_deharsh_reduces_high_frequency_harshness()
    test_off_target_leaves_loudness_alone()
    test_mono_input_becomes_stereo()
    test_processing_is_fast_enough_for_batch()
    test_analyze_and_release_check()
    test_authenticity_reports_interval_not_certainty()
    print("all engine tests passed")
