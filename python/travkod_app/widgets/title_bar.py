"""Frameless custom title bar: app name, subtitle, and mac-style window buttons."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

from ..theme import BG, BORDER_SOFT, ACCENT, TEXT, TEXT_DIM


class WindowButton(QPushButton):
    def __init__(self, color: str, hover: str):
        super().__init__()
        self.setFixedSize(13, 13)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton{{background:{color};border-radius:6px;}}"
            f"QPushButton:hover{{background:{hover};}}")


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__()
        self._win = window
        self._drag = None
        self.setFixedHeight(38)
        self.setStyleSheet(f"background:{BG}; border-bottom:1px solid {BORDER_SOFT};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 12, 0)

        logo = QLabel("▚")
        logo.setStyleSheet(f"color:{ACCENT}; font-size:14px;")
        title = QLabel("TRAVKOD")
        title.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:700; letter-spacing:5px;")
        sub = QLabel("honest master & humanize")
        sub.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")

        lay.addWidget(logo)
        lay.addSpacing(8)
        lay.addWidget(title)
        lay.addSpacing(10)
        lay.addWidget(sub)
        lay.addStretch(1)

        self.btn_min = WindowButton("#eab308", "#facc15")
        self.btn_max = WindowButton("#22c55e", "#4ade80")
        self.btn_close = WindowButton("#ef4444", "#f87171")
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(self._toggle_max)
        self.btn_close.clicked.connect(window.close)
        for b in (self.btn_min, self.btn_max, self.btn_close):
            lay.addWidget(b)
            lay.addSpacing(2)

    def _toggle_max(self):
        self._win.showNormal() if self._win.isMaximized() else self._win.showMaximized()

    # Drag the frameless window by the title bar.
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self._win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _e):
        self._drag = None

    def mouseDoubleClickEvent(self, _e):
        self._toggle_max()
