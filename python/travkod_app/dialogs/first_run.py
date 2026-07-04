"""First-run honest-use notice."""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

from ..theme import TEXT, ACCENT_SOFT, TEXT_DIM


class FirstRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to TRAVKOD")
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)

        p1 = QLabel("TRAVKOD improves audio quality — it makes finished tracks warmer, less "
                    "brittle and release-ready, then batch-exports them.")
        p1.setWordWrap(True)
        p1.setStyleSheet(f"color:{TEXT}; font-size:13px;")
        root.addWidget(p1)

        p2 = QLabel(f"<span style='color:{ACCENT_SOFT}; font-weight:600'>If your track uses AI, "
                    "disclose it</span> where your distributor requires. TRAVKOD does not help you "
                    "hide AI use or defeat any detection — the Authenticity Report is an "
                    "experimental, informational estimate only.")
        p2.setWordWrap(True)
        p2.setStyleSheet(f"color:{TEXT}; font-size:13px;")
        root.addWidget(p2)

        p3 = QLabel("All processing runs locally on your machine by default. Nothing is uploaded.")
        p3.setWordWrap(True)
        p3.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        root.addWidget(p3)

        ok = QPushButton("Got it"); ok.setProperty("accent", True)
        ok.clicked.connect(self.accept)
        b = QHBoxLayout(); b.addStretch(1); b.addWidget(ok)
        root.addLayout(b)
