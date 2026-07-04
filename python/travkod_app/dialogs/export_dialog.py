"""Export Settings dialog."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QPushButton, QFileDialog, QDoubleSpinBox, QWidget,
)

from ..state import ExportSettings, default_output_dir
from ..theme import TEXT, TEXT_DIM
from ..widgets.toggle import ToggleSwitch
from ..i18n import tr


def _row(label: str, widget: QWidget, hint: str = "") -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 4, 0, 4)
    left = QVBoxLayout()
    l = QLabel(label)
    l.setStyleSheet(f"color:{TEXT}; font-size:12px;")
    left.addWidget(l)
    if hint:
        h = QLabel(hint)
        h.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        left.addWidget(h)
    lay.addLayout(left)
    lay.addStretch(1)
    lay.addWidget(widget)
    return w


class ExportDialog(QDialog):
    def __init__(self, settings: ExportSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("exp.title"))
        self.setMinimumWidth(440)
        self.s = settings
        self.start = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(2)

        self.fmt = QComboBox(); self.fmt.addItems(["wav", "flac", "mp3"])
        self.fmt.setCurrentText(self.s.format)
        self.fmt.currentTextChanged.connect(self._on_fmt)
        root.addWidget(_row(tr("exp.format"), self.fmt))

        self.sr = QComboBox()
        self.sr.addItems([tr("exp.keepSource"), "44100", "48000", "96000"])
        self.sr.setCurrentText(tr("exp.keepSource") if self.s.sample_rate is None else str(self.s.sample_rate))
        root.addWidget(_row(tr("exp.sampleRate"), self.sr))

        self.bits = QComboBox(); self.bits.addItems(["16", "24", "32"])
        self.bits.setCurrentText(str(self.s.bit_depth))
        self.bits_row = _row(tr("exp.bitDepth"), self.bits)
        root.addWidget(self.bits_row)

        self.mp3 = QComboBox(); self.mp3.addItems(["192", "256", "320"])
        self.mp3.setCurrentText(str(self.s.mp3_bitrate))
        self.mp3_row = _row(tr("exp.mp3Bitrate"), self.mp3)
        root.addWidget(self.mp3_row)

        self.threads = QSpinBox(); self.threads.setRange(1, 8)
        self.threads.setValue(self.s.threads)
        root.addWidget(_row(tr("exp.threads"), self.threads, tr("exp.threadsHint")))

        self.lufs = QComboBox()
        self._lufs_opts = [tr("exp.lufsOff"), tr("exp.lufsStream"), tr("exp.lufsLoud"), tr("exp.lufsCustom")]
        self.lufs.addItems(self._lufs_opts)
        self._set_lufs_combo()
        self.lufs.currentTextChanged.connect(self._on_lufs)
        root.addWidget(_row(tr("exp.lufs"), self.lufs))

        self.lufs_custom = QDoubleSpinBox()
        self.lufs_custom.setRange(-30, 0); self.lufs_custom.setSingleStep(0.5)
        self.lufs_custom.setValue(self.s.lufs_target if self.s.lufs_target is not None else -12)
        self.lufs_custom_row = _row(tr("exp.customLufs"), self.lufs_custom)
        root.addWidget(self.lufs_custom_row)

        self.autotune = ToggleSwitch(self.s.autotune)
        root.addWidget(_row(tr("exp.autotune"), self.autotune, tr("exp.autotuneHint")))
        self.merge = ToggleSwitch(self.s.merge)
        root.addWidget(_row(tr("exp.merge"), self.merge, tr("exp.mergeHint")))

        self.folder_btn = QPushButton(tr("exp.choose"))
        self.folder_btn.clicked.connect(self._choose_folder)
        self.folder_lbl = self.s.output_folder or "~/TRAVKOD Exports"
        self.folder_row = _row(tr("exp.outFolder"), self.folder_btn, self.folder_lbl)
        root.addWidget(self.folder_row)

        root.addSpacing(8)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton(tr("exp.close")); cancel.clicked.connect(self.reject)
        go = QPushButton(tr("exp.start")); go.setProperty("accent", True)
        go.clicked.connect(self._start)
        btns.addWidget(cancel); btns.addWidget(go)
        root.addLayout(btns)

        self._on_fmt(self.s.format)
        self._on_lufs(self.lufs.currentText())

    def _set_lufs_combo(self):
        t = self.s.lufs_target
        if t is None:
            self.lufs.setCurrentIndex(0)
        elif t == -14:
            self.lufs.setCurrentIndex(1)
        elif t == -9:
            self.lufs.setCurrentIndex(2)
        else:
            self.lufs.setCurrentIndex(3)

    def _on_fmt(self, fmt: str):
        self.bits_row.setVisible(fmt != "mp3")
        self.mp3_row.setVisible(fmt == "mp3")

    def _on_lufs(self, _text: str):
        self.lufs_custom_row.setVisible(self.lufs.currentIndex() == 3)

    def _choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder")
        if d:
            self.folder_lbl = d
            self.folder_row.findChildren(QLabel)[-1].setText(d)

    def _start(self):
        self.start = True
        self.apply_to(self.s)
        self.accept()

    def apply_to(self, s: ExportSettings):
        s.format = self.fmt.currentText()
        s.sample_rate = None if self.sr.currentIndex() == 0 else int(self.sr.currentText())
        s.bit_depth = int(self.bits.currentText())
        s.mp3_bitrate = int(self.mp3.currentText())
        s.threads = self.threads.value()
        idx = self.lufs.currentIndex()
        s.lufs_target = {0: None, 1: -14.0, 2: -9.0}.get(idx, self.lufs_custom.value())
        s.autotune = self.autotune.isChecked()
        s.merge = self.merge.isChecked()
        s.output_folder = None if self.folder_lbl.startswith("~") else self.folder_lbl
