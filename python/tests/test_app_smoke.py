"""Headless functional smoke test for the PyQt6 app's batch path.

Runs offscreen (QT_QPA_PLATFORM=offscreen). Adds a folder of files, starts an
export through the real QThreadPool worker pool, spins the event loop until the
queue drains, and asserts every file exported at the LUFS target with true-peak
under the ceiling. This exercises the same code the GUI uses.
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import soundfile as sf
from PyQt6.QtWidgets import QApplication

from travkod_app.main_window import MainWindow
from travkod_app.theme import QSS


def _make_files(d, n=16, sr=44100):
    os.makedirs(d, exist_ok=True)
    rng = np.random.default_rng(0)
    paths = []
    for i in range(n):
        secs = 3.0 + rng.random() * 1.5
        t = np.arange(int(sr * secs)) / sr
        f0 = 180 + i * 12
        sig = (0.3 * np.sin(2 * np.pi * f0 * t) + 0.2 * np.sin(2 * np.pi * f0 * 8 * t)
               + 0.12 * np.sin(2 * np.pi * 7000 * t) + 0.02 * rng.standard_normal(t.size))
        st = np.stack([sig, sig * 0.98], axis=1).astype(np.float32)
        st /= np.max(np.abs(st)) + 1e-9
        p = os.path.join(d, f"track_{i:02d}.wav")
        sf.write(p, st * 0.9, sr, subtype="PCM_24")
        paths.append(p)
    return paths


def _pump(app, predicate, timeout=90):
    t0 = time.time()
    while not predicate() and time.time() - t0 < timeout:
        # Safety net: dismiss any modal dialog so headless runs never block.
        m = app.activeModalWidget()
        if m is not None:
            m.close()
        app.processEvents()
        time.sleep(0.02)
    return predicate()


def main():
    import tempfile
    indir = tempfile.mkdtemp(prefix="tk_in_")
    outdir = tempfile.mkdtemp(prefix="tk_out_")
    paths = _make_files(indir, n=16)

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(QSS)

    # Pre-acknowledge the first-run notice so its modal doesn't block the
    # headless run (a real user just clicks "Got it").
    from travkod_app.state import SettingsStore
    SettingsStore().set("first_run_ack", True)

    win = MainWindow()
    win.state.export.output_folder = outdir
    win.state.export.threads = 4
    win.state.export.lufs_target = -14.0
    win.state.params.strip.de_ess = 40
    win.state.params.strip.comp = 25
    win.state.params.humanize = 40

    win._add_paths(paths)
    assert _pump(app, lambda: all(it.meta for it in win._items.values()), 60), "analysis timed out"
    print(f"analyzed {len(win._items)} files; sample key = "
          f"{next(iter(win._items.values())).meta['key']}")

    win.start_export()
    ok = _pump(app, lambda: all(it.status in ("Done", "Error") for it in win._items.values()), 120)
    assert ok, "export timed out"

    done = [it for it in win._items.values() if it.status == "Done"]
    errors = [it for it in win._items.values() if it.status == "Error"]
    assert not errors, f"errors: {[e.error for e in errors][:2]}"
    assert len(done) == 16, f"only {len(done)}/16 done"

    # Verify outputs on disk hit the acceptance criteria.
    import pyloudnorm as pyln
    from travkod import analyze as an
    off, over, missing = 0, 0, 0
    for it in done:
        if not it.output_path or not os.path.exists(it.output_path):
            missing += 1
            continue
        audio, sr = sf.read(it.output_path, always_2d=True)
        lufs = pyln.Meter(sr).integrated_loudness(audio)
        tp = an.true_peak_dbtp(audio, sr)
        if abs(lufs + 14) > 0.5:
            off += 1
        if tp > -1 + 1e-6:
            over += 1
    print(f"exported {len(done)} files -> {outdir}")
    print(f"missing outputs: {missing} | LUFS off-target: {off} | true-peak over -1 dBTP: {over}")
    assert missing == 0 and off == 0 and over == 0

    # Release check + authenticity run without error.
    from travkod import release, authenticity
    sample = done[0]
    rc = release.check(sample.meta, lufs_target=-14.0, is_ai=True)
    assert any(i["name"] == "AI disclosure" for i in rc["items"])
    rep = authenticity.analyze(sample.path)
    assert rep["ci_low"] <= rep["p_ai"] <= rep["ci_high"]

    print("APP SMOKE: PASS")


if __name__ == "__main__":
    main()
