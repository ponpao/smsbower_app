"""Background tasks driving the shared DSP core from the PyQt6 UI.

Everything runs in one Python process: the batch queue is a QThreadPool and each
file is a QRunnable that calls ``travkod.humanize_master.process`` directly,
streaming progress back to the UI through Qt signals. The user's "Threads"
setting maps to the pool size (1-8).

All processing is local; nothing leaves the machine.
"""
from __future__ import annotations

import os
import traceback
from typing import Optional

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from travkod import analyze as analyze_mod
from travkod import authenticity as auth_mod
from travkod import io_export
from travkod import humanize_master as engine
from travkod.params import Params


class TaskSignals(QObject):
    progress = pyqtSignal(str, str, float)      # job_id, stage, frac
    analyzed = pyqtSignal(str, dict)            # job_id, meta
    finished = pyqtSignal(str, dict)            # job_id, result
    failed = pyqtSignal(str, str)               # job_id, error


class AnalyzeTask(QRunnable):
    def __init__(self, job_id: str, path: str, signals: TaskSignals):
        super().__init__()
        self.job_id, self.path, self.signals = job_id, path, signals

    def run(self):
        try:
            meta = analyze_mod.analyze_file(self.path)
            self.signals.analyzed.emit(self.job_id, meta)
        except Exception as e:  # noqa: BLE001
            self.signals.failed.emit(self.job_id, str(e))


class AuthTask(QRunnable):
    def __init__(self, job_id: str, path: str, signals: TaskSignals):
        super().__init__()
        self.job_id, self.path, self.signals = job_id, path, signals

    def run(self):
        try:
            self.signals.finished.emit(self.job_id, auth_mod.analyze(self.path))
        except Exception as e:  # noqa: BLE001
            self.signals.failed.emit(self.job_id, str(e))


class ProcessTask(QRunnable):
    """Humanize + master one file, then export it."""

    def __init__(self, job_id: str, input_path: str, output_base: str,
                 params: dict, export: dict, signals: TaskSignals):
        super().__init__()
        self.job_id = job_id
        self.input_path = input_path
        self.output_base = output_base
        self.params = params
        self.export = export
        self.signals = signals
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self._cancelled:
                return
            audio, sr = io_export.read_audio(self.input_path)
            params = Params.from_dict(self.params)

            def prog(stage, frac):
                if not self._cancelled:
                    self.signals.progress.emit(self.job_id, stage, frac)

            processed = engine.process(audio, sr, params, progress=prog)
            if self._cancelled:
                return

            out_path = io_export.export(
                processed, sr, self.output_base,
                fmt=self.export.get("format", "wav"),
                bit_depth=int(self.export.get("bit_depth", 24)),
                target_sr=self.export.get("sample_rate"),
                mp3_bitrate=int(self.export.get("mp3_bitrate", 320)),
            )
            lufs = engine.measure_lufs(processed, sr)
            tp = analyze_mod.true_peak_dbtp(processed, sr)
            self.signals.finished.emit(self.job_id, {
                "output_path": out_path,
                "loudness_lufs": None if lufs is None else round(lufs, 1),
                "true_peak_dbtp": tp,
            })
        except Exception as e:  # noqa: BLE001
            self.signals.failed.emit(self.job_id, f"{e}\n{traceback.format_exc()}")


class MergeProcessTask(QRunnable):
    """Merge > One File: concatenate inputs, process the whole, export once."""

    def __init__(self, job_id: str, inputs, output_base: str,
                 params: dict, export: dict, signals: TaskSignals, gap_s: float = 0.0):
        super().__init__()
        self.job_id, self.inputs, self.output_base = job_id, inputs, output_base
        self.params, self.export, self.signals, self.gap_s = params, export, signals, gap_s

    def run(self):
        try:
            clips = [io_export.read_audio(p) for p in self.inputs]
            base_sr = clips[0][1]
            merged = io_export.concat(clips, base_sr, gap_s=self.gap_s)
            params = Params.from_dict(self.params)
            processed = engine.process(
                merged, base_sr, params,
                progress=lambda s, f: self.signals.progress.emit(self.job_id, s, f),
            )
            out_path = io_export.export(
                processed, base_sr, self.output_base,
                fmt=self.export.get("format", "wav"),
                bit_depth=int(self.export.get("bit_depth", 24)),
                target_sr=self.export.get("sample_rate"),
                mp3_bitrate=int(self.export.get("mp3_bitrate", 320)),
            )
            lufs = engine.measure_lufs(processed, base_sr)
            tp = analyze_mod.true_peak_dbtp(processed, base_sr)
            self.signals.finished.emit(self.job_id, {
                "output_path": out_path, "merged_count": len(self.inputs),
                "loudness_lufs": None if lufs is None else round(lufs, 1),
                "true_peak_dbtp": tp,
            })
        except Exception as e:  # noqa: BLE001
            self.signals.failed.emit(self.job_id, str(e))


class PreviewRenderTask(QRunnable):
    """Render a short processed preview (for the A/B Effect toggle)."""

    def __init__(self, job_id: str, input_path: str, out_path: str,
                 params: dict, signals: TaskSignals, seconds: float = 20.0):
        super().__init__()
        self.job_id, self.input_path, self.out_path = job_id, input_path, out_path
        self.params, self.signals, self.seconds = params, signals, seconds

    def run(self):
        try:
            audio, sr = io_export.read_audio(self.input_path)
            n = min(audio.shape[0], int(sr * self.seconds))
            processed = engine.process(audio[:n], sr, Params.from_dict(self.params))
            io_export.export(processed, sr, os.path.splitext(self.out_path)[0],
                             fmt="wav", bit_depth=16)
            self.signals.finished.emit(self.job_id, {"output_path": self.out_path})
        except Exception as e:  # noqa: BLE001
            self.signals.failed.emit(self.job_id, str(e))
