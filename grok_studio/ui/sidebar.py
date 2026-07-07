"""56px vertical icon sidebar: Chat / Image / Video / Voice + Settings gear."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QToolButton, QVBoxLayout, QWidget

from ..constants import COLOR_ACCENT, COLOR_TEXT_SECONDARY, SIDEBAR_WIDTH
from ..i18n import tr

TAB_CHAT, TAB_IMAGE, TAB_VIDEO, TAB_VOICE, TAB_SETTINGS = range(5)

_GLYPHS = {
    TAB_CHAT: "\U0001F4AC",      # 💬
    TAB_IMAGE: "\U0001F5BC",     # 🖼
    TAB_VIDEO: "\U0001F3AC",     # 🎬
    TAB_VOICE: "\U0001F3A4",     # 🎤
    TAB_SETTINGS: "⚙",      # ⚙
}
_LABEL_KEYS = {
    TAB_CHAT: "tab.chat",
    TAB_IMAGE: "tab.image",
    TAB_VIDEO: "tab.video",
    TAB_VOICE: "tab.voice",
    TAB_SETTINGS: "tab.settings",
}


class SidebarButton(QToolButton):
    def __init__(self, glyph: str, parent=None):
        super().__init__(parent)
        self.setText(glyph)
        self.setCheckable(True)
        self.setFixedSize(44, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QToolButton {{
                border: none; border-radius: 10px;
                background: transparent;
                color: {COLOR_TEXT_SECONDARY};
                font-size: 18px;
            }}
            QToolButton:hover {{ background: #232330; }}
            QToolButton:checked {{
                background: {COLOR_ACCENT}33;
                color: {COLOR_ACCENT};
            }}
        """)


class Sidebar(QWidget):
    tab_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[int, SidebarButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 10, 6, 10)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        for tab in (TAB_CHAT, TAB_IMAGE, TAB_VIDEO, TAB_VOICE):
            layout.addWidget(self._make_button(tab),
                             alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        layout.addWidget(self._make_button(TAB_SETTINGS),
                         alignment=Qt.AlignmentFlag.AlignHCenter)

        self._buttons[TAB_CHAT].setChecked(True)
        self._group.idClicked.connect(self.tab_selected.emit)

    def _make_button(self, tab: int) -> SidebarButton:
        btn = SidebarButton(_GLYPHS[tab])
        self._group.addButton(btn, tab)
        self._buttons[tab] = btn
        return btn

    def set_current(self, tab: int) -> None:
        self._buttons[tab].setChecked(True)

    def set_locked(self, locked: bool) -> None:
        """While no API key is stored, only Settings is usable."""
        for tab, btn in self._buttons.items():
            btn.setEnabled(tab == TAB_SETTINGS or not locked)

    def retranslate_ui(self) -> None:
        for tab, btn in self._buttons.items():
            btn.setToolTip(tr(_LABEL_KEYS[tab]))
