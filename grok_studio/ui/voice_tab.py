"""Voice tab — TTS to MP3 with inline playback (play/pause/scrub) + Save As."""

from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..api_client import APIClient
from ..constants import TTS_LANGUAGES, TTS_VOICES
from ..i18n import tr
from ..logging_setup import app_data_dir
from ..settings_manager import SettingsManager
from ..workers import ApiWorker


def _fmt_ms(ms: int) -> str:
    seconds = max(0, ms // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


class VoiceTab(QWidget):
    toast = pyqtSignal(str, str)

    def __init__(self, client: APIClient, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self._client = client
        self._settings = settings
        self._worker: ApiWorker | None = None
        self._audio_bytes: bytes | None = None
        self._scrubbing = False

        self.text = QTextEdit()
        self.text.textChanged.connect(self._update_counter)

        self.counter_label = QLabel()
        self.counter_label.setProperty("secondary", True)

        self.voice_combo = QComboBox()
        self.voice_combo.addItems(TTS_VOICES)
        self.voice_combo.setCurrentText(settings.last_voice)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(TTS_LANGUAGES)
        self.lang_combo.setCurrentText(settings.last_tts_language)

        self.generate_btn = QPushButton()
        self.generate_btn.setProperty("accent", True)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self._generate)

        # ---- playback controls ----------------------------------------------
        self._player = QMediaPlayer(self)
        self._audio_out = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_out)
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.playbackStateChanged.connect(self._on_state)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedWidth(44)
        self.play_btn.clicked.connect(self._toggle_play)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderPressed.connect(
            lambda: setattr(self, "_scrubbing", True))
        self.seek_slider.sliderReleased.connect(self._seek_released)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setProperty("secondary", True)

        self.save_btn = QPushButton()
        self.save_btn.clicked.connect(self._save_as)

        self._player_row = QWidget()
        player_layout = QHBoxLayout(self._player_row)
        player_layout.setContentsMargins(0, 0, 0, 0)
        player_layout.setSpacing(6)
        player_layout.addWidget(self.play_btn)
        player_layout.addWidget(self.seek_slider, 1)
        player_layout.addWidget(self.time_label)
        self._player_row.hide()
        self.save_btn.hide()

        # ---- layout ---------------------------------------------------------
        self.voice_caption = QLabel()
        self.voice_caption.setProperty("secondary", True)
        self.lang_caption = QLabel()
        self.lang_caption.setProperty("secondary", True)
        opts_row = QHBoxLayout()
        opts_row.addWidget(self.voice_caption)
        opts_row.addWidget(self.voice_combo, 1)
        opts_row.addWidget(self.lang_caption)
        opts_row.addWidget(self.lang_combo, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.counter_label,
                         alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(opts_row)
        layout.addWidget(self.generate_btn)
        layout.addWidget(self._player_row)
        layout.addWidget(self.save_btn)

        self.retranslate_ui()
        self._update_counter()

    # ------------------------------------------------------------ generate --
    def _generate(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        text = self.text.toPlainText().strip()
        if not text:
            return

        voice = self.voice_combo.currentText()
        language = self.lang_combo.currentText()
        self._settings.last_voice = voice
        self._settings.last_tts_language = language

        self.generate_btn.setEnabled(False)
        self._worker = ApiWorker(self._client.tts, text, parent=self,
                                 voice=voice, language=language)
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.retry_wait.connect(
            lambda s: self.toast.emit(tr("generic.retry_in").format(s=s), "warning")
        )
        self._worker.start()

    def _on_success(self, data: bytes) -> None:
        self.generate_btn.setEnabled(True)
        self._audio_bytes = bytes(data)

        cache_dir = app_data_dir() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / f"tts_{int(time.time())}.mp3"
        try:
            path.write_bytes(self._audio_bytes)
        except OSError as exc:
            self.toast.emit(str(exc), "error")
            return

        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player_row.show()
        self.save_btn.show()
        self._player.play()

    def _on_error(self, message: str) -> None:
        self.generate_btn.setEnabled(True)
        self.toast.emit(message, "error")

    # ------------------------------------------------------------ playback --
    def _toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_state(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_btn.setText("⏸" if playing else "▶")
        self.play_btn.setToolTip(tr("voice.pause") if playing else tr("voice.play"))

    def _on_position(self, pos: int) -> None:
        if not self._scrubbing:
            self.seek_slider.setValue(pos)
        self.time_label.setText(
            f"{_fmt_ms(pos)} / {_fmt_ms(self._player.duration())}"
        )

    def _on_duration(self, duration: int) -> None:
        self.seek_slider.setRange(0, max(0, duration))

    def _seek_released(self) -> None:
        self._scrubbing = False
        self._player.setPosition(self.seek_slider.value())

    # ---------------------------------------------------------------- save --
    def _save_as(self) -> None:
        if not self._audio_bytes:
            return
        default = str(self._settings.output_dir / f"grok_tts_{int(time.time())}.mp3")
        path, _ = QFileDialog.getSaveFileName(
            self, tr("generic.save_as"), default, "MP3 (*.mp3)"
        )
        if not path:
            return
        try:
            Path(path).write_bytes(self._audio_bytes)
        except OSError as exc:
            self.toast.emit(str(exc), "error")
            return
        self.toast.emit(f'{tr("generic.saved_to")} {path}', "success")

    # ------------------------------------------------------------- counter --
    def _update_counter(self) -> None:
        count = len(self.text.toPlainText())
        self.counter_label.setText(f'{count} {tr("voice.chars")}')

    # ---------------------------------------------------------------- i18n --
    def retranslate_ui(self) -> None:
        self.text.setPlaceholderText(tr("voice.placeholder"))
        self.voice_caption.setText(tr("voice.voice"))
        self.lang_caption.setText(tr("voice.language"))
        self.generate_btn.setText(tr("generic.generate"))
        self.save_btn.setText(tr("generic.save_as"))
        self._update_counter()
