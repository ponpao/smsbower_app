"""Frameless custom title bar: traffic-light window buttons, app name, subtitle,
and an EN/KH language toggle.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

from ..theme import BG, BORDER_SOFT, ACCENT, TEXT, TEXT_DIM
from ..i18n import tr, I18N


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
        self.setFixedHeight(40)
        self.setStyleSheet(f"background:{BG}; border-bottom:1px solid {BORDER_SOFT};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        # Traffic-light window controls (left, matching the reference).
        self.btn_close = WindowButton("#ef4444", "#f87171")
        self.btn_min = WindowButton("#eab308", "#facc15")
        self.btn_max = WindowButton("#22c55e", "#4ade80")
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(self._toggle_max)
        self.btn_close.clicked.connect(window.close)
        for b in (self.btn_close, self.btn_min, self.btn_max):
            lay.addWidget(b)
        lay.addSpacing(10)

        logo = QLabel("▚")
        logo.setStyleSheet(f"color:{ACCENT}; font-size:15px;")
        title = QLabel("TRAVKOD")
        title.setStyleSheet(f"color:{ACCENT}; font-size:14px; font-weight:800; letter-spacing:4px;")
        self.sub = QLabel()
        self.sub.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        lay.addWidget(logo)
        lay.addSpacing(6)
        lay.addWidget(title)
        lay.addSpacing(10)
        lay.addWidget(self.sub)
        lay.addStretch(1)

        # EN / KH language toggle.
        self.lang_btn = QPushButton()
        self.lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_btn.setFixedHeight(24)
        self.lang_btn.setToolTip("English / ខ្មែរ")
        self.lang_btn.clicked.connect(I18N.toggle)
        lay.addWidget(self.lang_btn)

        I18N.changed.connect(self._retranslate)
        self._retranslate()

    def _retranslate(self):
        self.sub.setText(tr("app.subtitle"))
        # Show the language you'll switch TO, so the affordance is clear.
        self.lang_btn.setText("🌐  ខ្មែរ" if I18N.lang == "en" else "🌐  EN")

    def _toggle_max(self):
        self._win.showNormal() if self._win.isMaximized() else self._win.showMaximized()

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
