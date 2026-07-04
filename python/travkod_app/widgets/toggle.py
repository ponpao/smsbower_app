"""A compact custom-painted on/off switch (used for toggles across the UI)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QAbstractButton

from ..theme import ACCENT, BORDER


class ToggleSwitch(QAbstractButton):
    toggled_ = pyqtSignal(bool)

    def __init__(self, checked: bool = False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(38, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda: self.toggled_.emit(self.isChecked()))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        track = QColor(ACCENT if on else BORDER)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 10, 10)
        knob_x = self.width() - 17 if on else 3
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(knob_x, 3, 14, 14))
        p.end()
