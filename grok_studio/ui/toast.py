"""Non-blocking toast banner shown at the top of the window.

Used everywhere for errors (network, 4xx/5xx, moderation) and short
confirmations. Never modal, auto-dismisses.
"""

from __future__ import annotations

from PyQt6.QtCore import QPropertyAnimation, QTimer, Qt
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ..constants import COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING

_KIND_COLORS = {
    "error": COLOR_ERROR,
    "success": COLOR_SUCCESS,
    "warning": COLOR_WARNING,
    "info": "#5C8DFF",
}


class Toast(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._close = QPushButton("✕")
        self._close.setFixedSize(20, 20)
        self._close.setStyleSheet(
            "border:none;background:transparent;color:white;font-size:11px;"
        )
        self._close.clicked.connect(self.hide_now)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._close, 0, Qt.AlignmentFlag.AlignTop)

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(150)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_now)

    def show_message(self, text: str, kind: str = "error",
                     duration_ms: int = 5000) -> None:
        color = _KIND_COLORS.get(kind, _KIND_COLORS["info"])
        self.setStyleSheet(
            f"background: {color}; border-radius: 8px; color: white;"
        )
        self._label.setStyleSheet("color: white; font-weight: 600;")
        self._label.setText(text)
        self._reposition()
        self.raise_()
        self.show()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(duration_ms)

    def hide_now(self) -> None:
        self._timer.stop()
        self.hide()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        width = parent.width() - 40
        self.setFixedWidth(width)
        self.adjustSize()
        self.move(20, 48)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._reposition()
        super().resizeEvent(event)
