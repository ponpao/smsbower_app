"""Setting Console: template/presets/quick-EQ bar, the mastering strip (left),
and the 10-band graphic EQ (right). Reads and writes the shared AppState params.
"""
from __future__ import annotations

from typing import Dict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QFrame,
    QMenu, QSlider, QInputDialog,
)

from ..state import AppState, STRIP_CONTROLS, EQ_LABELS, QUICK_EQ
from ..theme import TEXT_MUTED, ACCENT, BORDER_SOFT
from ..i18n import tr, I18N
from ..widgets.vertical_slider import LabeledSlider
from ..widgets.toggle import ToggleSwitch
from travkod.params import Params, EQ_BANDS, FACTORY_TEMPLATES


class SettingConsole(QWidget):
    paramsChanged = pyqtSignal()
    humanizeToggled = pyqtSignal(bool)
    exportRequested = pyqtSignal()
    analyzeAiRequested = pyqtSignal()
    presetsChanged = pyqtSignal()

    def __init__(self, state: AppState, preset_store):
        super().__init__()
        self.state = state
        self.preset_store = preset_store
        self.strip_sliders: Dict[str, LabeledSlider] = {}
        self.eq_sliders = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 0, 12, 6)
        root.setSpacing(6)

        panel = QFrame()
        panel.setProperty("panel", True)
        proot = QVBoxLayout(panel)
        proot.setContentsMargins(0, 0, 0, 0)
        proot.setSpacing(0)
        proot.addWidget(self._build_header())
        proot.addWidget(self._build_body())
        root.addWidget(panel)

        I18N.changed.connect(self._retranslate)
        self._retranslate()

    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(f"border-bottom:1px solid {BORDER_SOFT};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)

        self.tpl_lbl = self._muted("")
        lay.addWidget(self.tpl_lbl)
        self.template_combo = QComboBox()
        names = ["Default"] + [t for t in FACTORY_TEMPLATES if t != "Default"]
        self.template_combo.addItems(names)
        self.template_combo.currentTextChanged.connect(self._apply_template)
        lay.addWidget(self.template_combo)

        self.presets_btn = QPushButton()
        self.presets_btn.clicked.connect(self._presets_menu)
        lay.addWidget(self.presets_btn)

        self.quick_btn = QPushButton()
        self.quick_btn.setProperty("accent", True)
        self.quick_btn.clicked.connect(self._quick_eq_menu)
        lay.addWidget(self.quick_btn)

        lay.addStretch(1)

        hm_box = QFrame()
        hm_box.setProperty("card", True)
        hm = QHBoxLayout(hm_box)
        hm.setContentsMargins(10, 4, 8, 4)
        hm.setSpacing(8)
        self.hm_lbl = QLabel()
        hm.addWidget(self.hm_lbl)
        self.hm_toggle = ToggleSwitch(self.state.humanize_on)
        self.hm_toggle.toggled_.connect(self._on_humanize_toggle)
        hm.addWidget(self.hm_toggle)
        self.auto_btn = QPushButton()
        self.auto_btn.setCheckable(True)
        self.auto_btn.setChecked(self.state.auto_intensity)
        self.auto_btn.clicked.connect(self._toggle_auto)
        self.auto_btn.setFixedWidth(58)
        hm.addWidget(self.auto_btn)
        lay.addWidget(hm_box)

        self.ai_btn = QPushButton()
        self.ai_btn.clicked.connect(self.analyzeAiRequested)
        lay.addWidget(self.ai_btn)

        self.export_btn = QPushButton()
        self.export_btn.setProperty("accent", True)
        self.export_btn.clicked.connect(self.exportRequested)
        lay.addWidget(self.export_btn)
        return bar

    def _build_body(self) -> QWidget:
        body = QWidget()
        lay = QHBoxLayout(body)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(10)

        self.strip_card = QFrame()
        self.strip_card.setProperty("card", True)
        sc = QVBoxLayout(self.strip_card)
        sc.setContentsMargins(12, 10, 12, 10)
        head = QHBoxLayout()
        self.strip_title = QLabel()
        self.strip_title.setStyleSheet(f"color:{ACCENT}; font-size:10px; letter-spacing:2px; font-weight:700;")
        head.addWidget(self.strip_title)
        head.addStretch(1)
        self.humanize_cap = self._muted("")
        head.addWidget(self.humanize_cap)
        self.humanize_slider = QSlider(Qt.Orientation.Horizontal)
        self.humanize_slider.setRange(0, 100)
        self.humanize_slider.setValue(int(self.state.params.humanize))
        self.humanize_slider.setFixedWidth(120)
        self.humanize_slider.valueChanged.connect(self._on_humanize_amount)
        head.addWidget(self.humanize_slider)
        self.humanize_lbl = QLabel(f"{int(self.state.params.humanize)}%")
        self.humanize_lbl.setStyleSheet(f"color:{ACCENT}; font-size:10px;")
        self.humanize_lbl.setFixedWidth(34)
        head.addWidget(self.humanize_lbl)
        sc.addLayout(head)

        strip_row = QHBoxLayout()
        strip_row.setSpacing(2)
        for key, label, unit, lo, hi, step, is_float in STRIP_CONTROLS:
            s = LabeledSlider(label, unit, lo, hi, step, is_float,
                              getattr(self.state.params.strip, key))
            s.valueChanged.connect(lambda v, k=key: self._on_strip(k, v))
            self.strip_sliders[key] = s
            strip_row.addWidget(s)
        sc.addLayout(strip_row)
        lay.addWidget(self.strip_card, stretch=3)

        eq_card = QFrame()
        eq_card.setProperty("card", True)
        ec = QVBoxLayout(eq_card)
        ec.setContentsMargins(12, 10, 12, 10)
        self.eq_title = QLabel()
        self.eq_title.setStyleSheet(f"color:{ACCENT}; font-size:10px; letter-spacing:2px; font-weight:700;")
        ec.addWidget(self.eq_title)
        eq_row = QHBoxLayout()
        eq_row.setSpacing(2)
        for i, _band in enumerate(EQ_BANDS):
            s = LabeledSlider(EQ_LABELS[i], "dB", -12, 12, 0.5, True, self.state.params.eq[i])
            s.valueChanged.connect(lambda v, idx=i: self._on_eq(idx, v))
            self.eq_sliders.append(s)
            eq_row.addWidget(s)
        ec.addLayout(eq_row)
        lay.addWidget(eq_card, stretch=2)
        return body

    # ---- i18n ---------------------------------------------------------
    def _retranslate(self):
        self.tpl_lbl.setText(tr("console.template"))
        self.presets_btn.setText(tr("console.presets") + " ▾")
        self.quick_btn.setText(tr("console.quickEq") + " ◂")
        self.hm_lbl.setText(tr("console.humanizeMaster"))
        self.auto_btn.setText(tr("console.auto") if self.state.auto_intensity else tr("console.manual"))
        self.ai_btn.setText(tr("console.analyzeAi"))
        self.export_btn.setText(tr("console.export"))
        self.strip_title.setText(tr("console.masteringStrip"))
        self.humanize_cap.setText(tr("console.humanize"))
        self.eq_title.setText(tr("console.eq"))

    # ---- helpers ------------------------------------------------------
    def _muted(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
        return lbl

    def _on_strip(self, key: str, v: float):
        setattr(self.state.params.strip, key, v)
        self._mark_custom()
        self.paramsChanged.emit()

    def _on_eq(self, idx: int, v: float):
        self.state.params.eq[idx] = v
        self._mark_custom()
        self.paramsChanged.emit()

    def _on_humanize_amount(self, v: int):
        self.state.params.humanize = float(v)
        self.humanize_lbl.setText(f"{v}%")
        self.paramsChanged.emit()

    def _on_humanize_toggle(self, on: bool):
        self.state.humanize_on = on
        for s in self.strip_sliders.values():
            s.set_enabled(on)
        self.strip_card.setEnabled(on)
        self.humanizeToggled.emit(on)

    def _toggle_auto(self):
        self.state.auto_intensity = self.auto_btn.isChecked()
        self.auto_btn.setText(tr("console.auto") if self.state.auto_intensity else tr("console.manual"))

    def _mark_custom(self):
        if self.template_combo.currentText() != "Custom":
            self.template_combo.blockSignals(True)
            if self.template_combo.findText("Custom") < 0:
                self.template_combo.insertItem(0, "Custom")
            self.template_combo.setCurrentText("Custom")
            self.template_combo.blockSignals(False)

    def _apply_template(self, name: str):
        tpl = FACTORY_TEMPLATES.get(name)
        if tpl is None:
            return
        base = Params()
        if tpl.get("strip"):
            for k, v in tpl["strip"].items():
                setattr(base.strip, k, v)
        if tpl.get("eq"):
            base.eq = list(tpl["eq"])
        if "humanize" in tpl:
            base.humanize = tpl["humanize"]
        if "lufs_target" in tpl:
            base.lufs_target = tpl["lufs_target"]
        self.state.params = base
        self.refresh_from_params()
        self.paramsChanged.emit()

    def refresh_from_params(self):
        p = self.state.params
        for key, s in self.strip_sliders.items():
            s.set_value(getattr(p.strip, key))
        for i, s in enumerate(self.eq_sliders):
            s.set_value(p.eq[i])
        self.humanize_slider.blockSignals(True)
        self.humanize_slider.setValue(int(p.humanize))
        self.humanize_slider.blockSignals(False)
        self.humanize_lbl.setText(f"{int(p.humanize)}%")

    def _presets_menu(self):
        menu = QMenu(self)
        save = menu.addAction(tr("console.savePreset"))
        menu.addSeparator()
        presets = self.preset_store.load()
        entries = {}
        if not presets:
            a = menu.addAction(tr("console.noPresets"))
            a.setEnabled(False)
        for p in presets:
            entries[menu.addAction(p["name"])] = p
        chosen = menu.exec(self.presets_btn.mapToGlobal(self.presets_btn.rect().bottomLeft()))
        if chosen == save:
            name, ok = QInputDialog.getText(self, tr("console.savePresetTitle"), tr("console.presetName"))
            if ok and name:
                self.preset_store.save(name, self.state.params)
                self.presetsChanged.emit()
        elif chosen in entries:
            self.state.params = Params.from_dict(entries[chosen]["params"])
            self.refresh_from_params()
            self._mark_custom()
            self.paramsChanged.emit()

    def _quick_eq_menu(self):
        menu = QMenu(self)
        acts = {menu.addAction(name): eq for name, eq in QUICK_EQ.items()}
        chosen = menu.exec(self.quick_btn.mapToGlobal(self.quick_btn.rect().bottomLeft()))
        if chosen in acts:
            self.state.params.eq = list(acts[chosen])
            self.refresh_from_params()
            self._mark_custom()
            self.paramsChanged.emit()
