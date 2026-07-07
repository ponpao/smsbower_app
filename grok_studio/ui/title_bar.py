"""Custom frameless-window title bar: Mac-style traffic lights + drag region."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..constants import COLOR_TEXT_SECONDARY

_TRAFFIC = {
    "close": ("#FF5F57", "#E0443E"),
    "minimize": ("#FEBC2E", "#D89E24"),
    "zoom": ("#28C840", "#1F9A31"),
}


class TrafficLightButton(QPushButton):
    def __init__(self, kind: str, enabled: bool = True, parent=None):
        super().__init__(parent)
        self._color, self._hover_color = _TRAFFIC[kind]
        self._enabled_look = enabled
        self.setFixedSize(13, 13)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled
                       else Qt.CursorShape.ArrowCursor)
        self.setFlat(True)
        self.setEnabled(enabled)
        self.setStyleSheet("border: none; background: transparent;")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._color if self._enabled_look else "#3A3A44")
        if self.underMouse() and self.isEnabled():
            color = QColor(self._hover_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))


class TitleBar(QWidget):
    close_requested = pyqtSignal()
    minimize_requested = pyqtSignal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._drag_offset: QPoint | None = None

        close_btn = TrafficLightButton("close")
        close_btn.clicked.connect(self.close_requested.emit)
        min_btn = TrafficLightButton("minimize")
        min_btn.clicked.connect(self.minimize_requested.emit)
        zoom_btn = TrafficLightButton("zoom", enabled=False)  # fixed-size app

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 600;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)
        layout.addWidget(close_btn)
        layout.addWidget(min_btn)
        layout.addWidget(zoom_btn)
        layout.addStretch(1)
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addSpacing(13 * 3 + 8 * 2)  # visually center the title

    # ------------------------------------------------------------ dragging --
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.window().move(
                event.globalPosition().toPoint() - self._drag_offset
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)
