"""
workers.py — QThread workers for Magic Studio.

Every worker here operates on LOCAL files on the user's own machine.
There is deliberately no network/session/cookie code: no uploading to
third-party services, no browser-session impersonation, no anti-detection
audio shifting, and no metadata spoofing. Long-running work (audio DSP,
analysis, tag writing) is pushed off the GUI thread so the UI never freezes.
"""

from __future__ import annotations

import os
import traceback

from PyQt6.QtCore import QThread, pyqtSignal

from modules import local_mastering, audio_analysis, tag_editor


class MasteringWorker(QThread):
    """Runs local loudness normalization + EQ on a queue of WAV files."""

    progress_signal = pyqtSignal(str, int)   # status message, percent (0-100)
    item_done_signal = pyqtSignal(str, str)  # input path, output path
    error_signal = pyqtSignal(str, str)      # input path, error message
    completion_signal = pyqtSignal(str)      # summary message

    def __init__(self, files, profile, output_format, out_dir=None, parent=None):
        super().__init__(parent)
        self.files = list(files)
        self.profile = profile
        self.output_format = output_format
        self.out_dir = out_dir
        self._running = True

    def run(self):
        total = len(self.files)
        if total == 0:
            self.completion_signal.emit("Nothing to master — queue is empty.")
            return

        done = 0
        for index, path in enumerate(self.files):
            if not self._running:
                break
            base = os.path.basename(path)
            pct = int((index / total) * 100)
            self.progress_signal.emit(f"Mastering: {base}", pct)
            try:
                out_path = local_mastering.master_file(
                    path,
                    profile=self.profile,
                    output_format=self.output_format,
                    out_dir=self.out_dir,
                )
                self.item_done_signal.emit(path, out_path)
                done += 1
            except Exception as err:  # noqa: BLE001 - surface to UI
                self.error_signal.emit(path, str(err))

        self.progress_signal.emit("Finished.", 100)
        self.completion_signal.emit(
            f"Mastered {done}/{total} file(s) locally."
        )

    def cancel(self):
        self._running = False


class AnalysisWorker(QThread):
    """Computes honest local audio stats (duration, LUFS, true peak, etc.)."""

    row_signal = pyqtSignal(str, dict)   # path, stats dict
    error_signal = pyqtSignal(str, str)  # path, error
    completion_signal = pyqtSignal(str)

    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.files = list(files)
        self._running = True

    def run(self):
        total = len(self.files)
        for path in self.files:
            if not self._running:
                break
            try:
                stats = audio_analysis.analyze_file(path)
                self.row_signal.emit(path, stats)
            except Exception as err:  # noqa: BLE001
                self.error_signal.emit(path, str(err))
        self.completion_signal.emit(f"Analyzed {total} file(s).")

    def cancel(self):
        self._running = False


class MetadataWorker(QThread):
    """Writes accurate tags + optional cover art to local files via mutagen."""

    row_signal = pyqtSignal(str, bool, str)  # path, ok, detail
    completion_signal = pyqtSignal(str)

    def __init__(self, files, tags, cover_path=None, options=None, parent=None):
        super().__init__(parent)
        self.files = list(files)
        self.tags = dict(tags)
        self.cover_path = cover_path
        self.options = options or {}
        self._running = True

    def run(self):
        ok_count = 0
        for path in self.files:
            if not self._running:
                break
            try:
                detail = tag_editor.write_tags(
                    path, self.tags, self.cover_path, self.options
                )
                self.row_signal.emit(path, True, detail)
                ok_count += 1
            except Exception as err:  # noqa: BLE001
                self.row_signal.emit(path, False, str(err))
        self.completion_signal.emit(
            f"Tagged {ok_count}/{len(self.files)} file(s)."
        )

    def cancel(self):
        self._running = False
