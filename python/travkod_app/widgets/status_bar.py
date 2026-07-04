"""Thin footer: Status / queue progress / CPU / RAM. Uses psutil when present."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from ..theme import BG, BORDER_SOFT, TEXT_MUTED, TEXT, ACCENT
from ..i18n import tr, I18N

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

        self._exporting = False
        self._done = 0
        self._total = 0

        self.status = QLabel()
        self.status.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10px;")
        self.queue = QLabel("")
        self.queue.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10px;")
        self.local = QLabel()
        self.local.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10px;")
        lay.addWidget(self.status)
        lay.addSpacing(14)
        lay.addWidget(self.queue)
        lay.addSpacing(14)
        lay.addWidget(self.local)
        lay.addStretch(1)

        self.cpu = QLabel("CPU: —")
        self.ram = QLabel("RAM: —")
        for w in (self.cpu, self.ram):
            w.setStyleSheet(f"color:{ACCENT}; font-size:10px; font-weight:600;")
        lay.addWidget(self.cpu)
        lay.addSpacing(14)
        lay.addWidget(self.ram)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1500)
        if _HAVE_PSUTIL:
            psutil.cpu_percent(interval=None)  # prime

        I18N.changed.connect(self._retranslate)
        self._retranslate()

    def _retranslate(self):
        self.local.setText(tr("sbar.local"))
        self.set_status(self._exporting, self._done, self._total)

    def set_status(self, exporting: bool, done: int, total: int):
        self._exporting, self._done, self._total = exporting, done, total
        if exporting:
            self.status.setText(f"{tr('sbar.status')} {tr('sbar.processing')}")
            self.status.setStyleSheet(f"color:{ACCENT}; font-size:10px;")
        else:
            state = tr("sbar.ready") if total else tr("sbar.idle")
            self.status.setText(f"{tr('sbar.status')} {state}")
            self.status.setStyleSheet(f"color:{TEXT}; font-size:10px;")
        self.queue.setText(f"{tr('sbar.queue')} {done}/{total}" if total else "")

    def _tick(self):
        if not _HAVE_PSUTIL:
            return
        self.cpu.setText(f"CPU: {int(psutil.cpu_percent(interval=None))}%")
        self.ram.setText(f"RAM: {int(psutil.virtual_memory().percent)}%")
