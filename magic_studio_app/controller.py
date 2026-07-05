"""
controller.py — Main window controller.

Owns the frameless QMainWindow, applies the stylesheet, polls CPU/RAM for the
title bar, and wires every panel's buttons to the local QThread workers. No
network, session, or provenance logic lives anywhere in this app.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QTableWidgetItem, QListWidgetItem, QMessageBox,
)

from views.main_window_ui import MainWindowUI
from workers import MasteringWorker, AnalysisWorker, MetadataWorker

try:
    import psutil
    _HAVE_PSUTIL = True
except Exception:  # noqa: BLE001
    _HAVE_PSUTIL = False

AUDIO_FILTER = "Audio (*.wav *.flac *.mp3 *.m4a *.aac *.ogg);;All files (*.*)"


class MainController(QMainWindow):
    def __init__(self, stylesheet=""):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(980, 640)

        self.ui = MainWindowUI()
        self.setCentralWidget(self.ui)
        if stylesheet:
            self.setStyleSheet(stylesheet)

        self._threads = []          # keep worker refs alive
        self._cover_path = None

        self._wire_titlebar()
        self._wire_master_tab()
        self._wire_batch_tab()
        self._wire_analysis_tab()
        self._wire_metadata_tab()
        self._wire_settings_tab()
        self._start_stats_timer()

    # ---------- title bar & window controls ----------
    def _wire_titlebar(self):
        tb = self.ui.title_bar
        tb.minimizeClicked.connect(self.showMinimized)
        tb.maximizeClicked.connect(self._toggle_max)
        tb.closeClicked.connect(self.close)

    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _start_stats_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_stats)
        self._timer.start(2000)
        self._update_stats()

    def _update_stats(self):
        if _HAVE_PSUTIL:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            self.ui.title_bar.stats_lbl.setText(f"CPU: {cpu:.0f}% | RAM: {ram:.0f}%")
        else:
            self.ui.title_bar.stats_lbl.setText("CPU: – | RAM: –  (pip install psutil)")

    # ---------- shared helpers ----------
    def _pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select audio files", "",
                                                AUDIO_FILTER)
        return files

    @staticmethod
    def _list_paths(listw):
        return [listw.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(listw.count())]

    @staticmethod
    def _add_to_list(listw, paths):
        existing = {listw.item(i).data(Qt.ItemDataRole.UserRole)
                    for i in range(listw.count())}
        for p in paths:
            if p and p not in existing:
                item = QListWidgetItem(os.path.basename(p))
                item.setData(Qt.ItemDataRole.UserRole, p)
                listw.addItem(item)

    # ---------- Tab 1: Local Master ----------
    def _wire_master_tab(self):
        u = self.ui
        u.m_add.clicked.connect(lambda: self._add_to_list(u.m_list, self._pick_files()))
        u.m_drop.filesDropped.connect(lambda p: self._add_to_list(u.m_list, p))
        u.m_drop.browse_btn.clicked.connect(
            lambda: self._add_to_list(u.m_list, self._pick_files()))
        u.m_remove.clicked.connect(lambda: self._remove_selected(u.m_list))
        u.m_run.clicked.connect(self._run_master)

    def _run_master(self):
        u = self.ui
        paths = self._list_paths(u.m_list)
        if not paths:
            return self._warn("Add files to the queue first.")
        self._start_mastering(paths, "neutral",
                              "Ultra HD (24-bit 48kHz WAV)",
                              u.m_progress, u.m_status, u.m_run)

    def _remove_selected(self, listw):
        for item in listw.selectedItems():
            listw.takeItem(listw.row(item))

    # ---------- Tab 2: Batch Master ----------
    def _wire_batch_tab(self):
        u = self.ui
        u.b_add.clicked.connect(lambda: self._add_to_list(u.b_list, self._pick_files()))
        u.b_drop.filesDropped.connect(lambda p: self._add_to_list(u.b_list, p))
        u.b_drop.browse_btn.clicked.connect(
            lambda: self._add_to_list(u.b_list, self._pick_files()))
        u.b_remove.clicked.connect(lambda: self._remove_selected(u.b_list))
        u.b_run.clicked.connect(self._run_batch)
        u.b_start.clicked.connect(self._run_batch)

    def _run_batch(self):
        u = self.ui
        paths = self._list_paths(u.b_list)
        if not paths:
            return self._warn("Add files to the queue first.")
        self._start_mastering(paths, u.b_profile.currentText(),
                              u.b_format.currentText(),
                              u.b_progress, u.b_status, u.b_start)

    def _start_mastering(self, paths, profile, fmt, progress, status, trigger):
        out_dir = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if not out_dir:
            return
        trigger.setEnabled(False)
        worker = MasteringWorker(paths, profile, fmt, out_dir=out_dir)
        worker.progress_signal.connect(
            lambda msg, pct: (progress.setValue(pct), status.setText(msg)))
        worker.item_done_signal.connect(
            lambda src, dst: status.setText(f"Wrote {os.path.basename(dst)}"))
        worker.error_signal.connect(
            lambda src, err: status.setText(f"Error on {os.path.basename(src)}: {err}"))
        worker.completion_signal.connect(
            lambda msg: (status.setText(msg), trigger.setEnabled(True)))
        self._run_worker(worker)

    # ---------- Tab 3: Audio Analysis ----------
    def _wire_analysis_tab(self):
        u = self.ui
        u.a_add.clicked.connect(self._run_analysis)
        u.a_clear.clicked.connect(lambda: u.a_table.setRowCount(0))

    def _run_analysis(self):
        u = self.ui
        paths = self._pick_files()
        if not paths:
            return
        u.a_status.setText("Analyzing…")
        worker = AnalysisWorker(paths)
        worker.row_signal.connect(self._add_analysis_row)
        worker.error_signal.connect(
            lambda p, e: u.a_status.setText(f"Error: {os.path.basename(p)}: {e}"))
        worker.completion_signal.connect(u.a_status.setText)
        self._run_worker(worker)

    def _add_analysis_row(self, path, stats):
        t = self.ui.a_table
        r = t.rowCount()
        t.insertRow(r)
        for col, key in enumerate(
                ["filename", "duration", "lufs", "true_peak", "rms", "samplerate"]):
            t.setItem(r, col, QTableWidgetItem(str(stats.get(key, ""))))

    # ---------- Tab 4: Metadata ----------
    def _wire_metadata_tab(self):
        u = self.ui
        u.md_add.clicked.connect(lambda: self._md_add(self._pick_files()))
        u.md_clear.clicked.connect(lambda: u.md_table.setRowCount(0))
        u.md_write.clicked.connect(self._run_metadata)
        self._md_paths = []

    def _md_add(self, paths):
        t = self.ui.md_table
        for p in paths:
            if not p or p in self._md_paths:
                continue
            self._md_paths.append(p)
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, QTableWidgetItem(os.path.basename(p)))
            t.setItem(r, 1, QTableWidgetItem("Queued"))
            t.setItem(r, 2, QTableWidgetItem(""))

    def _run_metadata(self):
        u = self.ui
        if not u.s_enable_injection.isChecked():
            return self._warn("Enable metadata writing in Settings first.")
        if not self._md_paths:
            return self._warn("Add files to the metadata queue first.")
        tags = self._collect_tags()
        options = {
            "force_uppercase": u.s_uppercase.isChecked(),
            "remove_track_numbers": u.s_striptrack.isChecked(),
        }
        u.md_status.setText("Writing tags…")
        worker = MetadataWorker(self._md_paths, tags, self._cover_path, options)
        worker.row_signal.connect(self._md_row_result)
        worker.completion_signal.connect(u.md_status.setText)
        self._run_worker(worker)

    def _md_row_result(self, path, ok, detail):
        t = self.ui.md_table
        base = os.path.basename(path)
        for r in range(t.rowCount()):
            if t.item(r, 0) and t.item(r, 0).text() == base:
                t.setItem(r, 1, QTableWidgetItem("OK" if ok else "Failed"))
                t.setItem(r, 2, QTableWidgetItem(detail))
                break

    def _collect_tags(self):
        u = self.ui
        return {
            "artist": u.s_artist.text(),
            "album": u.s_album.text(),
            "date": u.s_year.text(),
            "genre": u.s_genre.text(),
            "engineer": u.s_engineer.text(),
            "copyright": u.s_copyright.text(),
            "encoder": u.s_encoder.text(),
            "source": u.s_source.text(),
            "comment": u.s_comment.toPlainText(),
        }

    # ---------- Tab 5: Settings ----------
    def _wire_settings_tab(self):
        u = self.ui
        u.s_cover_browse.clicked.connect(self._pick_cover)
        u.s_cover_clear.clicked.connect(self._clear_cover)
        u.s_apply.clicked.connect(
            lambda: u.md_status.setText("Settings applied."))

    def _pick_cover(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select cover image", "", "Images (*.png *.jpg *.jpeg)")
        if not path:
            return
        self._cover_path = path
        self.ui.s_cover_path.setText(path)
        pix = QPixmap(path)
        if not pix.isNull():
            self.ui.s_cover_preview.setPixmap(
                pix.scaledToHeight(84, Qt.TransformationMode.SmoothTransformation))
            self.ui.s_cover_preview.setText("")

    def _clear_cover(self):
        self._cover_path = None
        self.ui.s_cover_path.clear()
        self.ui.s_cover_preview.setPixmap(QPixmap())
        self.ui.s_cover_preview.setText("No cover")

    # ---------- worker lifecycle ----------
    def _run_worker(self, worker):
        self._threads.append(worker)
        worker.finished.connect(lambda: self._threads.remove(worker)
                                if worker in self._threads else None)
        worker.start()

    def _warn(self, msg):
        QMessageBox.information(self, "Magic Studio", msg)

    def closeEvent(self, event):
        for w in list(self._threads):
            if w.isRunning():
                if hasattr(w, "cancel"):
                    w.cancel()
                w.wait(1500)
        event.accept()
