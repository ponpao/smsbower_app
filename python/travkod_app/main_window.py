"""TRAVKOD main window: assembles the panels and drives the DSP worker pool.

Batch processing runs on a QThreadPool sized to the user's Threads setting; each
file is a QRunnable calling the shared DSP core, streaming progress via signals.
Analysis, authenticity and A/B preview render on the global pool so they never
block the batch. All processing is local.
"""
from __future__ import annotations

import os
import tempfile
import uuid

from PyQt6.QtCore import Qt, QThreadPool, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFileDialog, QMessageBox,
)

from .state import (AppState, QueueItem, ExportSettings, PresetStore, SettingsStore,
                    default_output_dir)
from .theme import QSS, BG
from .widgets.title_bar import TitleBar
from .widgets.batch_queue import BatchQueue
from .widgets.setting_console import SettingConsole
from .widgets.transport_bar import TransportBar
from .widgets.status_bar import StatusBar
from .dialogs.export_dialog import ExportDialog
from .dialogs.release_dialog import ReleaseDialog
from .dialogs.authenticity_dialog import AuthenticityDialog
from .dialogs.first_run import FirstRunDialog
from .engine_worker import (TaskSignals, AnalyzeTask, ProcessTask, MergeProcessTask,
                            PreviewRenderTask, AuthTask)

AUDIO_EXTS = (".wav", ".flac", ".mp3", ".aif", ".aiff", ".ogg", ".m4a")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TRAVKOD")
        self.setMinimumSize(1040, 660)
        self.resize(1200, 760)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        self.state = AppState()
        self.presets = PresetStore()
        self.settings = SettingsStore()
        self._items = {}                    # id -> QueueItem
        self._active_tasks = {}             # id -> ProcessTask (for cancel)
        self.exporting = False
        self._last_out_dir = None
        self._preview_tmp = tempfile.mkdtemp(prefix="travkod_prev_")

        self.pool = QThreadPool()           # batch processing pool
        self.pool.setMaxThreadCount(self.state.export.threads)
        self.aux = QThreadPool.globalInstance()  # analysis / preview / auth

        # Shared signal hubs.
        self.sig_analyze = TaskSignals()
        self.sig_proc = TaskSignals()
        self.sig_preview = TaskSignals()
        self.sig_auth = TaskSignals()
        self.sig_analyze.analyzed.connect(self._on_analyzed)
        self.sig_analyze.failed.connect(self._on_analyze_failed)
        self.sig_proc.progress.connect(self._on_progress)
        self.sig_proc.finished.connect(self._on_finished)
        self.sig_proc.failed.connect(self._on_proc_failed)
        self.sig_preview.finished.connect(self._on_preview_ready)
        self.sig_auth.finished.connect(self._on_auth_ready)
        self.sig_auth.failed.connect(lambda _i, e: self._error("Authenticity", e))

        self._build_ui()
        self._shortcuts()

        # First-run honest-use notice.
        if not self.settings.load().get("first_run_ack"):
            QTimer.singleShot(200, self._show_first_run)

        # Debounced preview render on parameter changes.
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(600)
        self._preview_timer.timeout.connect(self._render_preview)

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        root.setStyleSheet(f"background:{BG};")
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.title_bar = TitleBar(self)
        lay.addWidget(self.title_bar)

        self.queue = BatchQueue()
        self.queue.setMinimumHeight(200)
        self.queue.addFilesRequested.connect(self.add_files)
        self.queue.addFolderRequested.connect(self.add_folder)
        self.queue.startExportRequested.connect(self.start_export)
        self.queue.stopExportRequested.connect(self.stop_export)
        self.queue.analyzeRequested.connect(self._reanalyze)
        self.queue.openOutputRequested.connect(self._open_output)
        self.queue.selectionChanged.connect(self._on_selection)
        lay.addWidget(self.queue, stretch=4)

        self.console = SettingConsole(self.state, self.presets)
        self.console.exportRequested.connect(self.open_export_dialog)
        self.console.analyzeAiRequested.connect(self.analyze_ai)
        self.console.humanizeToggled.connect(lambda _o: self._schedule_preview())
        self.console.paramsChanged.connect(self._schedule_preview)
        lay.addWidget(self.console, stretch=5)

        self.transport = TransportBar()
        self.transport.releaseCheckRequested.connect(self.release_check)
        self.transport.nextRequested.connect(self._play_next)
        lay.addWidget(self.transport)

        self.status = StatusBar()
        lay.addWidget(self.status)

        self.setCentralWidget(root)

    def _shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.transport.toggle_play)
        QShortcut(QKeySequence("Ctrl+E"), self, self.start_export)
        QShortcut(QKeySequence("Meta+E"), self, self.start_export)

    # ---- import -------------------------------------------------------
    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add audio files", "",
            "Audio (*.wav *.flac *.mp3 *.aif *.aiff *.ogg *.m4a)")
        self._add_paths(paths)

    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Add folder")
        if not d:
            return
        paths = []
        for base, _dirs, files in os.walk(d):
            for f in files:
                if f.lower().endswith(AUDIO_EXTS):
                    paths.append(os.path.join(base, f))
        self._add_paths(sorted(paths))

    def _add_paths(self, paths):
        existing = {it.path for it in self._items.values()}
        for p in paths:
            if p in existing:
                continue
            jid = uuid.uuid4().hex[:12]
            item = QueueItem(id=jid, path=p, filename=os.path.basename(p))
            self._items[jid] = item
            self.queue.add_item(item)
            self.aux.start(AnalyzeTask(jid, p, self.sig_analyze))
        self._refresh_status()

    def _reanalyze(self, jid: str):
        it = self._items.get(jid)
        if it:
            self.aux.start(AnalyzeTask(jid, it.path, self.sig_analyze))

    # ---- export -------------------------------------------------------
    def open_export_dialog(self):
        dlg = ExportDialog(self.state.export, self)
        dlg.setStyleSheet(QSS)
        if dlg.exec() and dlg.start:
            self.start_export()

    def _build_params(self) -> dict:
        p = self.state.params
        if self.state.humanize_on:
            d = p.to_dict()
            d["lufs_target"] = self.state.export.lufs_target
            d["autotune_enabled"] = self.state.export.autotune
            return d
        # Humanize & Master off: neutral params (normalize + safety limiter only).
        from travkod.params import Params
        neutral = Params()
        neutral.humanize = 0
        neutral.lufs_target = self.state.export.lufs_target
        for k in ("bass", "deep", "mid", "clear", "treble", "presence", "gate",
                  "de_ess", "air", "comp", "saturation", "reverb", "echo", "width", "gain"):
            setattr(neutral.strip, k, 0)
        return neutral.to_dict()

    def start_export(self):
        if self.exporting or not self._items:
            return
        out_dir = self.state.export.output_folder or default_output_dir()
        os.makedirs(out_dir, exist_ok=True)
        self._last_out_dir = out_dir
        params = self._build_params()
        exp = self.state.export.__dict__
        self.pool.setMaxThreadCount(self.state.export.threads)

        self.exporting = True
        self.queue.set_exporting(True)
        self._active_tasks.clear()

        items = list(self._items.values())
        if self.state.export.merge and len(items) > 1:
            for it in items:
                self._set_status(it.id, "Queued")
            base = os.path.join(out_dir, "TRAVKOD_merged")
            task = MergeProcessTask("merged", [i.path for i in items], base,
                                    params, exp, self.sig_proc)
            # merged progress mirrors onto all rows via _on_progress special-case
            self._merge_ids = [i.id for i in items]
            self.pool.start(task)
        else:
            self._merge_ids = None
            for it in items:
                self._set_status(it.id, "Queued")
                stem = os.path.splitext(it.filename)[0]
                base = os.path.join(out_dir, f"{stem}_travkod")
                task = ProcessTask(it.id, it.path, base, params, exp, self.sig_proc)
                self._active_tasks[it.id] = task
                self.pool.start(task)
        self._refresh_status()

    def stop_export(self):
        self.pool.clear()                    # drop not-yet-started jobs
        for t in self._active_tasks.values():
            t.cancel()
        self.exporting = False
        self.queue.set_exporting(False)
        for it in self._items.values():
            if it.status in ("Queued", "Processing"):
                self._set_status(it.id, "Paused")
        self._refresh_status()

    # ---- task callbacks ----------------------------------------------
    def _on_analyzed(self, jid, meta):
        if jid in self._items:
            self._items[jid].meta = meta
            self.queue.update_item(jid, meta=meta)

    def _on_analyze_failed(self, jid, err):
        self._set_status(jid, "Error", error=err)

    def _on_progress(self, jid, stage, frac):
        ids = self._merge_ids if (jid == "merged" and self._merge_ids) else [jid]
        for i in ids:
            if i in self._items:
                self._items[i].status = "Processing"
                self._items[i].progress = frac
                self._items[i].stage = stage
                self.queue.update_item(i, status="Processing", progress=frac, stage=stage)

    def _on_finished(self, jid, result):
        ids = self._merge_ids if (jid == "merged" and self._merge_ids) else [jid]
        for i in ids:
            self._set_status(i, "Done", output_path=result.get("output_path"))
        self._active_tasks.pop(jid, None)
        self._check_done()

    def _on_proc_failed(self, jid, err):
        ids = self._merge_ids if (jid == "merged" and self._merge_ids) else [jid]
        for i in ids:
            self._set_status(i, "Error", error=err)
        self._active_tasks.pop(jid, None)
        self._check_done()

    def _check_done(self):
        if not any(it.status in ("Queued", "Processing") for it in self._items.values()):
            self.exporting = False
            self.queue.set_exporting(False)
        self._refresh_status()

    # ---- selection / preview / playback -------------------------------
    def _on_selection(self, jid):
        it = self._items.get(jid)
        if not it:
            return
        self.transport.set_sources(it.path, None)
        self._schedule_preview()

    def _schedule_preview(self):
        self._preview_timer.start()

    def _render_preview(self):
        jid = self.queue.current_id()
        it = self._items.get(jid) if jid else None
        if not it or self.exporting:
            return
        out = os.path.join(self._preview_tmp, f"{it.id}.wav")
        self.aux.start(PreviewRenderTask(it.id, it.path, out, self._build_params(),
                                         self.sig_preview))

    def _on_preview_ready(self, _jid, result):
        self.transport.set_processed(result.get("output_path"))

    def _play_next(self):
        ids = list(self._items.keys())
        cur = self.queue.current_id()
        if cur in ids:
            nxt = ids[(ids.index(cur) + 1) % len(ids)]
            self.queue.table.selectRow(list(self._items).index(nxt))

    # ---- authenticity / release --------------------------------------
    def analyze_ai(self):
        jid = self.queue.current_id()
        it = self._items.get(jid) if jid else None
        if not it:
            self._info("Analyze AI", "Select a track first.")
            return
        self._auth_for = jid
        self.aux.start(AuthTask(jid, it.path, self.sig_auth))

    def _on_auth_ready(self, jid, report):
        it = self._items.get(jid)
        if not it:
            return
        dlg = AuthenticityDialog(report, it.is_ai, self)
        dlg.setStyleSheet(QSS)
        dlg.exec()
        it.is_ai = dlg.result_is_ai

    def release_check(self):
        jid = self.queue.current_id()
        it = self._items.get(jid) if jid else None
        meta = it.meta if it else None
        dlg = ReleaseDialog(meta, self.state.export.lufs_target,
                            it.is_ai if it else False, self)
        dlg.setStyleSheet(QSS)
        dlg.exec()

    # ---- helpers ------------------------------------------------------
    def _set_status(self, jid, status, **extra):
        it = self._items.get(jid)
        if not it:
            return
        it.status = status
        for k, v in extra.items():
            setattr(it, k, v)
        if status != "Processing":
            it.progress = 1.0 if status == "Done" else 0.0
        self.queue.update_item(jid, status=status, **extra)
        self._refresh_status()

    def _refresh_status(self):
        total = len(self._items)
        done = sum(1 for it in self._items.values() if it.status == "Done")
        self.status.set_status(self.exporting, done, total)

    def _open_output(self):
        d = self._last_out_dir or self.state.export.output_folder
        if d and os.path.isdir(d):
            self._open_path(d)

    @staticmethod
    def _open_path(path):
        import subprocess, sys
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])

    def _show_first_run(self):
        dlg = FirstRunDialog(self)
        dlg.setStyleSheet(QSS)
        dlg.exec()
        self.settings.set("first_run_ack", True)

    def closeEvent(self, e):
        # Stop accepting work and let in-flight tasks finish before the window
        # (which owns the signal hubs) is torn down, so no task emits into a
        # deleted object.
        self.pool.clear()
        for t in self._active_tasks.values():
            t.cancel()
        self.pool.waitForDone(3000)
        self.aux.waitForDone(3000)
        super().closeEvent(e)

    def _info(self, title, msg):
        QMessageBox.information(self, title, msg)

    def _error(self, title, msg):
        QMessageBox.warning(self, title, msg[:400])
