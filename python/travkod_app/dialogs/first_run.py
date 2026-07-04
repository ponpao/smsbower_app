"""First-run honest-use notice."""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

from ..theme import TEXT, ACCENT, TEXT_DIM
from ..i18n import tr


class FirstRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("fr.title"))
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)

        p1 = QLabel(tr("fr.p1"))
        p1.setWordWrap(True)
        p1.setStyleSheet(f"color:{TEXT}; font-size:13px;")
        root.addWidget(p1)

        p2 = QLabel(tr("fr.p2"))
        p2.setWordWrap(True)
        p2.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:600;")
        root.addWidget(p2)

        p3 = QLabel(tr("fr.p3"))
        p3.setWordWrap(True)
        p3.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        root.addWidget(p3)

        ok = QPushButton(tr("fr.ok")); ok.setProperty("accent", True)
        ok.clicked.connect(self.accept)
        b = QHBoxLayout(); b.addStretch(1); b.addWidget(ok)
        root.addLayout(b)
