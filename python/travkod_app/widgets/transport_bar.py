"""Transport bar: play/next, Effect A/B (processed vs original), scrubber, volume.

Playback uses QtMultimedia when available; if the platform lacks an audio backend
the controls stay visible but disabled, so the rest of the app is unaffected.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSlider,
)

from ..theme import TEXT_MUTED, TEXT_DIM, ACCENT_SOFT, BG, BORDER_SOFT
from ..widgets.toggle import ToggleSwitch

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    _HAVE_MEDIA = True
except Exception:  # pragma: no cover
    _HAVE_MEDIA = False


class TransportBar(QWidget):
    releaseCheckRequested = pyqtSignal()
    effectToggled = pyqtSignal(bool)
    nextRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(56)
        self.setStyleSheet(f"background:{BG}; border-top:1px solid {BORDER_SOFT};")
        self._orig: Optional[str] = None
        self._proc: Optional[str] = None
        self._effect = True
        self._duration = 0

        self.player = None
        self.audio = None
        if _HAVE_MEDIA:
            self.player = QMediaPlayer()
            self.audio = QAudioOutput()
            self.player.setAudioOutput(self.audio)
            self.audio.setVolume(0.8)
            self.player.positionChanged.connect(self._on_pos)
            self.player.durationChanged.connect(self._on_dur)
            self.player.playbackStateChanged.connect(self._on_pstate)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 14, 6)
        lay.setSpacing(12)

        self.play_btn = QPushButton("▶")
        self.play_btn.setProperty("accent", True)
        self.play_btn.setFixedSize(34, 34)
        self.play_btn.setStyleSheet("border-radius:17px;")
        self.play_btn.clicked.connect(self.toggle_play)
        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(28, 28)
        self.next_btn.clicked.connect(self.nextRequested)
        lay.addWidget(self.play_btn)
        lay.addWidget(self.next_btn)

        lay.addWidget(self._muted("Effect"))
        self.effect_toggle = ToggleSwitch(True)
        self.effect_toggle.toggled_.connect(self._on_effect)
        lay.addWidget(self.effect_toggle)
        self.effect_lbl = QLabel("Processed")
        self.effect_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        self.effect_lbl.setFixedWidth(60)
        lay.addWidget(self.effect_lbl)

        self.pos_lbl = QLabel("0:00")
        self.pos_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        lay.addWidget(self.pos_lbl)
        self.scrub = QSlider(Qt.Orientation.Horizontal)
        self.scrub.setRange(0, 1000)
        self.scrub.sliderMoved.connect(self._seek)
        lay.addWidget(self.scrub, stretch=1)
        self.dur_lbl = QLabel("0:00")
        self.dur_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        lay.addWidget(self.dur_lbl)

        lay.addWidget(QLabel("🔊"))
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(80)
        self.vol.setFixedWidth(80)
        self.vol.valueChanged.connect(self._on_vol)
        lay.addWidget(self.vol)

        self.release_btn = QPushButton("Release Check")
        self.release_btn.clicked.connect(self.releaseCheckRequested)
        lay.addWidget(self.release_btn)

        if not _HAVE_MEDIA:
            for w in (self.play_btn, self.next_btn, self.scrub, self.vol):
                w.setEnabled(False)
            self.play_btn.setToolTip("Audio playback unavailable on this system")

    def _muted(self, t):
        lbl = QLabel(t)
        lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
        return lbl

    # ---- source management -------------------------------------------
    def set_sources(self, original: Optional[str], processed: Optional[str] = None):
        self._orig, self._proc = original, processed
        self._load_current()

    def set_processed(self, processed: Optional[str]):
        self._proc = processed
        if self._effect:
            self._load_current(keep_pos=True)

    def _load_current(self, keep_pos: bool = False):
        if not self.player:
            return
        src = self._proc if (self._effect and self._proc) else self._orig
        if not src:
            return
        pos = self.player.position()
        self.player.setSource(QUrl.fromLocalFile(src))
        if keep_pos:
            self.player.setPosition(pos)

    # ---- playback -----------------------------------------------------
    def toggle_play(self):
        if not self.player:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if not self.player.source().isValid() and self._orig:
                self._load_current()
            self.player.play()

    def _on_effect(self, on: bool):
        self._effect = on
        self.effect_lbl.setText("Processed" if on else "Original")
        self.effectToggled.emit(on)
        self._load_current(keep_pos=True)

    def _on_vol(self, v: int):
        if self.audio:
            self.audio.setVolume(v / 100.0)

    def _seek(self, v: int):
        if self.player and self._duration:
            self.player.setPosition(int(self._duration * v / 1000))

    def _on_pos(self, ms: int):
        if self._duration:
            self.scrub.blockSignals(True)
            self.scrub.setValue(int(ms / self._duration * 1000))
            self.scrub.blockSignals(False)
        self.pos_lbl.setText(self._fmt(ms))

    def _on_dur(self, ms: int):
        self._duration = ms
        self.dur_lbl.setText(self._fmt(ms))

    def _on_pstate(self, _state):
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.play_btn.setText("❚❚" if playing else "▶")

    @staticmethod
    def _fmt(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"
