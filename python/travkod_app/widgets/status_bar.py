"""Thin footer: Status / queue progress / CPU / RAM. Uses psutil when present."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from ..theme import BG, BORDER_SOFT, TEXT_MUTED, TEXT, ACCENT_SOFT

try:
    import psutil
    _HAVE_PSUTIL = True
except Exception:
    _HAVE_PSUTIL = False


class StatusBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(24)
        self.setStyleSheet(f"background:{BG}; border-top:1px solid {BORDER_SOFT};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)

        self.status = QLabel("Status: Idle")
        self.status.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10px;")
        self.queue = QLabel("")
        self.queue.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10px;")
        local = QLabel("All processing runs locally")
        local.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10px;")
        lay.addWidget(self.status)
        lay.addSpacing(14)
        lay.addWidget(self.queue)
        lay.addSpacing(14)
        lay.addWidget(local)
        lay.addStretch(1)

        self.cpu = QLabel("CPU: —")
        self.ram = QLabel("RAM: —")
        for w in (self.cpu, self.ram):
            w.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10px;")
        lay.addWidget(self.cpu)
        lay.addSpacing(14)
        lay.addWidget(self.ram)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1500)
        if _HAVE_PSUTIL:
            psutil.cpu_percent(interval=None)  # prime

    def set_status(self, exporting: bool, done: int, total: int):
        if exporting:
            self.status.setText("Status: Processing")
            self.status.setStyleSheet(f"color:{ACCENT_SOFT}; font-size:10px;")
        else:
            self.status.setText("Status: " + ("Ready" if total else "Idle"))
            self.status.setStyleSheet(f"color:{TEXT}; font-size:10px;")
        self.queue.setText(f"Queue: {done}/{total}" if total else "")

    def _tick(self):
        if not _HAVE_PSUTIL:
            return
        self.cpu.setText(f"CPU: {int(psutil.cpu_percent(interval=None))}%")
        self.ram.setText(f"RAM: {int(psutil.virtual_memory().percent)}%")
