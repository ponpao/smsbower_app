"""A labeled vertical slider with a dB/%/Hz readout beneath it.

QSlider is integer-only, so float controls (dB in 0.5 steps) use an internal
scale factor. Double-click resets to the control's neutral value.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider

from ..theme import ACCENT_SOFT, TEXT_DIM, TEXT_MUTED


class LabeledSlider(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, label: str, unit: str, lo: float, hi: float,
                 step: float, is_float: bool, value: float = 0.0):
        super().__init__()
        self.unit = unit
        self.is_float = is_float
        self.lo, self.hi = lo, hi
        self.scale = int(round(1.0 / step)) if is_float and step < 1 else 1
        self._neutral = lo if unit == "Hz" else 0.0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.name = QLabel(label)
        self.name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.name.setStyleSheet(f"font-size:10px; color:{TEXT_MUTED};")

        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setMinimum(int(lo * self.scale))
        self.slider.setMaximum(int(hi * self.scale))
        self.slider.setFixedHeight(96)
        self.slider.setValue(int(value * self.scale))
        self.slider.valueChanged.connect(self._on_change)

        self.readout = QLabel()
        self.readout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.readout.setStyleSheet(f"font-size:10px; color:{TEXT_DIM};")

        lay.addWidget(self.name)
        lay.addWidget(self.slider, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.readout)
        self._update_readout(value)

    def _fmt(self, v: float) -> str:
        if self.unit == "Hz":
            return f"{int(round(v))} Hz"
        if self.unit == "%":
            return f"{int(round(v))} %"
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.0f} dB" if v % 1 == 0 else f"{sign}{v:.1f} dB"

    def _on_change(self, raw: int):
        v = raw / self.scale
        self._update_readout(v)
        self.valueChanged.emit(v)

    def _update_readout(self, v: float):
        active = abs(v - self._neutral) > 1e-6
        color = ACCENT_SOFT if active else TEXT_DIM
        self.readout.setStyleSheet(f"font-size:10px; color:{color};")
        self.name.setStyleSheet(
            f"font-size:10px; color:{'#cbd5e1' if active else TEXT_MUTED};")
        self.readout.setText(self._fmt(v))

    def set_value(self, v: float):
        self.slider.blockSignals(True)
        self.slider.setValue(int(v * self.scale))
        self.slider.blockSignals(False)
        self._update_readout(v)

    def value(self) -> float:
        return self.slider.value() / self.scale

    def set_enabled(self, on: bool):
        self.slider.setEnabled(on)

    def mouseDoubleClickEvent(self, _e):
        self.set_value(self._neutral)
        self.valueChanged.emit(self._neutral)
