"""Authenticity Report dialog (BETA — honest, probabilistic, with a CI bar)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
)

from ..theme import TEXT, TEXT_MUTED, TEXT_DIM, ACCENT, ACCENT_SOFT, BORDER, WARN
from ..i18n import tr


class CIBar(QWidget):
    """Draws the confidence interval band + point estimate (never a bare number)."""

    def __init__(self, p: float, lo: float, hi: float):
        super().__init__()
        self.p, self.lo, self.hi = p, lo, hi
        self.setFixedHeight(14)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(BORDER))
        p.drawRoundedRect(QRectF(0, h / 2 - 3, w, 6), 3, 3)
        x0, x1 = self.lo * w, self.hi * w
        band = QColor(ACCENT); band.setAlpha(90)
        p.setBrush(band)
        p.drawRoundedRect(QRectF(x0, h / 2 - 3, max(3, x1 - x0), 6), 3, 3)
        p.setBrush(QColor(ACCENT_SOFT))
        p.drawRect(QRectF(self.p * w - 1, 0, 2, h))
        p.end()


class AuthenticityDialog(QDialog):
    markedAi = None  # set by caller

    def __init__(self, report: dict, is_ai: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("auth.title"))
        self.setMinimumWidth(520)
        self.result_is_ai = is_ai
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(8)

        beta = QLabel(tr("auth.beta"))
        beta.setStyleSheet(
            f"color:{WARN}; font-size:10px; padding:3px 8px; border:1px solid {WARN};"
            "border-radius:4px;")
        beta.setFixedWidth(260)
        beta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(beta)

        cap = QLabel(tr("auth.caption"))
        cap.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
        cap.setWordWrap(True)
        root.addWidget(cap)

        pct = round(report["p_ai"] * 100)
        lo, hi = round(report["ci_low"] * 100), round(report["ci_high"] * 100)
        big = QLabel(f"~{pct}%")
        big.setStyleSheet(f"color:{TEXT}; font-size:30px; font-weight:700;")
        rng = QLabel(f"{tr('auth.range')} {lo}–{hi}% · {report['confidence_label']}")
        rng.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
        row = QHBoxLayout(); row.addWidget(big); row.addSpacing(10)
        row.addWidget(rng, alignment=Qt.AlignmentFlag.AlignBottom); row.addStretch(1)
        root.addLayout(row)

        root.addWidget(CIBar(report["p_ai"], report["ci_low"], report["ci_high"]))
        ends = QHBoxLayout()
        l0 = QLabel(tr("auth.human")); l1 = QLabel(tr("auth.ai"))
        for l in (l0, l1):
            l.setStyleSheet(f"color:{TEXT_DIM}; font-size:9px;")
        ends.addWidget(l0); ends.addStretch(1); ends.addWidget(l1)
        root.addLayout(ends)

        note = QLabel(report["note"])
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{TEXT}; font-size:12px;")
        root.addSpacing(4)
        root.addWidget(note)
        disc = QLabel(report["disclaimer"])
        disc.setWordWrap(True)
        disc.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        root.addWidget(disc)

        root.addSpacing(6)
        mark_row = QHBoxLayout()
        mark_lbl = QLabel(tr("auth.markQ"))
        mark_lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
        self.mark_btn = QPushButton(tr("auth.marked") if is_ai else tr("auth.mark"))
        if is_ai:
            self.mark_btn.setProperty("accent", True)
        self.mark_btn.clicked.connect(self._toggle_ai)
        mark_row.addWidget(mark_lbl); mark_row.addStretch(1); mark_row.addWidget(self.mark_btn)
        root.addLayout(mark_row)

        hint = QLabel(tr("auth.markHint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:10px;")
        root.addWidget(hint)

        close = QPushButton(tr("auth.close")); close.clicked.connect(self.accept)
        b = QHBoxLayout(); b.addStretch(1); b.addWidget(close)
        root.addLayout(b)

    def _toggle_ai(self):
        self.result_is_ai = not self.result_is_ai
        self.mark_btn.setText(tr("auth.marked") if self.result_is_ai else tr("auth.mark"))
        self.mark_btn.setProperty("accent", self.result_is_ai)
        self.mark_btn.style().unpolish(self.mark_btn)
        self.mark_btn.style().polish(self.mark_btn)
