"""Chat tab — grok-4.3 with streaming, bubbles and per-message copy."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QKeyEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..api_client import APIClient
from ..constants import (
    CHAT_MODEL,
    COLOR_ACCENT,
    COLOR_BG_ELEVATED,
    COLOR_TEXT_SECONDARY,
)
from ..i18n import tr
from ..workers import ChatStreamWorker


class MessageBubble(QWidget):
    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)
        self.role = role
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        is_user = role == "user"
        bubble_color = COLOR_ACCENT if is_user else COLOR_BG_ELEVATED
        self._label.setStyleSheet(f"""
            background: {bubble_color};
            color: {"white" if is_user else "#F2F2F5"};
            border-radius: 10px;
            padding: 8px 11px;
        """)
        self._label.setMaximumWidth(270)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(4)

        if is_user:
            row.addStretch(1)
            row.addWidget(self._label)
        else:
            column = QVBoxLayout()
            column.setSpacing(2)
            column.addWidget(self._label)
            self.copy_btn = QToolButton()
            self.copy_btn.setText(tr("generic.copy"))
            self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.copy_btn.setStyleSheet(
                f"border:none;background:transparent;"
                f"color:{COLOR_TEXT_SECONDARY};font-size:11px;padding:0 4px;"
            )
            self.copy_btn.clicked.connect(self._copy)
            column.addWidget(self.copy_btn,
                             alignment=Qt.AlignmentFlag.AlignLeft)
            row.addLayout(column)
            row.addStretch(1)

    def set_text(self, text: str) -> None:
        self._label.setText(text)

    def text(self) -> str:
        return self._label.text()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.text())
        self.copy_btn.setText(tr("generic.copied"))
        QTimer.singleShot(1200, lambda: self.copy_btn.setText(tr("generic.copy")))


class ChatInput(QTextEdit):
    """Enter sends, Shift+Enter inserts a newline."""

    send_requested = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.send_requested.emit()
            return
        super().keyPressEvent(event)


class ChatTab(QWidget):
    toast = pyqtSignal(str, str)  # message, kind

    def __init__(self, client: APIClient, parent=None):
        super().__init__(parent)
        self._client = client
        self._history: list[dict[str, str]] = []
        self._worker: ChatStreamWorker | None = None
        self._streaming_bubble: MessageBubble | None = None
        self._typing_timer = QTimer(self)
        self._typing_timer.timeout.connect(self._animate_typing)
        self._typing_dots = 0

        # -- collapsible system prompt ---------------------------------------
        self.system_toggle = QToolButton()
        self.system_toggle.setCheckable(True)
        self.system_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.system_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.system_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.system_toggle.setStyleSheet(
            f"border:none;background:transparent;color:{COLOR_TEXT_SECONDARY};"
        )
        self.system_toggle.toggled.connect(self._toggle_system)

        self.system_edit = QPlainTextEdit()
        self.system_edit.setFixedHeight(64)
        self.system_edit.hide()

        self.clear_btn = QToolButton()
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(
            f"border:none;background:transparent;color:{COLOR_TEXT_SECONDARY};"
        )
        self.clear_btn.clicked.connect(self._clear_chat)

        header = QHBoxLayout()
        header.addWidget(self.system_toggle)
        header.addStretch(1)
        header.addWidget(self.clear_btn)

        # -- message list -----------------------------------------------------
        self._messages_layout = QVBoxLayout()
        self._messages_layout.setSpacing(2)
        self._messages_layout.addStretch(1)
        container = QWidget()
        container.setLayout(self._messages_layout)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(container)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.typing_label = QLabel()
        self.typing_label.setProperty("secondary", True)
        self.typing_label.hide()

        # -- input row ----------------------------------------------------------
        self.input = ChatInput()
        self.input.setFixedHeight(64)
        self.input.send_requested.connect(self._send)

        self.send_btn = QPushButton()
        self.send_btn.setProperty("accent", True)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setFixedWidth(72)
        self.send_btn.clicked.connect(self._send)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.send_btn, 0,
                            Qt.AlignmentFlag.AlignBottom)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 12)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self.system_edit)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self.typing_label)
        layout.addLayout(input_row)

        self.retranslate_ui()

    # ------------------------------------------------------------------ ui --
    def _toggle_system(self, checked: bool) -> None:
        self.system_toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
        self.system_edit.setVisible(checked)

    def _add_bubble(self, role: str, text: str) -> MessageBubble:
        bubble = MessageBubble(role, text)
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, bubble
        )
        QTimer.singleShot(30, self._scroll_to_bottom)
        return bubble

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_chat(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self._history.clear()
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _animate_typing(self) -> None:
        self._typing_dots = (self._typing_dots + 1) % 4
        self.typing_label.setText(tr("chat.thinking") + "." * self._typing_dots)

    # ---------------------------------------------------------------- send --
    def _send(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()

        self._add_bubble("user", text)
        self._history.append({"role": "user", "content": text})

        messages: list[dict[str, str]] = []
        system = self.system_edit.toPlainText().strip()
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(self._history)

        self._streaming_bubble = None
        self.send_btn.setEnabled(False)
        self.typing_label.show()
        self._typing_timer.start(350)

        self._worker = ChatStreamWorker(self._client, messages, parent=self)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.retry_wait.connect(self._on_retry_wait)
        self._worker.start()

    def _on_chunk(self, delta: str) -> None:
        if self._streaming_bubble is None:
            self._stop_typing()
            self._streaming_bubble = self._add_bubble("assistant", "")
        self._streaming_bubble.set_text(self._streaming_bubble.text() + delta)
        self._scroll_to_bottom()

    def _on_done(self, full_text: str) -> None:
        self._stop_typing()
        if self._streaming_bubble is None:
            self._add_bubble("assistant", full_text)
        else:
            self._streaming_bubble.set_text(full_text)
        self._history.append({"role": "assistant", "content": full_text})
        self._streaming_bubble = None
        self.send_btn.setEnabled(True)
        self._scroll_to_bottom()

    def _on_error(self, message: str) -> None:
        self._stop_typing()
        self.send_btn.setEnabled(True)
        self._streaming_bubble = None
        # keep history consistent: drop the user turn that failed
        if self._history and self._history[-1]["role"] == "user":
            self._history.pop()
        self.toast.emit(message, "error")

    def _on_retry_wait(self, seconds: int) -> None:
        self.toast.emit(tr("generic.retry_in").format(s=seconds), "warning")

    def _stop_typing(self) -> None:
        self._typing_timer.stop()
        self.typing_label.hide()

    # ---------------------------------------------------------------- i18n --
    def retranslate_ui(self) -> None:
        self.system_toggle.setText(" " + tr("chat.system_prompt"))
        self.system_edit.setPlaceholderText(tr("chat.system_placeholder"))
        self.input.setPlaceholderText(tr("chat.placeholder"))
        self.send_btn.setText(tr("chat.send"))
        self.clear_btn.setText(tr("chat.clear"))
        self.typing_label.setText(tr("chat.thinking"))
