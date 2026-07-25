# -*- coding: utf-8 -*-
"""Custom title bar — replaces the native one this window does not have."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import theme
from .i18n import en, km


class TitleBar(QWidget):
    """Drag area + window controls.

    Emits nothing the window does not already own; it calls back into the
    FramelessWindow so system move/maximise stay in one place.
    """

    close_requested = pyqtSignal()

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(theme.TITLEBAR_H)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 0, 0)
        lay.setSpacing(10)

        mark = QLabel("◈")
        mark.setObjectName("AppMark")
        lay.addWidget(mark)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        title = QLabel(en("app_title"))
        title.setObjectName("AppTitle")
        sub = QLabel(f"{km('app_sub')} · {en('app_sub')}")
        sub.setObjectName("AppSub")
        text.addWidget(title)
        text.addWidget(sub)
        lay.addLayout(text)

        lay.addStretch(1)

        self.btn_min = self._win_button("—", km("minimize"), en("minimize"))
        self.btn_max = self._win_button("□", km("maximize"), en("maximize"))
        self.btn_close = self._win_button("✕", km("close"), en("close"))
        self.btn_close.setObjectName("WinBtnClose")

        self.btn_min.clicked.connect(self._window.showMinimized)
        self.btn_max.clicked.connect(self._on_max)
        self.btn_close.clicked.connect(self.close_requested.emit)

        for b in (self.btn_min, self.btn_max, self.btn_close):
            lay.addWidget(b)

    def _win_button(self, glyph, km_tip, en_tip):
        b = QPushButton(glyph)
        b.setObjectName("WinBtn")
        b.setToolTip(f"{km_tip} ({en_tip})")
        b.setCursor(Qt.CursorShape.ArrowCursor)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return b

    def _on_max(self):
        self._window.toggle_max_restore()
        maxed = self._window.isMaximized()
        self.btn_max.setText("❐" if maxed else "□")
        self.btn_max.setToolTip(
            f"{km('restore')} ({en('restore')})" if maxed
            else f"{km('maximize')} ({en('maximize')})")

    # -- drag -------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._window.begin_system_move():
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_max()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
