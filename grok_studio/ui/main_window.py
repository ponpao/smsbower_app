"""Main window — frameless rounded card, sidebar, stacked tabs, toast, gating."""

from __future__ import annotations

from PyQt6.QtCore import QPropertyAnimation, Qt, QEasingCurve
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..api_client import APIClient
from ..constants import (
    CORNER_RADIUS,
    SHADOW_MARGIN,
    TAB_TRANSITION_MS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from ..i18n import set_language, tr
from ..settings_manager import SettingsManager
from .chat_tab import ChatTab
from .image_tab import ImageTab
from .settings_tab import SettingsTab
from .sidebar import (
    Sidebar,
    TAB_CHAT,
    TAB_IMAGE,
    TAB_SETTINGS,
    TAB_VIDEO,
    TAB_VOICE,
)
from .title_bar import TitleBar
from .toast import Toast
from .video_tab import VideoTab
from .voice_tab import VoiceTab


class MainWindow(QWidget):
    def __init__(self, settings: SettingsManager):
        super().__init__()
        self._settings = settings
        self._client = APIClient(settings.get_api_key)

        set_language(settings.language)

        # frameless, fixed-size, translucent so the rounded card shows through
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(
            WINDOW_WIDTH + SHADOW_MARGIN * 2,
            WINDOW_HEIGHT + SHADOW_MARGIN * 2,
        )
        self.setWindowTitle(tr("app.title"))

        # ---- rounded card with drop shadow -----------------------------------
        self.card = QWidget()
        self.card.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(SHADOW_MARGIN * 3)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.card.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(*[SHADOW_MARGIN] * 4)
        root.addWidget(self.card)

        # ---- content -----------------------------------------------------------
        self.title_bar = TitleBar(tr("app.title"))
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.minimize_requested.connect(self.showMinimized)

        self.sidebar = Sidebar()
        self.stack = QStackedWidget()

        self.chat_tab = ChatTab(self._client)
        self.image_tab = ImageTab(self._client, settings)
        self.video_tab = VideoTab(self._client, settings)
        self.voice_tab = VoiceTab(self._client, settings)
        self.settings_tab = SettingsTab(self._client, settings)

        self._tabs = {
            TAB_CHAT: self.chat_tab,
            TAB_IMAGE: self.image_tab,
            TAB_VIDEO: self.video_tab,
            TAB_VOICE: self.voice_tab,
            TAB_SETTINGS: self.settings_tab,
        }
        for tab_id in sorted(self._tabs):
            self.stack.addWidget(self._tabs[tab_id])

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.sidebar)
        body.addWidget(self.stack, 1)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(self.title_bar)
        card_layout.addLayout(body, 1)

        self.toast = Toast(self.card)

        # ---- wiring -------------------------------------------------------------
        self.sidebar.tab_selected.connect(self._switch_tab)
        for tab in self._tabs.values():
            tab.toast.connect(self.toast.show_message)
        self.image_tab.send_image_to_video.connect(self._image_to_video)
        self.settings_tab.key_validated.connect(self._unlock)
        self.settings_tab.language_switched.connect(self._change_language)

        self._fade_anim: QPropertyAnimation | None = None
        self.sidebar.retranslate_ui()

        # ---- API-key gate: force Settings until a key is stored -----------------
        if not settings.has_api_key():
            self.sidebar.set_locked(True)
            self.settings_tab.show_key_required_banner(True)
            self.sidebar.set_current(TAB_SETTINGS)
            self.stack.setCurrentWidget(self.settings_tab)

        self._center_on_screen()

    # ------------------------------------------------------------------ tabs --
    def _switch_tab(self, tab_id: int) -> None:
        target = self._tabs[tab_id]
        if self.stack.currentWidget() is target:
            return
        self.stack.setCurrentWidget(target)
        # ~150ms fade-in on the incoming tab
        effect = QGraphicsOpacityEffect(target)
        target.setGraphicsEffect(effect)
        self._fade_anim = QPropertyAnimation(effect, b"opacity", self)
        self._fade_anim.setDuration(TAB_TRANSITION_MS)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(
            lambda t=target: t.setGraphicsEffect(None)
        )
        self._fade_anim.start()

    def _image_to_video(self, data: bytes) -> None:
        self.video_tab.add_reference_image(data)
        self.sidebar.set_current(TAB_VIDEO)
        self._switch_tab(TAB_VIDEO)

    def _unlock(self) -> None:
        self.sidebar.set_locked(False)
        self.settings_tab.show_key_required_banner(False)

    # ------------------------------------------------------------------ i18n --
    def _change_language(self, lang: str) -> None:
        set_language(lang)
        self.setWindowTitle(tr("app.title"))
        self.title_bar.title_label.setText(tr("app.title"))
        self.sidebar.retranslate_ui()
        for tab in self._tabs.values():
            tab.retranslate_ui()

    # ------------------------------------------------------------------ misc --
    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )
