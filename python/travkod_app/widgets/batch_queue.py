"""Batch Queue panel: metadata table + right-click menu.

Columns: #, Filename, Duration, Type, Key/Major, Sample Rate/Bits, Loudness,
True Peak, Channels, Status. Owns the list of QueueItem rows; the main window
listens to its signals to add files, analyze, and start/stop the export.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QProgressBar, QAbstractItemView,
)

from ..state import QueueItem
from ..theme import TEXT_MUTED, TEXT, TEXT_DIM, ACCENT, GOOD, WARN, BAD
from ..i18n import tr, I18N

COLUMN_KEYS = ["col.no", "col.filename", "col.duration", "col.type", "col.key",
               "col.samplerate", "col.loudness", "col.truepeak", "col.channels",
               "col.status"]

STATUS_COLOR = {
    "Idle": TEXT_DIM, "Queued": WARN, "Processing": ACCENT,
    "Done": GOOD, "Error": BAD, "Paused": TEXT_MUTED,
}


class BatchQueue(QWidget):
    addFilesRequested = pyqtSignal()
    addFolderRequested = pyqtSignal()
    startExportRequested = pyqtSignal()
    stopExportRequested = pyqtSignal()
    analyzeRequested = pyqtSignal(str)
    openOutputRequested = pyqtSignal()
    selectionChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.items: List[QueueItem] = []
        self._row_by_id: Dict[str, int] = {}
        self.exporting = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 6)
        root.setSpacing(6)

        header = QHBoxLayout()
        self.title = QLabel()
        self.title.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; letter-spacing:2px; font-weight:600;")
        header.addWidget(self.title)
        header.addStretch(1)
        self.btn_files = QPushButton()
        self.btn_folder = QPushButton()
        self.btn_export = QPushButton()
        self.btn_export.setProperty("accent", True)
        self.btn_files.clicked.connect(self.addFilesRequested)
        self.btn_folder.clicked.connect(self.addFolderRequested)
        self.btn_export.clicked.connect(self._toggle_export)
        for b in (self.btn_files, self.btn_folder, self.btn_export):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            header.addWidget(b)
        root.addLayout(header)

        self.table = QTableWidget(0, len(COLUMN_KEYS))
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.table.setShowGrid(False)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3, 4, 5, 6, 7, 8, 9):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table)

        I18N.changed.connect(self._retranslate)
        self._retranslate()

    # ---- i18n ---------------------------------------------------------
    def _retranslate(self):
        self.title.setText(tr("queue.title"))
        self.btn_files.setText(tr("btn.files"))
        self.btn_folder.setText(tr("btn.folder"))
        self.btn_export.setText(tr("btn.stop") if self.exporting else tr("btn.startExport"))
        self.table.setHorizontalHeaderLabels([tr(k) for k in COLUMN_KEYS])
        for row in range(len(self.items)):
            self._render_row(row)

    # ---- public API ---------------------------------------------------
    def add_item(self, item: QueueItem):
        self.items.append(item)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._row_by_id[item.id] = row
        self._render_row(row)

    def update_item(self, item_id: str, **changes):
        for it in self.items:
            if it.id == item_id:
                for k, v in changes.items():
                    setattr(it, k, v)
                self._render_row(self._row_by_id[item_id])
                break

    def set_exporting(self, on: bool):
        self.exporting = on
        self.btn_export.setText(tr("btn.stop") if on else tr("btn.startExport"))
        self.btn_export.setProperty("accent", not on)
        self.btn_export.setProperty("danger", on)
        self.btn_export.style().unpolish(self.btn_export)
        self.btn_export.style().polish(self.btn_export)

    def selected_ids(self) -> List[str]:
        rows = {i.row() for i in self.table.selectedIndexes()}
        return [self.items[r].id for r in sorted(rows) if r < len(self.items)]

    def current_id(self) -> Optional[str]:
        ids = self.selected_ids()
        return ids[0] if ids else (self.items[0].id if self.items else None)

    def clear_all(self):
        self.items.clear()
        self._row_by_id.clear()
        self.table.setRowCount(0)

    def remove_selected(self):
        ids = set(self.selected_ids())
        self.items = [i for i in self.items if i.id not in ids]
        self._rebuild()

    # ---- rendering ----------------------------------------------------
    def _rebuild(self):
        self.table.setRowCount(0)
        self._row_by_id.clear()
        for idx, it in enumerate(self.items):
            self.table.insertRow(idx)
            self._row_by_id[it.id] = idx
            self._render_row(idx)

    def _cell(self, text: str, color: str = TEXT):
        from PyQt6.QtGui import QColor
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        return item

    def _render_row(self, row: int):
        it = self.items[row]
        m = it.meta or {}
        vals = [
            str(row + 1),
            it.filename,
            m.get("duration_str", "—"),
            m.get("type", "—"),
            m.get("key", "—"),
            (f"{m['sample_rate']/1000:.1f}k / {m.get('bit_depth') or '—'}bit"
             if m.get("sample_rate") else "—"),
            (f"{m['loudness_lufs']} LUFS" if m.get("loudness_lufs") is not None else "—"),
            (f"{m['true_peak_dbtp']} dB" if m.get("true_peak_dbtp") is not None else "—"),
            m.get("channel_label", "—"),
        ]
        colors = [TEXT_DIM, TEXT, TEXT_MUTED, TEXT_MUTED, TEXT_MUTED,
                  TEXT_MUTED, TEXT_MUTED, TEXT_MUTED, TEXT_MUTED]
        for c, (v, col) in enumerate(zip(vals, colors)):
            self.table.setItem(row, c, self._cell(v, col))

        if it.status == "Processing":
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(it.progress * 100))
            bar.setTextVisible(False)
            bar.setFixedWidth(120)
            self.table.setCellWidget(row, 9, bar)
        else:
            self.table.removeCellWidget(row, 9)
            label = tr(f"status.{it.status}")
            if it.status == "Error" and it.error:
                label += f" · {it.error[:24]}"
            self.table.setItem(row, 9, self._cell(label, STATUS_COLOR.get(it.status, TEXT)))

    # ---- events -------------------------------------------------------
    def _toggle_export(self):
        self.stopExportRequested.emit() if self.exporting else self.startExportRequested.emit()

    def _on_select(self):
        self.selectionChanged.emit(self.current_id() or "")

    def _context_menu(self, pos):
        menu = QMenu(self)
        act_selall = menu.addAction(tr("menu.selectAll"))
        act_files = menu.addAction(tr("menu.addFiles"))
        act_folder = menu.addAction(tr("menu.addFolder"))
        act_remove = menu.addAction(tr("menu.remove"))
        act_clear = menu.addAction(tr("menu.clear"))
        menu.addSeparator()
        act_analyze = menu.addAction(tr("menu.analyze"))
        act_export = menu.addAction(tr("menu.stopExport") if self.exporting else tr("menu.startExport"))
        act_open = menu.addAction(tr("menu.openOutput"))

        act_remove.setEnabled(bool(self.selected_ids()))
        act_clear.setEnabled(bool(self.items))
        act_analyze.setEnabled(self.current_id() is not None)
        act_export.setEnabled(bool(self.items))

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_selall:
            self.table.selectAll()
        elif chosen == act_files:
            self.addFilesRequested.emit()
        elif chosen == act_folder:
            self.addFolderRequested.emit()
        elif chosen == act_remove:
            self.remove_selected()
        elif chosen == act_clear:
            self.clear_all()
        elif chosen == act_analyze and self.current_id():
            self.analyzeRequested.emit(self.current_id())
        elif chosen == act_export:
            self._toggle_export()
        elif chosen == act_open:
            self.openOutputRequested.emit()
