# -*- coding: utf-8 -*-
"""
Live template preview.

Frames are addressed by INDEX, never by wall clock: the timer only advances a
counter, and `render(i)` is a pure function of it. That is the same contract
the exporter uses, so what plays here is what encodes — the preview cannot
drift against the audio and cannot disagree with the export about layout.

Layout is computed at the master resolution and the finished frame is scaled
down for display, so a cue that fits here fits at 2160p too.
"""

import numpy as np
from PIL import Image
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from visualizer import templates as T


def pil_to_pixmap(im: Image.Image) -> QPixmap:
    if im.mode != "RGB":
        im = im.convert("RGB")
    data = im.tobytes("raw", "RGB")
    qim = QImage(data, im.width, im.height, im.width * 3,
                 QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qim.copy())


class PreviewPanel(QWidget):
    """Renders the selected template at `master_size`, displays it scaled."""

    frame_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewFrame")

        self.template_key = T.TEMPLATE_KEYS[0]
        self.master_size = (1920, 1080)
        self.fps = 30
        self.duration = 210.0
        self.art = None
        self.title = ""
        self.artist = ""
        self.tracks = []
        self.cues = []
        self.spectra = None          # ndarray [frames, bands] when audio loaded
        self.font_family = None

        self._i = 0
        self._pix = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                  QSizePolicy.Policy.Ignored)
        self._label.setMinimumSize(320, 180)
        lay.addWidget(self._label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # -- transport --------------------------------------------------------
    def play(self):
        self._timer.start(int(1000 / max(1, self.fps)))

    def pause(self):
        self._timer.stop()

    @property
    def playing(self) -> bool:
        return self._timer.isActive()

    def seek(self, frame_index: int):
        self._i = max(0, int(frame_index))
        self.render()

    def _tick(self):
        total = int(self.duration * self.fps)
        self._i = (self._i + 1) % max(1, total)
        self.render()
        self.frame_changed.emit(self._i)

    # -- rendering --------------------------------------------------------
    def _bands_for(self, i: int) -> np.ndarray:
        """Real spectrum when audio is loaded, otherwise a synthetic one so
        the template still animates while the user is choosing a look."""
        if self.spectra is not None and len(self.spectra):
            return self.spectra[min(i, len(self.spectra) - 1)]
        x = np.linspace(0, 7, 64)
        wave = np.abs(np.sin(x + i * 0.09)) * (0.55 + 0.45 * np.sin(i * 0.031))
        decay = np.linspace(1.0, 0.35, 64)
        return np.clip(wave * decay + 0.06, 0, 1).astype(np.float32)

    def _cue_at(self, t: float):
        for start, end, text in self.cues:
            if start <= t <= end:
                return (start, end, text)
        return None

    def render(self):
        w, h = self.master_size
        bands = self._bands_for(self._i)
        t = self._i / float(self.fps)
        ctx = T.Ctx(
            frame=Image.new("RGB", (w, h)), w=w, h=h,
            i=self._i, fps=self.fps, duration=self.duration,
            bands=bands,
            bass=float(np.mean(bands[:8])),
            phase=self._i * 0.21,
            art=self.art, title=self.title, artist=self.artist,
            tracks=self.tracks, cue=self._cue_at(t),
            font_family=self.font_family,
        )
        T.render_frame(T.TEMPLATES[self.template_key], ctx)
        self._pix = pil_to_pixmap(ctx.frame)
        self._rescale()

    def _rescale(self):
        if self._pix is None:
            return
        self._label.setPixmap(self._pix.scaled(
            self._label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def current_frame(self) -> int:
        return self._i
